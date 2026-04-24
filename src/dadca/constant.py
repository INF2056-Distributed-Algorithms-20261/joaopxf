from enum import Enum, auto


class Agent(Enum):
    ENERGY_STATION = auto()
    GROUND_STATION = auto()
    SENSOR = auto()
    UAV = auto()

class Message(Enum):
    ACKNOWLEDGEMENT = auto()
    DEFAULT = auto()
    ENERGY_STATION = auto()
    ENTRY_CRITICAL_SECTION = auto()
    PACKET = auto()

class Movement(Enum):
    FORWARD = 1
    BACKWARD = -1

class OperationStage(Enum):
    DATA_COLLECTION = "DATA_COLLECTION"      # Movement along the pathline to collect data from sensors
    RECHARGE = "RECHARGE"
    MISSION_START = "MISSION_START"          # Initial flight from the ground station to the starting point of the pathline
    WAIT_FOR_RECHARGE = "WAIT_FOR_RECHARGE"
