from src.dadca.constant import Message
from src.dadca.message.default_message import DefaultMessage


class WelcomeMessage(DefaultMessage):
    label: Message = Message.WELCOME