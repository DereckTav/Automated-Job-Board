import tempfile
import time
from typing import Optional

import aiohttp

from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager
from src.core.services.resources.core.base_resource_management import BaseResourceManager
import asyncio

class ResourceManager(BaseResourceManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session: Optional[aiohttp.ClientSession] = None
        self._browser_manager: Optional[BrowserManager] = None

        self._session_lock = asyncio.Lock()
        self._browser_lock = asyncio.Lock()

    async def get_session(self, **kwargs):
        if self._session:
            return self._session

        async with self._session_lock:
            if self._session:
                return self._session

            self._session = await self._stack.enter_async_context(aiohttp.ClientSession())
            return self._session

    async def get_browser_manager(self,
        headless: bool = True,
        max_browser_instances: int = 2,
        use_download_dir: Optional[bool] = False,
        **kwargs
    ) -> BrowserManager:
        if self._browser_manager:
            return self._browser_manager

        async with self._browser_lock:
            if self._browser_manager:
                return self._browser_manager

            download_dir = None
            if use_download_dir:
                download_dir = await self._loop.run_in_executor(None, lambda: tempfile.mkdtemp(
                    prefix=f'downloads_{int(time.time() * 1000)}'
                ))

            self._browser_manager = await self._stack.enter_async_context(BrowserManager(
                headless=headless,
                max_browser_instances=max_browser_instances,
                download_dir=download_dir
            ))

            return self._browser_manager