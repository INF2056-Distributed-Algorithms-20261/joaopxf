import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.constant import Agent
from src.dadca.domain.package_message import PacketMessage
from src.dadca.domain.uav_message import UAVMessage
from src.dadca.domain.default_message import Sender, DefaultMessage


class GroundStationProtocol(IProtocol):
    _log: logging.Logger
    packet_count: int
    lamport_clock: int

    def initialize(self) -> None:
        self._log = logging.getLogger()

        self.packet_count = 0
        self.lamport_clock = 0

    def handle_timer(self, timer: str) -> None:
        pass

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.sender.agent == Agent.UAV:
            self.lamport_clock += 1
            message = UAVMessage.model_validate_json(message)
            response = PacketMessage.model_construct(
                packet_count=self.packet_count,
                lamport_clock=self.lamport_clock,
                sender=Sender.model_construct(
                    agent=Agent.GROUND_STATION,
                    id=self.provider.get_id()
                ),
            )
            command = SendMessageCommand(response.model_dump_json(), message.sender.id)
            self.provider.send_communication_command(command)

            self.packet_count += message.packet_count

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass