from src.dadca.constant import Message, Movement
from src.dadca.message.default_message import DefaultMessage


class InformationMessage(DefaultMessage):
    direction: Movement | None = None
    last_waypoint: int | None = None
    battery_map: dict[int, float] | None = None
    packet_count: int
    label: Message = Message.INFORMATION