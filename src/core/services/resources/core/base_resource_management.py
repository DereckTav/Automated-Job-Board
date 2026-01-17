'''
outputs resources like sessions
or browserManagers
'''
import asyncio
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack

import aiohttp
from fake_useragent import UserAgent

from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager

class BaseResourceManager(ABC):

    def __init__(self, **kwargs):
        """manages resources required by application.

            examples: browsers or aiohttp.ClientSession
        """
        self._loop = asyncio.get_event_loop()
        self._stack = AsyncExitStack()
        self.ua = UserAgent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._stack.aclose()

    @abstractmethod
    async def get_session(self, **kwargs) -> aiohttp.ClientSession:
        pass

    @abstractmethod
    async def get_browser_manager(self, **kwargs) -> BrowserManager:
        pass

    def get_random_user_agent(self) -> str:
        return self.ua.random
