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
    NUMBER_NODES_CRITICAL_SECTION = auto()
    PACKET = auto()
    PRIORITY_CRITICAL_SECTION = auto()
    RELEASE_CRITICAL_SECTION = auto()

class Movement(Enum):
    FORWARD = 1
    BACKWARD = -1

class UAVOperation(Enum):
    DATA_COLLECTION = "DATA_COLLECTION"      # Movement along the pathline to collect data from sensors
    RECHARGE = "RECHARGE"
    MISSION_START = "MISSION_START"          # Initial flight from the ground station to the starting point of the pathline
    MISSION_RETURN = "MISSION_RETURN"
    WAIT_FOR_RECHARGE = "WAIT_FOR_RECHARGE"

class EnergyStationOperation(Enum):
    CHANGE_GROUP = "CHANGE_GROUP"
