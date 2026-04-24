from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class EnergyStationMessage(DefaultMessage):
    number_uavs: int
    label: Message = Message.ENERGY_STATION