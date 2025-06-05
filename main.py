from physics.body import Body
from physics.environment import Environment
from physics.simulator import Simulator


def main():
    print("2D Projectile Motion Simulator with Air Resistance\n")

    # Create simulation objects
    env = Environment(gravity=9.81, air_density=1.225)
    projectile = Body(mass=0.145, area=0.0042, drag_coeff=0.47,
                      initial_position=(0, 0),
                      initial_velocity=(30, 30))  # m/s

    simulator = Simulator(env, projectile)
    simulator.run(total_time=5.0, dt=0.01)
    simulator.plot()

if __name__ == "__main__":
    main()
