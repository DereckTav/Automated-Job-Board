from abc import abstractmethod, ABC
from typing import Optional

class ChangeTracker(ABC):
    """
    Abstraction for tracking content changes.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def track(self, key: str, value: str) -> None:
        pass
