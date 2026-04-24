from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class EntryCriticalSectionMessage(DefaultMessage):
    priority: float
    label: Message = Message.ENTRY_CRITICAL_SECTION