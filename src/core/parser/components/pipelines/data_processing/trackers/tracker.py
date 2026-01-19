from abc import ABC, abstractmethod
from typing import Optional

'''
tracks most recent seen job
'''

class ChangeTracker(ABC):
    """
    Abstraction for tracking content changes.
    """

    @abstractmethod
    def has(self, key: str) -> bool:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def track(self, key: str, hash_value: str) -> None:
        pass

class Tracker(ChangeTracker):
    def __init__(self):
        self._tracker = {}

    def has(self, key: str) -> bool:
        return key in self._tracker

    def get(self, key: str) -> Optional[str]:
        if self.has(key):
            return self._tracker[key]

        return None

    def track(self, key: str, hash_value: str) -> None:
        self._tracker[key] = hash_value
