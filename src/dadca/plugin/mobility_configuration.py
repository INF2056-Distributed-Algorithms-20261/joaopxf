from dataclasses import dataclass


@dataclass
class MobilityConfiguration:
    speed: float = 4
    distance_tolerance: float = 0.5