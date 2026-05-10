import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher
from gradysim.protocol.position import squared_distance, Position

from src.dadca.config import ENERGY_STATION_POSITION
from src.dadca.plugin.battery_configuration import BatteryConfiguration


class BatteryPlugin:
    def __init__(
        self, protocol: IProtocol,
        configuration: BatteryConfiguration,
        initial_battery: float,
    ):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._configuration = configuration
        self._logger = logging.getLogger()
        self._previous_position = None
        self._id = self._instance.provider.get_id()

        self.battery_map: dict[int, float] = {self._id: initial_battery}

        self._initialize_telemetry_handling()

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> None:
            current_position = telemetry.current_position

            if self._previous_position:
                battery_cost = self._compute_battery_cost(self._previous_position, current_position)
                for _id, battery in self.battery_map.items():
                    self.battery_map[_id] -= battery_cost

            self._previous_position = current_position

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def _compute_battery_cost(self, current_position: Position, target_position: Position) -> float:
        distance = squared_distance(current_position, target_position) ** 0.5
        battery_cost = distance * self._configuration.discharge_per_meter_rate

        return battery_cost

    def get_battery(self) -> float:
        return self.battery_map[self._id]

    def reset_battery_map(self):
        self.battery_map = {self._id: self.get_battery()}

    def has_reached_critical_battery(self, current_position: Position) -> bool:
        """
        Check if battery station is reacheable

        """
        battery = self.get_battery()
        battery_cost = self._compute_battery_cost(current_position, ENERGY_STATION_POSITION)

        return battery <= battery_cost + self._configuration.battery_tolerance

    def recharge_battery(self):
        battery = self.get_battery()

        if battery < 100:
            self.battery_map[self._id] += self._configuration.charge_per_time_rate

        if battery > 100:
            self.battery_map[self._id] = 100
            # self._logger.info("Battery fully charged. Agent is returning to mission")


