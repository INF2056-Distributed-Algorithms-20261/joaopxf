from dataclasses import dataclass


@dataclass
class MobilityConfiguration:
    speed: float = 4
    tolerance: float = 0.5