import logging

from gradysim.protocol.interface import IProtocol

from gradysim.protocol.plugin.dispatcher import create_dispatcher
from src.dadca.constant import CriticalSectionStatus


class MutualExclusionPlugin:
    def __init__(
        self,
        protocol: IProtocol,
    ):
        self._dispatcher = create_dispatcher(protocol)
        self._instance = protocol
        self._logger = logging.getLogger()

        self.number_uavs: int | None = None
        self.entry_score: int | None = None
        self.repliers: set[int] = set()
        self.critical_section_status: CriticalSectionStatus = CriticalSectionStatus.RELEASED

    def evaluate_entry_score(self, lamport_clock: int, battery: float):
        self.entry_score = 0.5 / lamport_clock + 0.5 / battery

    def compare_entry_score(self, entry_score: float, _id: int) -> bool:
        if self.entry_score < entry_score:
            return True
        elif self.entry_score > entry_score:
            return False
        else:
            return self._instance.provider.get_id() < _id

    def check_all_replies(self) -> bool:
        return len(self.repliers) == self.number_uavs - 1
