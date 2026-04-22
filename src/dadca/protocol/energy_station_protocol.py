import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.constant import Agent
from src.dadca.domain.default_message import Sender, DefaultMessage
from src.dadca.domain.energy_station_message import EnergyStationMessage


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
        self._broadcast()

        self.group += 1
        self.number_uavs = 0
        self._newer_group = True

    def handle_packet(self, default_message: str) -> None:
        default_message = DefaultMessage.model_validate_json(default_message)
        self._update_clock_on_receive(default_message.lamport_clock)
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

    def _broadcast(self):
        response = EnergyStationMessage.model_construct(
            lamport_clock=0,
            priority=self.group,
            number_uavs=self.number_uavs,
            sender=Sender.model_construct(
                agent=Agent.ENERGY_STATION,
                id=self.provider.get_id()
            ),
        )
        command = BroadcastMessageCommand(response.model_dump_json())
        self.provider.send_communication_command(command)

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass