from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class InformationMessage(DefaultMessage):
    battery: float | None = None
    packet_count: int
    label: Message = Message.INFORMATION