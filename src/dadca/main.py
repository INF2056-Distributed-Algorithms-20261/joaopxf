from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler, VisualizationConfiguration
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.dadca.protocol.energy_station_protocol import EnergyStationProtocol
from src.dadca.protocol.ground_station_protocol import GroundStationProtocol
from src.dadca.protocol.sensor_protocol import SensorProtocol
from src.dadca.protocol.uav_protocol import UAVProtocol


def main():
    config = SimulationConfiguration(
        duration=10000
    )
    builder = SimulationBuilder(config)

    # Instantiating 7 sensors in fixed positions
    builder.add_node(SensorProtocol, (50, 0, 0))
    builder.add_node(SensorProtocol, (100, 0, 0))
    builder.add_node(SensorProtocol, (150, 0, 0))
    builder.add_node(SensorProtocol, (250, 0, 0))
    builder.add_node(SensorProtocol, (300, 0, 0))
    builder.add_node(SensorProtocol, (350, 0, 0))
    builder.add_node(SensorProtocol, (450, 0, 0))

    # Instantiating 3 UAVs
    builder.add_node(UAVProtocol, (0, 0, 0))
    builder.add_node(UAVProtocol, (0, 0, 0))
    builder.add_node(UAVProtocol, (0, 0, 0))
    builder.add_node(UAVProtocol, (0, 0, 0))
    builder.add_node(UAVProtocol, (0, 0, 0))

    # Instantiating ground station at (0,0,0)
    builder.add_node(GroundStationProtocol, (0, 0, 0))

    # Instantiating energy station
    builder.add_node(EnergyStationProtocol, (225, 389.71, 0))

    # Adding required handlers
    builder.add_handler(TimerHandler())
    builder.add_handler(CommunicationHandler(CommunicationMedium(
        transmission_range=20
    )))
    builder.add_handler(MobilityHandler())
    builder.add_handler(VisualizationHandler(VisualizationConfiguration(
        x_range=(-1000, 1000),
        y_range=(-500, 500),
        z_range=(0, 150),
        update_rate=0.05
    )))

    # Building & starting
    simulation = builder.build()
    simulation.start_simulation()


if __name__ == "__main__":
    main()
