import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import squared_distance, Position
from typing_extensions import NamedTuple

from src.dadca.constant import OperationStage, Message
from src.dadca.config import initial_waypoints, PATH, NUMBER_UVAS, ENERGY_STATION_POSITION
from src.dadca.constant import Agent
from src.dadca.message.acknowledgement_message import AcknowledgementMessage
from src.dadca.message.energy_station_message import EnergyStationMessage
from src.dadca.message.entry_critical_section_message import EntryCriticalSectionMessage
from src.dadca.message.packet_message import PacketMessage
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.dadca.plugin.battery_plugin import BatteryPlugin
from src.dadca.plugin.mobility_configuration import MobilityConfiguration
from src.dadca.message.default_message import Sender, DefaultMessage
from src.dadca.plugin.mobility_plugin import MobilityPlugin
from src.dadca.plugin.mutual_exclusion_plugin import MutualExclusionPlugin
from src.dadca.utils import get_waiting_position


class UAVProtocol(IProtocol):
    _log: logging.Logger
    _mobility_plugin: MobilityPlugin
    _battery_plugin: BatteryPlugin
    _mutual_exclusion_plugin: MutualExclusionPlugin
    _tolerance: float = 0.5

    waiting_position: NamedTuple
    packet_count: int
    lamport_clock: int
    ready_to_swap: bool
    operation_stage: OperationStage

    wait: float = 0
    order: int = 1

    @classmethod
    def delay(cls):
        cls.wait += 20

    @classmethod
    def increase(cls):
        cls.order += 1 if cls.order < NUMBER_UVAS else 1

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._mobility_plugin = MobilityPlugin(self, MobilityConfiguration())
        self._battery_plugin = BatteryPlugin(self, BatteryConfiguration())
        self._mutual_exclusion_plugin = MutualExclusionPlugin(self)

        self.packet_count = 0
        self.lamport_clock = 0
        self.ready_to_swap = True
        self.operation_stage = OperationStage.MISSION_START
        self.waiting_position = get_waiting_position(self.order)
        self.increase()

        self._start_flight()

    def handle_timer(self, timer: str) -> None:
        if timer == OperationStage.MISSION_START.value:
            self._mobility_plugin.start_mission(initial_waypoints.pop(), PATH)

        elif timer == OperationStage.DATA_COLLECTION.value:
            if self.operation_stage == OperationStage.DATA_COLLECTION:
                self.lamport_clock += 1
                message = self._build_packet_message()
                self._send_heartbeat(message)

        elif timer == OperationStage.RECHARGE.value:
            if self._battery_plugin.battery < 100:
                self._battery_plugin.recharge_battery()
                self.provider.schedule_timer(
                    OperationStage.RECHARGE.value,
                    self.provider.current_time() +1
                )
            else:
                self._mobility_plugin.move_to_position(self.waiting_position)
                self._mutual_exclusion_plugin.notify_waiter_nodes()

        elif timer == "SWAP_DIRECTION":
            self.ready_to_swap = True

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

        elif default_message.label == Message.ENERGY_STATION:
            message = EnergyStationMessage.model_validate_json(message)
            self._mutual_exclusion_plugin.number_nodes = message.number_uavs
            self._mutual_exclusion_plugin.priority = 1/self._battery_plugin.battery
            entry_critical_section_message = self._build_entry_critical_section_message()
            self._broadcast(entry_critical_section_message)

        elif default_message.label == Message.ENTRY_CRITICAL_SECTION:
            message = EntryCriticalSectionMessage.model_validate_json(message)
            self._log.info(f"Mensagem de {default_message.sender.id} ({message.priority}) para {self.provider.get_id()} ({self._mutual_exclusion_plugin.priority})")
            _id = message.sender.id
            if self._mutual_exclusion_plugin.compare_priority(message.priority, _id):
                self._mutual_exclusion_plugin.waiter_nodes.append(_id)
            else:
                response = self._build_acknowledgement_message()
                self._mutual_exclusion_plugin.reply_node(response, _id)

        elif default_message.label == Message.ACKNOWLEDGEMENT:
            message = AcknowledgementMessage.model_validate_json(message)
            self._mutual_exclusion_plugin.acknowledgments.append(message.sender.id)
            self._log.info(f"Eu tenho os seguintes acknowledgments: {self._mutual_exclusion_plugin.acknowledgments}")

            if self._mutual_exclusion_plugin.check_all_acknolewdgements():
                self._mobility_plugin.move_to_position(ENERGY_STATION_POSITION)

        elif default_message.sender.agent == Agent.GROUND_STATION:
            self.packet_count = 0

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        current_position = telemetry.current_position

        def _has_reached(_current_position: Position, target_position: NamedTuple) -> bool:
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
            self._mobility_plugin.move_to_position(self.waiting_position)

        elif (
            self.operation_stage == OperationStage.WAIT_FOR_RECHARGE
            and _has_reached(current_position, self.waiting_position)
        ):
            default_message = self._build_default_message()
            self._mutual_exclusion_plugin.ask_number_nodes_to_reply(default_message)
            self.operation_stage = OperationStage.RECHARGE

        elif (
            self.operation_stage == OperationStage.RECHARGE
            and _has_reached(current_position, ENERGY_STATION_POSITION)
        ):
            self.provider.schedule_timer(self.operation_stage.value, self.provider.current_time())

    def _build_packet_message(self) -> PacketMessage:
        return PacketMessage.model_construct(
            packet_count=self.packet_count,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_default_message(self) -> DefaultMessage:
        return DefaultMessage.model_construct(
            packet_count=self.packet_count,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_entry_critical_section_message(self):
        return EntryCriticalSectionMessage.model_construct(
            priority=self._mutual_exclusion_plugin.priority,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_acknowledgement_message(self):
        return AcknowledgementMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _start_flight(self):
        self.provider.schedule_timer(
            OperationStage.MISSION_START.value,
            self.provider.current_time() + self.wait
        )
        self.delay()

    def _send_heartbeat(self, message: DefaultMessage) -> None:
        self._broadcast(message)
        self.provider.schedule_timer(
            self.operation_stage.DATA_COLLECTION.value,
            self.provider.current_time() + 1
        )

    def _broadcast(self, message: DefaultMessage) -> None:
        command = BroadcastMessageCommand(message.model_dump_json())
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