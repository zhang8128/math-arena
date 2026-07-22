from abc import ABC, abstractmethod
from collections.abc import Iterator

from mathloop.domain import ProblemCandidate


class ProblemSource(ABC):
    @abstractmethod
    def read(self) -> Iterator[ProblemCandidate]:
        """Yield immutable problem candidates from this source."""
