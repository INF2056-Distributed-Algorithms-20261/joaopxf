import logging
from collections import defaultdict

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.constant import Agent, Message, EnergyStationOperation
from src.dadca.message.default_message import Sender
from src.dadca.message.energy_station_message import DefaultMessage, EnergyStationMessage


class EnergyStationProtocol(IProtocol):
    _log: logging.Logger
    _newer_group: bool
    lamport_clock: int
    last_releases: int
    group_number: int
    uavs_per_group: dict[int, list[int]]

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self._newer_group = True
        self.lamport_clock = 0
        self.last_releases = 0
        self.group_number = 1

        self.uavs_per_group = defaultdict(list)

    def handle_timer(self, timer: str) -> None:
        if timer == EnergyStationOperation.CHANGE_GROUP.value:
            self._log.info(f"There are {len(self.uavs_per_group[self.group_number])} UAVs in group {self.group_number}")
            self._newer_group = True
            self.group_number += 1

            if len(self.uavs_per_group) == 1:
                key = next(iter(self.uavs_per_group))
                group = self.uavs_per_group[key]
                message = self._build_energy_station_message(group)
                self._broadcast(message)

    def handle_packet(self, message: str) -> None:
        message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(message.lamport_clock)

        if message.label == Message.NUMBER_NODES_CRITICAL_SECTION:
            self.uavs_per_group[self.group_number].append(message.sender.id)
            if self._newer_group:
                self._newer_group = False
                self.provider.schedule_timer(
                    EnergyStationOperation.CHANGE_GROUP.value,
                    self.provider.current_time() + 100
                )

        elif message.label == Message.RELEASE_CRITICAL_SECTION:
            self.last_releases += 1
            key = next(iter(self.uavs_per_group))
            self._log.info(f"Group {key} releases: {self.last_releases}/{len(self.uavs_per_group[key])}")
            if self.last_releases == len(self.uavs_per_group[key]):
                self.uavs_per_group.pop(key)
                self.last_releases = 0
                if self.uavs_per_group:
                    self._reply_to_waiting_group()

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass

    def _build_energy_station_message(self, group: list[int]) -> DefaultMessage:
        return EnergyStationMessage.model_construct(
            lamport_clock=self.lamport_clock,
            group=group,
            sender=Sender.model_construct(
                agent=Agent.ENERGY_STATION,
                id=self.provider.get_id()
            ),
        )

    def _reply_to_waiting_group(self):
        key = next(iter(self.uavs_per_group))
        group = self.uavs_per_group[key]
        message = self._build_energy_station_message(group)

        for _id in self.uavs_per_group[key]:
            self._log.info(f"Sending message to {_id} from group {key}")
            command = SendMessageCommand(message.model_dump_json(), _id)
            self.provider.send_communication_command(command)

    def _broadcast(self, message: DefaultMessage):
        command = BroadcastMessageCommand(message.model_dump_json())
        self.provider.send_communication_command(command)