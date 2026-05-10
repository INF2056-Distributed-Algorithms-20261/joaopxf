from src.dadca.constant import Message, Movement
from src.dadca.message.default_message import DefaultMessage
from src.dadca.object.packet import Packet


class InformationMessage(DefaultMessage):
    direction: Movement | None = None
    last_waypoint: int | None = None
    battery_map: dict[int, float] | None = None
    packets: set[Packet]
    label: Message = Message.INFORMATION