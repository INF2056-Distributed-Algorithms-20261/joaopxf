from src.dadca.message.default_message import DefaultMessage


class UAVMessage(DefaultMessage):
    packet_count: int
    entry_score: float | None