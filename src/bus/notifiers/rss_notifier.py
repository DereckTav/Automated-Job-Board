"""
designed for only one-to-one communication
"""
import asyncio

from src.bus.notifiers.notifier import Notifier

class RSSNotifier(Notifier):

    def __init__(self):
        self.event = asyncio.Event()

    async def listen(self) -> None:
        await self.event.wait()
        self.event.clear()

    async def notify(self) -> None:
        self.event.set()