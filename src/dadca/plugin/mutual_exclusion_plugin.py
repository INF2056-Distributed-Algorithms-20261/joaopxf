import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand

from gradysim.protocol.plugin.dispatcher import create_dispatcher

from src.dadca.config import ENERGY_STATION_ID
from src.dadca.message.acknowledgement_message import AcknowledgementMessage
from src.dadca.message.default_message import DefaultMessage


class MutualExclusionPlugin:
    def __init__(
        self,
        protocol: IProtocol,
    ):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._logger = logging.getLogger()

        self.priority: float = 0
        self.number_nodes: int  = 0
        self.waiter_nodes: list[int] = []
        self.acknowledgements: list[int] = []

    def ask_number_nodes_to_reply(self, message: DefaultMessage):
        command = SendMessageCommand(message.model_dump_json(), ENERGY_STATION_ID)
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
            len(self.acknowledgements) == self.number_nodes - 1
            or self.number_nodes == 1
        )
