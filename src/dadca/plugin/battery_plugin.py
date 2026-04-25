import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher
from gradysim.protocol.position import squared_distance, Position

from src.dadca.config import ENERGY_STATION_POSITION
from src.dadca.plugin.battery_configuration import BatteryConfiguration


class BatteryPlugin:
    def __init__(self, protocol: IProtocol, configuration: BatteryConfiguration):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._configuration = configuration
        self._logger = logging.getLogger()
        self._previous_position = None

        self.battery: float = 100

        self._initialize_telemetry_handling()

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> None:
            current_position = telemetry.current_position

            if self._previous_position:
                battery_cost = self._compute_battery_cost(self._previous_position, current_position)
                self.battery -= battery_cost

            self._previous_position = current_position

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def _compute_battery_cost(self, current_position: Position, target_position: Position) -> float:
        distance = squared_distance(current_position, target_position) ** 0.5
        battery_cost = distance * self._configuration.discharge_per_meter_rate

        return battery_cost

    def has_reached_critical_battery(self, current_position: Position) -> bool:
        """
        Check if battery station is reacheable

        """
        battery_cost = self._compute_battery_cost(current_position, ENERGY_STATION_POSITION)

        return self.battery <= battery_cost + self._configuration.battery_tolerance

    def recharge_battery(self):
        if self.battery < 100:
            self.battery += self._configuration.charge_per_time_rate

        if self.battery > 100:
            self.battery = 100
            # self._logger.info("Battery fully charged. Agent is returning to mission")


