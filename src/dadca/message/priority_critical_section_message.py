from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class PriorityCriticalSectionMessage(DefaultMessage):
    priority: float
    label: Message = Message.PRIORITY_CRITICAL_SECTION