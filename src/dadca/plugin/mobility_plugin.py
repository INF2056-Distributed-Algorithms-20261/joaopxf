import logging
from typing import Optional

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.mobility import SetSpeedMobilityCommand, GotoCoordsMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.plugin.dispatcher import create_dispatcher, DispatchReturn
from gradysim.protocol.position import Position, squared_distance

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
        self._mission: Optional[list[Position]] = None

        self.on_mission: bool = False
        self.ready_to_rendesvouz: Optional[bool] = None
        self.current_waypoint: Optional[int] = None
        self.current_direction: Optional[Movement] = None

    def _initialize_telemetry_handling(self):
        def telemetry_handler(_instance: IProtocol, telemetry: Telemetry) -> DispatchReturn | None:
            if (
                self.current_waypoint is not None
                and self.has_reached_target(telemetry.current_position)
            ):
                self.on_mission = True
                self._progress_current_waypoint()
                self.travel_to_current_waypoint()

        self._dispatcher.register_handle_telemetry(telemetry_handler)

    def has_reached_target(self, current_position, target_position = None) -> bool:
        if target_position is None:
            target_position = self._mission[self.current_waypoint]

        return squared_distance(current_position, target_position) <= self._configuration.tolerance ** 2

    def _progress_current_waypoint(self) -> None:
        if (
            self.current_waypoint == len(self._mission) - 1
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

        mobility_command = GotoCoordsMobilityCommand(*self._mission[self.current_waypoint])
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
        self._mission = path
        self.current_waypoint = initial_waypoint
        self.current_direction = direction
        self.ready_to_rendesvouz = True

        self.travel_to_current_waypoint()

        speed_command = SetSpeedMobilityCommand(self._configuration.speed)
        self._instance.provider.send_mobility_command(speed_command)

        self._logger.info("Mission: Starting mission")

