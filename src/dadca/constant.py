from enum import Enum, auto


class Agent(Enum):
    ENERGY_STATION = auto()
    GROUND_STATION = auto()
    SENSOR = auto()
    UAV = auto()


class Timer(Enum):
    CLEAR_RENDEZVOUS = "CLEAR_RENDEZVOUS"
    CRITICAL_SECTION = "CRITICAL_SECTION"
    HEARTBEAT = "HEARTBEAT"
    RECHARGE_BATTERY = "RECHARGE_BATTERY"
    REQUEST_ENERGY_STATION = "REQUEST_ENERGY_STATION"
    START_MISSION = "START_MISSION"


class Movement(Enum):
    FORWARD = 1
    BACKWARD = -1


class CriticalSectionStatus(Enum):
    RELEASED = auto()
    WANTED = auto()
    HELD = auto()
