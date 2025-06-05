import math

def magnitude(vector):
    return math.hypot(*vector)

def normalize(vector):
    mag = magnitude(vector)
    if mag == 0:
        return (0, 0)
    return (vector[0] / mag, vector[1] / mag)

def scale(vector, scalar):
    return (vector[0] * scalar, vector[1] * scalar)
