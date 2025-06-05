import math
import utils.py

import matplotlib.pyplot as plt  # type: ignore


class Simulator:
    def __init__(self, environment, body):
        self.env = environment
        self.body = body

    def compute_drag(self, velocity):
        v_mag = math.hypot(*velocity)
        drag_mag = 0.5 * self.env.air_density * v_mag**2 * self.body.drag_coeff * self.body.area
        drag_x = -drag_mag * (velocity[0] / v_mag) if v_mag != 0 else 0
        drag_y = -drag_mag * (velocity[1] / v_mag) if v_mag != 0 else 0
        return (drag_x, drag_y)

    def run(self, total_time, dt):
        steps = int(total_time / dt)
        for _ in range(steps):
            drag_fx, drag_fy = self.compute_drag(self.body.velocity)

            ax = drag_fx / self.body.mass
            ay = (drag_fy / self.body.mass) - self.env.gravity

            self.body.velocity[0] += ax * dt
            self.body.velocity[1] += ay * dt

            self.body.update_position(dt)

            if self.body.position[1] <= 0:
                break

    def plot(self):
        x_vals, y_vals = zip(*self.body.positions)
        plt.figure(figsize=(8, 4))
        plt.plot(x_vals, y_vals)
        plt.title("Projectile Motion with Air Resistance")
        plt.xlabel("X Position (m)")
        plt.ylabel("Y Position (m)")
        plt.grid(True)
        plt.show()
