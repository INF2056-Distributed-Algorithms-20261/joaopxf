import logging
import random

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import squared_distance, Position
from typing_extensions import NamedTuple

from src.dadca.constant import UAVOperation, Message, Movement
from src.dadca.config import INITIAL_WAYPOINTS, PATH, NUMBER_UVAS, ENERGY_STATION_POSITION, GROUND_STATION_POSITION, \
    MIN_NUMBER_INFORMATION
from src.dadca.constant import Agent
from src.dadca.message.acknowledgement_message import AcknowledgementMessage
from src.dadca.message.energy_station_message import EnergyStationMessage
from src.dadca.message.ground_station_message import GroundStationMessage
from src.dadca.message.number_nodes_critical_section_message import NumberNodesCriticalSectionMessage
from src.dadca.message.information_message import InformationMessage
from src.dadca.message.priority_critical_section_message import PriorityCriticalSectionMessage
from src.dadca.message.release_critical_section_message import ReleaseCriticalSectionMessage
from src.dadca.message.welcome_message import WelcomeMessage
from src.dadca.object.packet import Packet
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
    packets: set[Packet]
    lamport_clock: int
    reset_map: bool
    ready_to_swap: bool
    operation_stage: UAVOperation

    initial_battery: float = random.uniform(90, 100)
    wait: float = 0
    order: int = 1

    @classmethod
    def delay(cls):
        cls.wait += 20

    @classmethod
    def increase(cls):
        cls.order += 1 if cls.order < NUMBER_UVAS else 1

    @classmethod
    def change_initial_battery(cls):
        cls.initial_battery = random.uniform(80, 100)

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._mobility_plugin = MobilityPlugin(self, MobilityConfiguration())
        self._battery_plugin = BatteryPlugin(self, BatteryConfiguration(), self.initial_battery)
        self._mutual_exclusion_plugin = MutualExclusionPlugin(self)

        self.packets = set()
        self.lamport_clock = 0
        self.reset_map = False
        self.ready_to_swap = False
        self.operation_stage = UAVOperation.MISSION_START
        self.waiting_position = get_waiting_position(self.order)

        self.change_initial_battery()
        self.increase()

        self._start_flight()

    def handle_timer(self, timer: str) -> None:
        if timer == UAVOperation.MISSION_START.value:
            self._mobility_plugin.start_mission(INITIAL_WAYPOINTS.pop(), PATH)

        elif timer == UAVOperation.DATA_COLLECTION.value:
            if self.operation_stage == UAVOperation.DATA_COLLECTION:
                self.lamport_clock += 1
                message = self._build_welcome_message()
                self._send_heartbeat(message)

        elif timer == UAVOperation.RECHARGE.value:
            if self._battery_plugin.get_battery() < 100:
                self._battery_plugin.recharge_battery()
                self.provider.schedule_timer(
                    UAVOperation.RECHARGE.value,
                    self.provider.current_time() + 1
                )
            else:
                return_waypoint = self._mobility_plugin.current_waypoint
                return_direction = self._mobility_plugin.current_direction
                self._mobility_plugin.start_mission(return_waypoint, PATH, return_direction)

                message = self._build_acknowledgement_message(entry_crtical_section=True)
                self._mutual_exclusion_plugin.notify_waiter_nodes(message)
                self._mutual_exclusion_plugin.reset()

                message = self._build_release_critical_section_message()
                self._mutual_exclusion_plugin.send_message_to_central_station(message)

        else:
            raise NotImplementedError(f"There is no current support to timer {timer}")

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.label == Message.WELCOME:
            message = WelcomeMessage.model_validate_json(message)
            response = self._build_information_message()
            command = SendMessageCommand(response.model_dump_json(), message.sender.id)
            self.provider.send_communication_command(command)

        if default_message.label == Message.INFORMATION:
            message = InformationMessage.model_validate_json(message)
            self.packets.update(message.packets)

            if message.sender.agent == Agent.UAV:
                response = self._build_acknowledgement_message(information=True)
                command = SendMessageCommand(response.model_dump_json(), message.sender.id)
                self.provider.send_communication_command(command)

                if self._check_need_to_swap(message.direction, message.last_waypoint):
                    self.ready_to_swap = True

                for _id, battery in message.battery_map.items():
                    self._battery_plugin.battery_map[_id] = battery

                number_information = len(self._battery_plugin.battery_map)
                if number_information >= MIN_NUMBER_INFORMATION:
                    index = self._get_sorted_index()
                    if index == 1 or index == number_information:
                        self.ready_to_swap = False
                        self.reset_map = True
                        if index == 1:
                            self.operation_stage = UAVOperation.WAIT_FOR_RECHARGE
                            self._mobility_plugin.move_to_position(self.waiting_position)
                        else:
                            self._mobility_plugin.move_to_position(GROUND_STATION_POSITION)

        elif default_message.label == Message.ENERGY_STATION:
            message = EnergyStationMessage.model_validate_json(message)
            self._mutual_exclusion_plugin.set_neighbors(message.group)
            if len(self._mutual_exclusion_plugin.neighbors) == 0:
                self._mobility_plugin.move_to_position(ENERGY_STATION_POSITION)
            else:
                response = self._build_priority_critical_section_message()
                self._mutual_exclusion_plugin.send_message_to_nodes(response)

        elif default_message.label == Message.PRIORITY_CRITICAL_SECTION:
            message = PriorityCriticalSectionMessage.model_validate_json(message)
            _id = message.sender.id
            if self._mutual_exclusion_plugin.compare_priority(message.priority, _id):
                self._mutual_exclusion_plugin.waiter_nodes.append(_id)
            else:
                response = self._build_acknowledgement_message(entry_crtical_section=True)
                self._mutual_exclusion_plugin.reply_node(response, _id)

        elif default_message.label == Message.ACKNOWLEDGEMENT:
            message = AcknowledgementMessage.model_validate_json(message)
            if message.entry_critical_section:
                self._mutual_exclusion_plugin.acknowledgements.append(message.sender.id)
                if self._mutual_exclusion_plugin.check_all_acknowledgements():
                    self._mobility_plugin.move_to_position(ENERGY_STATION_POSITION)
            if message.information:
                if self.reset_map:
                    self._battery_plugin.reset_battery_map()
                    self.reset_map = False
                if self.ready_to_swap:
                    self._swap_direction()

        elif default_message.label == Message.GROUND_STATION:
            message = GroundStationMessage.model_validate_json(message)
            response = self._build_information_message()
            command = SendMessageCommand(response.model_dump_json(), message.sender.id)
            self.provider.send_communication_command(command)

            self.packets.clear()

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        current_position = telemetry.current_position

        def _has_reached(_current_position: Position, target_position: NamedTuple) -> bool:
            return (
                squared_distance(_current_position, target_position)
                <= self._tolerance ** 2
            )

        if (
            self.operation_stage == UAVOperation.MISSION_START
            and self._mobility_plugin.initial_position
            and _has_reached(current_position, self._mobility_plugin.initial_position)
        ):
            self.ready_to_swap = True
            self.operation_stage = UAVOperation.DATA_COLLECTION
            self.provider.schedule_timer(self.operation_stage.value, self.provider.current_time())

        elif (
            self.operation_stage == UAVOperation.DATA_COLLECTION
            and _has_reached(current_position, GROUND_STATION_POSITION)
        ):
            self._battery_plugin.reset_battery_map()
            return_waypoint = self._mobility_plugin.current_waypoint
            return_direction = self._mobility_plugin.current_direction
            self.operation_stage = UAVOperation.MISSION_START
            self._mobility_plugin.start_mission(return_waypoint, PATH, return_direction)

        elif (
            self.operation_stage == UAVOperation.DATA_COLLECTION
            and self._battery_plugin.has_reached_critical_battery(current_position)
        ):
            self.ready_to_swap = False
            self.reset_map = True
            self._battery_plugin.reset_battery_map()
            self.operation_stage = UAVOperation.WAIT_FOR_RECHARGE
            self._mobility_plugin.move_to_position(self.waiting_position)

        elif (
            self.operation_stage == UAVOperation.WAIT_FOR_RECHARGE
            and _has_reached(current_position, self.waiting_position)
        ):
            message = self._build_number_nodes_critical_section_message()
            self._mutual_exclusion_plugin.send_message_to_central_station(message)
            self._mutual_exclusion_plugin.priority = 1 / self._battery_plugin.get_battery()
            self.operation_stage = UAVOperation.RECHARGE

        elif (
            self.operation_stage == UAVOperation.RECHARGE
            and _has_reached(current_position, ENERGY_STATION_POSITION)
        ):
            self.provider.schedule_timer(self.operation_stage.value, self.provider.current_time())
            self.operation_stage = UAVOperation.MISSION_START

    def _build_welcome_message(self):
        return WelcomeMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_information_message(self) -> InformationMessage:
        return InformationMessage.model_construct(
            direction=self._mobility_plugin.current_direction,
            last_waypoint=self._mobility_plugin.last_waypoint,
            battery_map=self._battery_plugin.battery_map,
            packets=self.packets,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_number_nodes_critical_section_message(self) -> NumberNodesCriticalSectionMessage:
        return NumberNodesCriticalSectionMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_priority_critical_section_message(self) -> PriorityCriticalSectionMessage:
        return PriorityCriticalSectionMessage.model_construct(
            priority=self._mutual_exclusion_plugin.priority,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_acknowledgement_message(
        self,
        entry_crtical_section: bool = False,
        information: bool = False,
    ) -> AcknowledgementMessage:
        return AcknowledgementMessage.model_construct(
            entry_critical_section=entry_crtical_section,
            information=information,
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _build_release_critical_section_message(self) -> ReleaseCriticalSectionMessage:
        return ReleaseCriticalSectionMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.UAV,
                id=self.provider.get_id()
            )
        )

    def _start_flight(self):
        self.provider.schedule_timer(
            UAVOperation.MISSION_START.value,
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

    def _get_sorted_index(self) -> int:
        _id = self.provider.get_id()
        sorted_ids = sorted(
            self._battery_plugin.battery_map,
            key=lambda k: self._battery_plugin.battery_map[k]
        )
        for index, sorted_id in enumerate(sorted_ids, 1):
            if _id == sorted_id:
                return index
        else:
            raise self._log.error(f"The {_id} must be in the sorted id list.")

    def _check_need_to_swap(self, direction: Movement, last_waypoint: int) -> bool:
        if (
            self._mobility_plugin.current_direction == Movement.FORWARD
            and direction == Movement.BACKWARD
        ):
            return self._mobility_plugin.last_waypoint <= last_waypoint
        elif (
            self._mobility_plugin.current_direction == Movement.BACKWARD
            and direction == Movement.FORWARD
        ):
            return self._mobility_plugin.last_waypoint >= last_waypoint
        else:
            return False

    def _swap_direction(self) -> None:
        self._mobility_plugin.reverse_direction()
        self._mobility_plugin.change_current_waypoint()
        self._mobility_plugin.travel_to_current_waypoint()
        self.ready_to_swap = False

    def finish(self) -> None:
        pass