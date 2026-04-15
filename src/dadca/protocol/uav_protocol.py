import logging
import math

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.config import initial_waypoints, PATH, ENERGY_STATION_POSITION, DIAMETER, ENERGY_STATION_ID, \
    AERIAL_ENERGY_STATION_POSITION, NUMBER_UVAS
from src.dadca.constant import Agent, Timer, CriticalSectionStatus
from src.dadca.domain.energy_station_message import EnergyStationMessage
from src.dadca.domain.package_message import PacketMessage
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.dadca.plugin.battery_plugin import BatteryPlugin
from src.dadca.plugin.mobility_configuration import MobilityConfiguration
from src.dadca.domain.uav_message import UAVMessage
from src.dadca.domain.default_message import Sender, DefaultMessage
from src.dadca.plugin.mobility_plugin import MobilityPlugin
from src.geometry.point import Point
from src.geometry.vector import Vector


class UAVProtocol(IProtocol):
    _log: logging.Logger
    _mobility_plugin: MobilityPlugin
    _battery_plugin: BatteryPlugin
    _to_heartbeat: bool
    _critical_section_status: CriticalSectionStatus | None = None
    _waiting_position: Point | None = None
    _entry_score: float | None = None
    _number_uavs_in_group: int | None = None
    _reply_to: set[int] = set()

    lamport_clock: int
    packet_count: int
    wait: float = 0
    uav_number: int = 1

    @classmethod
    def delay(cls):
        cls.wait += 20

    @classmethod
    def increase_uav_number(cls):
        if cls.uav_number > NUMBER_UVAS:
            cls.uav_number = 1
        else:
            cls.uav_number += 1

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._mobility_plugin = MobilityPlugin(self, MobilityConfiguration())
        self._battery_plugin = BatteryPlugin(self, BatteryConfiguration())

        self._to_heartbeat = True
        self.packet_count = 0
        self.lamport_clock = 0

        self._start_flight()
        self._send_heartbeat()

    def handle_timer(self, timer: str) -> None:
        if timer == Timer.HEARTBEAT.value:
            self._send_heartbeat()

        elif timer == Timer.START_MISSION.value:
            self._mobility_plugin.start_mission(
                initial_waypoint=initial_waypoints.pop(),
                path=PATH,
            )

        elif timer == Timer.BATTERY.value:
            self._move_to_waiting_area_energy_station()

        elif timer == Timer.CRITICAL_SECTION.value:
            if len(self._reply_to) == self._number_uavs_in_group - 1:
                self._enter_energy_station()
                self._enter_energy_station()

            if self._critical_section_status == CriticalSectionStatus.RELEASED:
                for _id in self._reply_to:
                    self._reply_entry(_id)

            else:
                self.provider.schedule_timer(
                    Timer.CRITICAL_SECTION.value,
                    self.provider.current_time() + 1
                )

        elif timer == Timer.CLEAR_RENDEZVOUS.value:
            self._mobility_plugin.ready_to_rendesvouz = True

        else:
            raise NotImplementedError(f"There is no current support to timer {timer}")

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.sender.agent == Agent.SENSOR:
            message = PacketMessage.model_validate_json(message)
            self.packet_count += message.packet_count

        elif default_message.sender.agent == Agent.UAV:
            message = UAVMessage.model_validate_json(message)

            if self._mobility_plugin.on_mission:
                self.packet_count += message.packet_count

                if self._is_rendezvous():
                    self._execute_rendezvous()
                    self.provider.schedule_timer(
                        Timer.CLEAR_RENDEZVOUS.value,
                        self.provider.current_time() + 2
                    )

            if self._critical_section_status is not None:

                if (
                    self._critical_section_status == CriticalSectionStatus.WANTED
                    and self._compare_entry_score(message.entry_score, message.sender.id)
                    or self._critical_section_status == CriticalSectionStatus.HELD
                ):
                        self._log.info(f"{self.provider.get_id()}>>>>>>{default_message.sender.id}")
                        self._reply_to.add(message.sender.id)
                        self.provider.schedule_timer(
                            Timer.CRITICAL_SECTION.value,
                            self.provider.current_time() + 1
                        )
                else:
                    self._log.info(f"{self.provider.get_id()}->{default_message.sender.id}")
                    self._reply_entry(message.sender.id)

        elif default_message.sender.agent == Agent.GROUND_STATION:
            self.packet_count = 0

        elif default_message.sender.agent == Agent.ENERGY_STATION:
            message = EnergyStationMessage.model_validate_json(message)
            self._number_uavs_in_group = message.number_uavs
            self._request_entry()

        else:
            raise NotImplementedError(f"There is no current support to agent {default_message.sender.agent}")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        if self._waiting_position:
            current_position = telemetry.current_position

            if self._mobility_plugin.has_reached_target(current_position, self._waiting_position):
                self._critical_section_status = CriticalSectionStatus.WANTED
                self._entry_score = 0.5 / self.lamport_clock + 0.5 / self._battery_plugin.battery

                self._waiting_position = None
                message = DefaultMessage.model_construct(
                    lamport_clock=self.lamport_clock,
                    sender=Sender.model_construct(
                        agent=Agent.UAV,
                        id=self.provider.get_id()
                    )
                )
                command = SendMessageCommand(message.model_dump_json(), ENERGY_STATION_ID)
                self.provider.send_communication_command(command)

    def _start_flight(self):
        self.provider.schedule_timer(
            Timer.START_MISSION.value,
            self.provider.current_time() + self.wait
        )
        self.delay()

    def _send_heartbeat(self) -> None:
        if self._to_heartbeat:
            self._broadcast()
            self.provider.schedule_timer(
                Timer.HEARTBEAT.value,
                self.provider.current_time() + 1
            )

    def _broadcast(self):
        self.lamport_clock += 1
        uav_message = UAVMessage.model_construct(
            lamport_clock=self.lamport_clock,
            packet_count=self.packet_count,
            do_rendezvous=False,
            entry_score=self._entry_score,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )
        command = BroadcastMessageCommand(uav_message.model_dump_json())
        self.provider.send_communication_command(command)

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def _is_rendezvous(self) -> bool:
        return self._mobility_plugin.ready_to_rendesvouz

    def _execute_rendezvous(self) -> None:
        self._mobility_plugin.reverse_direction()
        self._mobility_plugin.change_current_waypoint()
        self._mobility_plugin.travel_to_current_waypoint()
        self._mobility_plugin.ready_to_rendesvouz = False

    def _move_to_waiting_area_energy_station(self) -> None:
        self._mobility_plugin.on_mission = False
        self._to_heartbeat = False

        direction = Vector(1, 0, 0)
        angle = 2 * math.pi * self.uav_number/NUMBER_UVAS
        self._waiting_position = AERIAL_ENERGY_STATION_POSITION + direction.rotate(angle).normalize() * (DIAMETER / 2)
        self.increase_uav_number()

        mobility_command = GotoCoordsMobilityCommand(*self._waiting_position)
        self.provider.send_mobility_command(mobility_command)

    def _request_entry(self):
        self._broadcast()

    def _reply_entry(self, _id: int):
        self.lamport_clock += 1
        uav_message = UAVMessage.model_construct(
            lamport_clock=self.lamport_clock,
            packet_count=self.packet_count,
            do_rendezvous=False,
            entry_score=self._entry_score,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )
        command = SendMessageCommand(uav_message.model_dump_json(), _id)
        self.provider.send_communication_command(command)

    def _compare_entry_score(self, entry_score: float, _id: int) -> bool:
        if self._entry_score < entry_score:
            return True
        elif self._entry_score > entry_score:
            return False
        else:
            return self.provider.get_id() < _id

    def _enter_energy_station(self):
        self._critical_section_status = CriticalSectionStatus.HELD

        mobility_command = GotoCoordsMobilityCommand(*ENERGY_STATION_POSITION)
        self.provider.send_mobility_command(mobility_command)

    def finish(self) -> None:
        self._log.info(f"Final Lamport clock: {self.lamport_clock}")