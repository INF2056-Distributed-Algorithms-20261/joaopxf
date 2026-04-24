import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.constant import Agent, Message
from src.dadca.message.default_message import Sender, DefaultMessage
from src.dadca.message.energy_station_message import EnergyStationMessage


class EnergyStationProtocol(IProtocol):
    _log: logging.Logger
    lamport_clock: int
    number_uavs: int
    group: int
    _newer_group: bool

    def initialize(self) -> None:
        self.lamport_clock = 0
        self.number_uavs = 0
        self.group = 1
        self._log = logging.getLogger()
        self._newer_group = True

    def handle_timer(self, timer: str) -> None:
        self._log.info(f"There are {self.number_uavs} UAVs in the group")
        message = self._build_energy_station_message()
        self._broadcast(message)

        self.group += 1
        self.number_uavs = 0
        self._newer_group = True

    def handle_packet(self, message: str) -> None:
        message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(message.lamport_clock)

        if message.label == Message.DEFAULT:
            self.number_uavs += 1
            if self._newer_group:
                self._newer_group = False
                self.provider.schedule_timer(
                    "",
                    self.provider.current_time() + 100
                )

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass

    def _build_energy_station_message(self) -> EnergyStationMessage:
        return EnergyStationMessage.model_construct(
            lamport_clock=self.lamport_clock,
            group=self.group,
            number_uavs=self.number_uavs,
            sender=Sender.model_construct(
                agent=Agent.ENERGY_STATION,
                id=self.provider.get_id()
            ),
        )

    def _broadcast(self, message: DefaultMessage):
        command = BroadcastMessageCommand(message.model_dump_json())
        self.provider.send_communication_command(command)