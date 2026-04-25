import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand

from gradysim.protocol.plugin.dispatcher import create_dispatcher

from src.dadca.config import ENERGY_STATION_ID
from src.dadca.message.acknowledgement_message import AcknowledgementMessage
from src.dadca.message.number_nodes_critical_section_message import NumberNodesCriticalSectionMessage
from src.dadca.message.priority_critical_section_message import PriorityCriticalSectionMessage
from src.dadca.message.release_critical_section_message import ReleaseCriticalSectionMessage


class MutualExclusionPlugin:
    def __init__(
        self,
        protocol: IProtocol,
    ):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._logger = logging.getLogger()

        self.priority: float = 0
        self.neighbors: list[int] = []
        self.waiter_nodes: list[int] = []
        self.acknowledgements: list[int] = []

    def send_message_to_central_station(
        self,
        message: NumberNodesCriticalSectionMessage | ReleaseCriticalSectionMessage
    ):
        command = SendMessageCommand(message.model_dump_json(), ENERGY_STATION_ID)
        self._instance.provider.send_communication_command(command)

    def set_neighbors(self, group: list[int]):
        neighbors = set(group) - {self._instance.provider.get_id()}
        self.neighbors = list(neighbors)

    def send_message_to_nodes(self, message: PriorityCriticalSectionMessage):
        for _id in self.neighbors:
            command = SendMessageCommand(message.model_dump_json(), _id)
            self._instance.provider.send_communication_command(command)

    def reply_node(self, message: AcknowledgementMessage, _id: int):
        command = SendMessageCommand(message.model_dump_json(), _id)
        self._instance.provider.send_communication_command(command)

    def notify_waiter_nodes(self, message: AcknowledgementMessage):
        for waiter_node in self.waiter_nodes:
            command = SendMessageCommand(message.model_dump_json(), waiter_node)
            self._instance.provider.send_communication_command(command)

    def compare_priority(self, priority: float, _id: int) -> bool:
        if self.priority > priority:
            return True
        elif self.priority < priority:
            return False
        else:
            return self._instance.provider.get_id() < _id

    def check_all_acknowledgements(self) -> bool:
        return (
            len(self.acknowledgements) == len(self.neighbors)
            or len(self.neighbors) == 0
        )

    def reset(self):
        self.neighbors = []
        self.waiter_nodes = []
        self.acknowledgements = []
