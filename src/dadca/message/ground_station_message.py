from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class GroundStationMessage(DefaultMessage):
    label: Message = Message.GROUND_STATION