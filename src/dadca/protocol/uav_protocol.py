import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.config import initial_waypoints, PATH, ENERGY_STATION_ID, NUMBER_UVAS
from src.dadca.constant import Agent, Timer, CriticalSectionStatus
from src.dadca.domain.energy_station_message import EnergyStationMessage
from src.dadca.domain.package_message import PacketMessage
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.dadca.plugin.battery_plugin import BatteryPlugin
from src.dadca.plugin.mobility_configuration import MobilityConfiguration
from src.dadca.domain.uav_message import UAVMessage
from src.dadca.domain.default_message import Sender, DefaultMessage
from src.dadca.plugin.mobility_plugin import MobilityPlugin
from src.dadca.plugin.mutual_exclusion_plugin import MutualExclusionPlugin


class UAVProtocol(IProtocol):
    _log: logging.Logger
    _mobility_plugin: MobilityPlugin
    _battery_plugin: BatteryPlugin
    _mutual_exclusion_plugin: MutualExclusionPlugin

    lamport_clock: int
    packet_count: int
    wait: float = 0
    register: int = 1

    @classmethod
    def delay(cls):
        cls.wait += 20

    @classmethod
    def increase_register(cls):
        if cls.register > NUMBER_UVAS:
            cls.register = 1
        else:
            cls.register += 1

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._mobility_plugin = MobilityPlugin(self, MobilityConfiguration())
        self._battery_plugin = BatteryPlugin(self, BatteryConfiguration())
        self._mutual_exclusion_plugin = MutualExclusionPlugin(self)

        self.packet_count = 0
        self.lamport_clock = 0

        self._start_flight()
        self._send_heartbeat()

    def handle_timer(self, timer: str) -> None:
        if (
            timer == Timer.HEARTBEAT.value
            and not self._battery_plugin.disable_heartbeat
        ):
            self._send_heartbeat()

        elif timer == Timer.START_MISSION.value:
            self._mobility_plugin.start_mission(
                initial_waypoint=initial_waypoints.pop(),
                path=PATH,
            )

        elif timer == Timer.INTERRUPT_MISSION.value:
            self._mobility_plugin.on_mission = False
            self._battery_plugin.disable_heartbeat = True
            self._battery_plugin.move_to_energy_station_waiting_area(self.register)
            self.increase_register()

        elif timer == Timer.RETURN_MISSION.value:
            self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.RELEASED
            for _id in self._mutual_exclusion_plugin.repliers:
                self._reply_entry(_id)

            self._battery_plugin.move_to_critical_battery_position()
            self._mobility_plugin.start_mission(
                initial_waypoint=self._mobility_plugin.current_waypoint,
                path=PATH,
                direction=self._mobility_plugin.current_direction,
            )

        elif timer == Timer.RECHARGE_BATTERY.value:
            self._battery_plugin.recharge_battery()

        elif timer == Timer.REQUEST_ENERGY_STATION.value:
            self._request_information_from_energy_station()
            self._mutual_exclusion_plugin.evaluate_entry_score(
                self.lamport_clock,
                self._battery_plugin.battery
            )
            self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.WANTED

        elif timer == Timer.CRITICAL_SECTION.value:
            if (
                self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED
                and self._mutual_exclusion_plugin.check_all_replies()
            ):
                self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.HELD
                self._battery_plugin.move_to_energy_station()

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

                if self._mobility_plugin.ready_to_rendesvouz:
                    self._execute_rendezvous()
                    self.provider.schedule_timer(
                        Timer.CLEAR_RENDEZVOUS.value,
                        self.provider.current_time() + 2
                    )

            if self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED:

                if (
                    self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED
                    and self._mutual_exclusion_plugin.compare_entry_score(
                        message.entry_score,
                        message.sender.id
                )
                    or self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.HELD
                ):
                    self._mutual_exclusion_plugin.repliers.add(message.sender.id)
                    self.provider.schedule_timer(
                        Timer.CRITICAL_SECTION.value,
                        self.provider.current_time()
                    )

        elif default_message.sender.agent == Agent.GROUND_STATION:
            self.packet_count = 0

        elif default_message.sender.agent == Agent.ENERGY_STATION:
            message = EnergyStationMessage.model_validate_json(message)
            self._mutual_exclusion_plugin.number_uavs = message.number_uavs
            self._broadcast()

        else:
            raise NotImplementedError(f"There is no current support to agent {default_message.sender.agent}")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def _start_flight(self):
        self.provider.schedule_timer(
            Timer.START_MISSION.value,
            self.provider.current_time() + self.wait
        )
        self.delay()

    def _send_heartbeat(self) -> None:
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
            entry_score=self._mutual_exclusion_plugin.entry_score,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )
        command = BroadcastMessageCommand(uav_message.model_dump_json())
        self.provider.send_communication_command(command)

    def _request_information_from_energy_station(self):
        message = DefaultMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )
        command = SendMessageCommand(message.model_dump_json(), ENERGY_STATION_ID)
        self.provider.send_communication_command(command)

    def _reply_entry(self, _id: int):
        message = UAVMessage.model_construct(
            lamport_clock=self.lamport_clock,
            packet_count=self.packet_count,
            entry_score=self._mutual_exclusion_plugin.entry_score,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )
        command = SendMessageCommand(message.model_dump_json(), _id)
        self.provider.send_communication_command(command)

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def _execute_rendezvous(self) -> None:
        self._mobility_plugin.reverse_direction()
        self._mobility_plugin.change_current_waypoint()
        self._mobility_plugin.travel_to_current_waypoint()
        self._mobility_plugin.ready_to_rendesvouz = False

    def finish(self) -> None:
        self._log.info(f"Final Lamport clock: {self.lamport_clock}")