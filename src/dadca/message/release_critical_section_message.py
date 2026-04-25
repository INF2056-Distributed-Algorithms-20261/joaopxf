from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class ReleaseCriticalSectionMessage(DefaultMessage):
    label: Message = Message.RELEASE_CRITICAL_SECTION