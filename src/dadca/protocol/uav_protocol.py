import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import squared_distance, Position

from src.dadca.constant import OperationStage, Message
from src.dadca.config import initial_waypoints, PATH, ENERGY_STATION_ID
from src.dadca.constant import Agent
from src.dadca.message.acknowledge_message import AcknowledgeMessage
from src.dadca.message.packet_message import PacketMessage
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.dadca.plugin.battery_plugin import BatteryPlugin
from src.dadca.plugin.mobility_configuration import MobilityConfiguration
from src.dadca.message.uav_message import UAVMessage
from src.dadca.message.default_message import Sender, DefaultMessage
from src.dadca.plugin.mobility_plugin import MobilityPlugin
from src.dadca.plugin.mutual_exclusion_plugin import MutualExclusionPlugin


class UAVProtocol(IProtocol):
    _log: logging.Logger
    _mobility_plugin: MobilityPlugin
    _battery_plugin: BatteryPlugin
    _mutual_exclusion_plugin: MutualExclusionPlugin
    _tolerance: float = 0.01

    packet_count: int
    lamport_clock: int
    ready_to_swap: bool
    operation_stage: OperationStage

    wait: float = 0
    register: int = 1

    @classmethod
    def delay(cls):
        cls.wait += 20

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._mobility_plugin = MobilityPlugin(self, MobilityConfiguration())
        self._battery_plugin = BatteryPlugin(self, BatteryConfiguration())
        self._mutual_exclusion_plugin = MutualExclusionPlugin(self)

        self.packet_count = 0
        self.lamport_clock = 0
        self.ready_to_swap = True
        self.operation_stage = OperationStage.MISSION_START

        self._start_flight()

    def handle_timer(self, timer: str) -> None:
        if timer == OperationStage.MISSION_START.value:
            self._mobility_plugin.start_mission(initial_waypoints.pop(), PATH)

        elif (
            timer == OperationStage.DATA_COLLECTION.value
            and self.operation_stage == OperationStage.DATA_COLLECTION
        ):
            self._send_heartbeat()

        elif timer == "SWAP_DIRECTION":
            self.ready_to_swap = True


        #
        # elif timer == Timer.RETURN_MISSION.value:
        #     self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.RELEASED
        #     for _id in self._mutual_exclusion_plugin.repliers:
        #         self._reply_entry(_id)
        #
        #     self._battery_plugin.move_to_critical_battery_position()
        #     self._mobility_plugin.start_mission(
        #         initial_waypoint=self._mobility_plugin.current_waypoint,
        #         path=PATH,
        #         direction=self._mobility_plugin.current_direction,
        #     )

        # elif timer == Timer.RECHARGE_BATTERY.value:
        #     self._battery_plugin.recharge_battery()
        #
        # elif timer == Timer.REQUEST_ENERGY_STATION.value:
        #     self._request_information_from_energy_station()
        #     self._mutual_exclusion_plugin.evaluate_entry_score(
        #         self.lamport_clock,
        #         self._battery_plugin.battery
        #     )
        #     self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.WANTED
        #
        # elif timer == Timer.CRITICAL_SECTION.value:
        #     if (
        #         self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED
        #         and self._mutual_exclusion_plugin.check_all_replies()
        #     ):
        #         self._mutual_exclusion_plugin.critical_section_status = CriticalSectionStatus.HELD
        #         self._battery_plugin.move_to_energy_station()
        #
        #     else:
        #         self.provider.schedule_timer(
        #             Timer.CRITICAL_SECTION.value,
        #             self.provider.current_time() + 1
        #         )
        #
        # elif timer == Timer.CLEAR_RENDEZVOUS.value:
        #     self._mobility_plugin.ready_to_rendesvouz = True

        else:
            raise NotImplementedError(f"There is no current support to timer {timer}")

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.label == Message.PACKET:
            message = PacketMessage.model_validate_json(message)
            self.packet_count += message.packet_count
            if default_message.sender.agent == Agent.UAV and self.ready_to_swap:
                self._swap_direction()
                self.ready_to_swap = False
                self.provider.schedule_timer("SWAP_DIRECTION", self.provider.current_time() + 2)



        if default_message.label == Message.ACKNOWLEDGE:
            message = AcknowledgeMessage.model_validate_json(message)




            # if self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED:

                # if (
                #     self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.WANTED
                #     and self._mutual_exclusion_plugin.compare_entry_score(
                #         message.entry_score,
                #         message.sender.id
                # )
                #     or self._mutual_exclusion_plugin.critical_section_status == CriticalSectionStatus.HELD
                # ):
                #     self._mutual_exclusion_plugin.repliers.add(message.sender.id)
                #     self.provider.schedule_timer(
                #         Timer.CRITICAL_SECTION.value,
                #         self.provider.current_time()
                #     )

        elif default_message.sender.agent == Agent.GROUND_STATION:
            self.packet_count = 0

        # elif default_message.sender.agent == Agent.ENERGY_STATION:
        #     message = EnergyStationMessage.model_validate_json(message)
        #     self._mutual_exclusion_plugin.number_uavs = message.number_uavs
        #     self._broadcast()

        # else:
        #     raise NotImplementedError(f"There is no current support to agent {default_message.sender.agent}")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        current_position = telemetry.current_position

        def _has_reached(_current_position: Position, target_position: Position) -> bool:
            return (
                squared_distance(_current_position, target_position)
                <= self._tolerance ** 2
            )

        if (
            self.operation_stage == OperationStage.MISSION_START
            and self._mobility_plugin.initial_position
            and _has_reached(current_position, self._mobility_plugin.initial_position)
        ):
            self.operation_stage = OperationStage.DATA_COLLECTION
            self.provider.schedule_timer(self.operation_stage.value, self.provider.current_time())

        elif (
            self.operation_stage == OperationStage.DATA_COLLECTION
            and self._battery_plugin.has_reached_critical_battery(current_position)
        ):
            self.operation_stage = OperationStage.WAIT_FOR_RECHARGE
            self._mobility_plugin.move_to_position(self._mutual_exclusion_plugin.free_spot)

        elif (
            self.operation_stage == OperationStage.WAIT_FOR_RECHARGE
            and _has_reached(current_position, self._mutual_exclusion_plugin.free_spot)
        ):
            pass


    def _start_flight(self):
        self.provider.schedule_timer(
            OperationStage.MISSION_START.value,
            self.provider.current_time() + self.wait
        )
        self.delay()

    def _send_heartbeat(self) -> None:
        self._broadcast()
        self.provider.schedule_timer(
            self.operation_stage.DATA_COLLECTION.value,
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

    def _swap_direction(self) -> None:
        if self.ready_to_swap:
            self._mobility_plugin.reverse_direction()
            self._mobility_plugin.change_current_waypoint()
            self._mobility_plugin.travel_to_current_waypoint()

    def finish(self) -> None:
        self._log.info(f"Final Lamport clock: {self.lamport_clock}")