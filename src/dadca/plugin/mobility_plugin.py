import logging

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.mobility import SetSpeedMobilityCommand, GotoCoordsMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher, DispatchReturn
from gradysim.protocol.position import Position, squared_distance
from typing_extensions import NamedTuple

from src.dadca.constant import Movement
from src.dadca.plugin.mobility_configuration import MobilityConfiguration


class MobilityPlugin:
    def __init__(
        self,
        protocol: IProtocol,
        configuration: MobilityConfiguration,
    ):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._configuration = configuration
        self._logger = logging.getLogger()
        self._initialize_telemetry_handling()

        self._path: list[Position] | None = None

        self.initial_position: NamedTuple | None = None
        self.current_waypoint: int | None = None
        self.current_direction: Movement | None = None

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> DispatchReturn | None:
            if (
                self.current_waypoint is not None
                and self.has_reached_target(telemetry.current_position)
            ):
                self._progress_current_waypoint()
                self.travel_to_current_waypoint()

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def has_reached_target(self, current_position, target_position = None) -> bool:
        if target_position is None:
            target_position = self._path[self.current_waypoint]

        return squared_distance(current_position, target_position) <= self._configuration.distance_tolerance ** 2

    def _progress_current_waypoint(self) -> None:
        if (
            self.current_waypoint == len(self._path) - 1
            or self.current_waypoint == 0
        ):
            self.reverse_direction()

        self.change_current_waypoint()

    def reverse_direction(self) -> None:
        if self.current_direction == Movement.FORWARD:
            self.current_direction = Movement.BACKWARD

        else:
            self.current_direction = Movement.FORWARD

    def change_current_waypoint(self) -> None:
        self.current_waypoint += self.current_direction.value

    def travel_to_current_waypoint(self) -> None:
        if self.current_waypoint is None:
            return

        mobility_command = GotoCoordsMobilityCommand(*self._path[self.current_waypoint])
        self._instance.provider.send_mobility_command(mobility_command)

    def start_mission(
        self,
        initial_waypoint: int,
        path: list[Position],
        direction: Movement = Movement.FORWARD,
    ) -> None:
        """
        Send the UAVs to the initial position to start collecting data from the sensors.

        """
        self._path = path

        self.current_waypoint = initial_waypoint
        self.current_direction = direction
        self.initial_position = path[initial_waypoint]

        self.travel_to_current_waypoint()

        speed_command = SetSpeedMobilityCommand(self._configuration.speed)
        self._instance.provider.send_mobility_command(speed_command)

        self._logger.info("Mission: Starting mission")

    def move_to_position(self, position: NamedTuple) -> None:
        mobility_command = GotoCoordsMobilityCommand(*position)
        self._instance.provider.send_mobility_command(mobility_command)



