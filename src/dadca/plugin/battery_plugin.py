import logging
import math

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher
from gradysim.protocol.position import squared_distance, Position

from src.dadca.config import ENERGY_STATION_POSITION, NUMBER_UVAS, AERIAL_ENERGY_STATION_POSITION, DIAMETER
from src.dadca.constant import Timer
from src.dadca.plugin.battery_configuration import BatteryConfiguration
from src.geometry.point import Point
from src.geometry.vector import Vector


class BatteryPlugin:
    def __init__(self, protocol: IProtocol, configuration: BatteryConfiguration):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._configuration = configuration
        self._logger = logging.getLogger()

        self.disable_heartbeat: bool = False
        self.is_critical: bool = False
        self.battery: float = 100

        self._critical_battery_position: Point | None = None
        self._previous_position: Position | None = None
        self._waiting_position: Position | None = None

        self._at_energy_station_waiting_area: bool = False
        self._at_energy_station: bool = False

        self._initialize_telemetry_handling()

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> None:
            current_position = telemetry.current_position

            if self._previous_position:
                self._monitory_battery_loss(current_position)

            if self.is_critical:
                if not self._at_energy_station_waiting_area:
                    self._monitory_energy_station_waiting_area(current_position)

                if not self._at_energy_station:
                    self._monitory_energy_station(current_position)

            else:
                if self._critical_battery_position:
                    self._monitory_return(current_position)

            self._previous_position = current_position

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def _compute_battery_cost(self, current_position: Position, target_position: Position) -> float:
        distance = squared_distance(current_position, target_position) ** 0.5
        battery_cost = distance * self._configuration.discharge_per_meter_rate

        return battery_cost

    def _monitory_battery_loss(self, current_position: Position):
        battery_cost = self._compute_battery_cost(self._previous_position, current_position)
        self.battery -= battery_cost

        if (
            self.is_critical is False
            and self._has_reached_critical_battery(current_position)
        ):
            self.is_critical = True
            self._critical_battery_position = Point(*current_position)
            self._logger.info("Critical battery has been reached. Agent is moving to Energy Station")

            self._instance.provider.schedule_timer(
                Timer.INTERRUPT_MISSION.value,
                self._instance.provider.current_time()
            )

    def _monitory_energy_station_waiting_area(self, current_position: Position):
        if (
            self._waiting_position
            and squared_distance(current_position, self._waiting_position)
                <= self._configuration.distance_tolerance ** 2
        ):
            self._at_energy_station_waiting_area = True
            self._instance.provider.schedule_timer(
                Timer.REQUEST_ENERGY_STATION.value,
                self._instance.provider.current_time()
            )

    def _monitory_energy_station(self, current_position: Position):
        if (
            squared_distance(current_position, ENERGY_STATION_POSITION)
            <= self._configuration.distance_tolerance ** 2
        ):
            self._at_energy_station = True
            self.recharge_battery()

    def _monitory_return(self, current_position: Position):
        if (
            squared_distance(current_position, self._critical_battery_position)
            <= self._configuration.distance_tolerance ** 2
        ):
            self.disable_heartbeat = False
            self._at_energy_station_waiting_area = False
            self._at_energy_station = False

    def move_to_critical_battery_position(self):
        mobility_command = GotoCoordsMobilityCommand(*self._critical_battery_position)
        self._instance.provider.send_mobility_command(mobility_command)

    def move_to_energy_station_waiting_area(self, uav_register: int):
        direction = Vector(1, 0, 0)
        angle = 2 * math.pi * uav_register/NUMBER_UVAS
        self._waiting_position = AERIAL_ENERGY_STATION_POSITION + direction.rotate(angle).normalize() * (DIAMETER / 2)

        mobility_command = GotoCoordsMobilityCommand(*self._waiting_position)
        self._instance.provider.send_mobility_command(mobility_command)

    def move_to_energy_station(self):
        mobility_command = GotoCoordsMobilityCommand(*ENERGY_STATION_POSITION)
        self._instance.provider.send_mobility_command(mobility_command)

    def _has_reached_critical_battery(self, current_position: Position) -> bool:
        """
        Check if battery station is reacheable

        """
        battery_cost = self._compute_battery_cost(current_position, ENERGY_STATION_POSITION)

        return self.battery <= battery_cost + self._configuration.battery_tolerance

    def recharge_battery(self):
        if self.battery < 100:
            self._instance.provider.schedule_timer(
                Timer.RECHARGE_BATTERY.value,
                self._instance.provider.current_time() + 1
            )

            self.battery += self._configuration.charge_per_time_rate

        else:
            self.battery = 100
            self.is_critical = False

            self._logger.info("Battery fully charged. Agent is returning to mission")
            self._instance.provider.schedule_timer(
                Timer.RETURN_MISSION.value,
                self._instance.provider.current_time() + 1
            )

