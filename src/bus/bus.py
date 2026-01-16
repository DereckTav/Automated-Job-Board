import asyncio
from abc import ABC, abstractmethod
from typing import Any


class Bus(ABC):

    def __init__(self):
        self.queue = asyncio.Queue()

    # todo will be changed once I look at integrations

    @abstractmethod
    async def listen(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def notify(self, event: dict[str, Any]) -> None:
        pass