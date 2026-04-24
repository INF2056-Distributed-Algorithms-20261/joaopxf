from pydantic import BaseModel

from src.dadca.constant import Agent, Message


class Sender(BaseModel):
    agent: Agent
    id: int

class DefaultMessage(BaseModel):
    lamport_clock: int
    sender: Sender
    label: Message = Message.DEFAULT


