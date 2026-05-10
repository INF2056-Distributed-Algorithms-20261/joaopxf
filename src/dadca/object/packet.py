from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Packet(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Packet):
            return NotImplemented

        return self.uuid == other.uuid

    def __hash__(self) -> int:
        return hash(self.uuid)