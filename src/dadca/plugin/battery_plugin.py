import logging
from typing import Callable

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher
from gradysim.protocol.position import squared_distance, Position

from src.dadca.config import ENERGY_STATION_POSITION
from src.dadca.constant import Timer
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.geometry.point import Point


class BatteryPlugin:
    def __init__(self, protocol: IProtocol, configuration: BatteryConfiguration):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._configuration = configuration
        self._logger = logging.getLogger()

        self._previous_position: Position | None = None
        self.critical_battery_position: Point | None = None
        self.is_critical = False
        self.battery: float = 100

        self._initialize_telemetry_handling()

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> None:
            current_position = telemetry.current_position

            if self._previous_position is not None:
                battery_cost = self._compute_battery_cost(self._previous_position, current_position)
                self.battery -= battery_cost

                if (
                    self.is_critical is False
                    and self.has_reached_critical_battery(current_position)
                ):
                    self.is_critical = True
                    self.critical_battery_position = Point(*current_position)
                    self._logger.info("Critical battery has been reached. Agent is moving to Energy Station")

                    self._instance.provider.schedule_timer(
                        Timer.BATTERY.value,
                        self._instance.provider.current_time()
                    )

            self._previous_position = current_position

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def has_reached_critical_battery(self, current_position: Position) -> bool:
        """
        Check if battery station is reacheable

        """
        battery_cost = self._compute_battery_cost(current_position, ENERGY_STATION_POSITION)

        return self.battery <= battery_cost + self._configuration.battery_tolerance

    def _compute_battery_cost(self, current_position: Position, target_position: Position) -> float:
        distance = squared_distance(current_position, target_position) ** 0.5
        battery_cost = distance * self._configuration.discharge_per_meter_rate

        return battery_cost

    def recharge_battery(self):
        if self.battery < 100:
            self._instance.provider.schedule_timer(
                Timer.BATTERY.value,
                self._instance.provider.current_time() + 1
            )

            self.battery += self._configuration.charge_per_time_rate

        else:
            self.battery = 100
            self.is_critical = False

            self._logger.info("Battery fully charged. Agent is returning to mission")

