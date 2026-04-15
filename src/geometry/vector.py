import math


class Vector:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def __key(self):
        return self.x, self.y, self.z

    def __eq__(self, vector: "Vector"):
        return self.__key() == vector.__key()

    def __hash__(self):
        return hash(self.__key())

    def __mul__(self, scalar: float) -> "Vector":
        match scalar:
            case float():
                return self.__compute_scalar_product(scalar)

            case _:
                raise TypeError("Somente produto escalar está implementado")

    def __compute_scalar_product(self, scalar: float) -> "Vector":
        x = scalar * self.x
        y = scalar * self.y
        z = scalar * self.z

        return Vector(x, y, z)

    def rotate(self, angle: float) -> "Vector":
        x = math.cos(angle) * self.x - math.sin(angle) * self.y
        y = math.sin(angle) * self.x + math.cos(angle) * self.y

        return Vector(x, y, self.z)

    def compute_euclidean_norm(self) -> float:
        p_norm_2 = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

        return p_norm_2

    def compute_inner_product(self, vector: "Vector") -> float:
        inner_product = (
            self.x * vector.x +
            self.y * vector.y +
            self.z * vector.z
        )

        return inner_product

    def compute_vectorial_product(self, vector: "Vector") -> "Vector":
        x = self.y * vector.z - self.z * vector.y
        y = self.z * vector.x - self.x * vector.z
        z = self.x * vector.y - self.y * vector.x

        return Vector(x, y, z)

    def normalize(self) -> "Vector":
        factor= 1/(self.compute_euclidean_norm())
        unit_vector = self * factor

        return unit_vector
