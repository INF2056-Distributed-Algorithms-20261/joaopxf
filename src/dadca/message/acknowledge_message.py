from src.dadca.message.default_message import DefaultMessage


class AcknowledgeMessage(DefaultMessage):
    swap_direction: bool = False
