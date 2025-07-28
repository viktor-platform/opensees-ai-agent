from math import sqrt
from app.types import Vec3

# Vector helpers
def v_sub(a: Vec3, b: Vec3) -> Vec3:
    """a - b"""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_cross(a: Vec3, b: Vec3) -> Vec3:
    """a × b"""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def v_norm(a: Vec3) -> float:
    """‖a‖₂"""
    return sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
