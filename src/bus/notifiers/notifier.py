from abc import ABC, abstractmethod

class Notifier(ABC):

    @abstractmethod
    async def listen(self) -> None:
        pass

    @abstractmethod
    async def notify(self) -> None:
        pass