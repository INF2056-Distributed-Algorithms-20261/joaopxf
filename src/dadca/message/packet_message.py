from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class PacketMessage(DefaultMessage):
    packet_count: int
    label: Message = Message.PACKET