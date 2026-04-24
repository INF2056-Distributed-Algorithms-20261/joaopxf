import math

from geometry.point import Point
from geometry.vector import Vector
from src.dadca.config import NUMBER_UVAS, AERIAL_ENERGY_STATION_POSITION, DIAMETER


DIRECTION = Vector(1,0,0)


def get_waiting_position(order: int) -> Point:
    angle = 2 * math.pi * order / NUMBER_UVAS
    waiting_position = (
        AERIAL_ENERGY_STATION_POSITION + DIRECTION.rotate(angle).normalize() * (DIAMETER / 2)
    )

    return waiting_position