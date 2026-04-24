from typing import NamedTuple
from geometry.vector import Vector


class Point(NamedTuple):
    x: float
    y: float
    z: float

    def __key(self):
        return self.x, self.y, self.z

    def __eq__(self, point: "Point"):
        if not isinstance(point, Point):
            return False

        return self.__key() == point.__key()

    def __hash__(self):
        return hash(self.__key())

    def __add__(self, vector: Vector) -> "Point":
        if not isinstance(vector, Vector):
            raise TypeError("Operando deve ser da classe Vetor")

        x = self.x + vector.x
        y = self.y + vector.y
        z = self.z + vector.z

        return Point(x, y, z)

    def __sub__(self, point: "Point") -> Vector:
        if not isinstance(point, Point):
            raise TypeError("Operando deve ser da classe Ponto")

        x = self.x - point.x
        y = self.y - point.y
        z = self.z - point.z

        return Vector(x, y, z)

