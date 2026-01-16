from abc import ABC, abstractmethod
from typing import Callable, Any, Awaitable


class Watcher(ABC):

    @abstractmethod
    async def poll(self, callback: Callable[[], Awaitable[None]]) -> None:
        pass