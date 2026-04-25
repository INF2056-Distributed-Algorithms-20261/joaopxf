from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class NumberNodesCriticalSectionMessage(DefaultMessage):
    label: Message = Message.NUMBER_NODES_CRITICAL_SECTION