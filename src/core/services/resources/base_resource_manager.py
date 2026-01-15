import tempfile
import time
from typing import Optional

import aiohttp

from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager
from src.core.services.resources.core.resource_management import ResourceManager

class BaseResourceManager(ResourceManager):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def get_session(self, **kwargs):
        return await self._stack.enter_async_context(aiohttp.ClientSession())

    async def get_browser_manager(self,
        headless: bool = True,
        max_browser_instances: int = 2,
        use_download_dir: Optional[bool] = False,
        **kwargs
    ) -> BrowserManager:
        download_dir = None
        if use_download_dir:
            download_dir = await self._loop.run_in_executor(None, lambda: tempfile.mkdtemp(
                prefix=f'downloads_{int(time.time() * 1000)}'
            )) # type: ignore

        return await self._stack.enter_async_context(BrowserManager(
            headless=headless,
            max_browser_instances=max_browser_instances,
            download_dir=download_dir
        ))