class Body:
    def __init__(self, mass, area, drag_coeff, initial_position, initial_velocity):
        self.mass = mass
        self.area = area
        self.drag_coeff = drag_coeff
        self.position = list(initial_position)
        self.velocity = list(initial_velocity)
        self.positions = [list(initial_position)]

    def update_position(self, dt):
        self.position[0] += self.velocity[0] * dt
        self.position[1] += self.velocity[1] * dt
        self.positions.append(list(self.position))
