from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class AcknowledgementMessage(DefaultMessage):
    entry_critical_section: bool = True
    label: Message = Message.ACKNOWLEDGEMENT