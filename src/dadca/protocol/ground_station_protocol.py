import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.constant import Agent, Message
from src.dadca.message.ground_station_message import GroundStationMessage
from src.dadca.message.information_message import InformationMessage
from src.dadca.message.default_message import Sender, DefaultMessage
from src.dadca.message.welcome_message import WelcomeMessage
from src.dadca.object.packet import Packet


class GroundStationProtocol(IProtocol):
    _log: logging.Logger
    packets: set[Packet]
    lamport_clock: int

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self.lamport_clock = 0
        self.packets = set()

    def handle_timer(self, timer: str) -> None:
        pass

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.label == Message.WELCOME:
            message = WelcomeMessage.model_validate_json(message)
            self.lamport_clock += 1

            response = self._build_ground_station_message()
            command = SendMessageCommand(response.model_dump_json(), message.sender.id)
            self.provider.send_communication_command(command)

        elif default_message.label == Message.INFORMATION:
            message = InformationMessage.model_validate_json(message)
            self.packets.update(message.packets)

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        self._log.info(f"Number of packets received: {len(self.packets)}")

    def _build_ground_station_message(self) -> GroundStationMessage:
        return GroundStationMessage.model_construct(
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.GROUND_STATION,
                id=self.provider.get_id()
            )
        )