import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.dadca.config import PACKET_SPAWN, PACKET_DROP
from src.dadca.message.information_message import InformationMessage
from src.dadca.message.default_message import Sender, DefaultMessage

from src.dadca.constant import Agent, Message, SensorOperation
from src.dadca.message.welcome_message import WelcomeMessage
from src.dadca.object.packet import Packet


class SensorProtocol(IProtocol):
    _log: logging.Logger
    packets: dict[int, Packet]
    lost_packets: int
    generated_packets: int
    lamport_clock: int
    drop_count: int

    def initialize(self) -> None:
        self._log = logging.getLogger()
        self.packets = {}
        self.lost_packets = 0
        self.generated_packets = 0
        self.lamport_clock = 0
        self.drop_count = 0
        self._generate_packet()

    def handle_timer(self, timer: str) -> None:
        if timer == SensorOperation.GENERATE_PACKAGE.value:
            self._generate_packet()

        elif timer == SensorOperation.DROP_PACKAGE.value:
            self.drop_count += 1
            try:
                self.packets.pop(self.drop_count)
                self.lost_packets += 1
            except KeyError:
                pass

    def handle_packet(self, message: str) -> None:
        default_message = DefaultMessage.model_validate_json(message)
        self._update_clock_on_receive(default_message.lamport_clock)

        if default_message.label == Message.WELCOME:
            message = WelcomeMessage.model_validate_json(message)
            self.lamport_clock += 1

            response = self._build_information_message()
            command = SendMessageCommand(response.model_dump_json(), message.sender.id)
            self.provider.send_communication_command(command)
            self.packets.clear()

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        self._log.info(
            f"Number of packets generated: {self.generated_packets}"
            f" and number of packets lost: {self.lost_packets}"
        )

    def _generate_packet(self) -> None:
        self.generated_packets += 1
        self.packets[self.generated_packets] = Packet()
        self.provider.schedule_timer(
            SensorOperation.GENERATE_PACKAGE.value,
            self.provider.current_time() + PACKET_SPAWN
        )
        self.provider.schedule_timer(
            SensorOperation.DROP_PACKAGE.value,
            self.provider.current_time() + PACKET_DROP
        )

    def _update_clock_on_receive(self, lamport_clock: int) -> None:
        new_lamport_cock = max(self.lamport_clock, lamport_clock) + 1
        self.lamport_clock = new_lamport_cock

    def _build_information_message(self) -> InformationMessage:
        return InformationMessage.model_construct(
            packets=self._get_packet_set(),
            lamport_clock=self.lamport_clock,
            sender=Sender.model_construct(
                agent=Agent.SENSOR,
                id=self.provider.get_id()
            )
        )

    def _get_packet_set(self) -> set[Packet]:
        packets = set()
        for packet in self.packets.values():
            packets.add(packet)

        return packets
