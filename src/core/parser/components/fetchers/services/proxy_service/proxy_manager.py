from __future__ import annotations

import asyncio
import tempfile
import time
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Optional

from src.core.logs import Logger
from src.core.parser.components.fetchers.services.resource_management import ResourceManager

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.components.browser.proxy_browser_manager import ProxyBrowserManager

LOGGER = Logger('app')

class ProxyManager(ResourceManager):

    def __init__(self):
        self._stack = AsyncExitStack()
        self._loop = asyncio.get_event_loop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._stack.aclose()

    async def request_new_proxy(self, proxy_obj: Proxy, **kwargs):
        required_type = proxy_obj.type_required()

        if isinstance(required_type, list):
            new_proxies = []
        else:
            new_proxies = ""

        await proxy_obj.change_proxy(new_proxies, **kwargs)

    async def get_session(self):
        pass #TODO finish

    async def get_browser_manager(self,
        headless: bool = True,
        max_browser_instances: int = 2,
        use_download_dir: Optional[bool] = False
    ):
        download_dir = None
        if use_download_dir:
            download_dir = await self._loop.run_in_executor(None, lambda: tempfile.mkdtemp(
                prefix=f'downloads_{int(time.time() * 1000)}'
            )) # type: ignore

        pbm = await self._stack.enter_async_context(ProxyBrowserManager(
            proxy_manager=self,
            headless=headless,
            max_browser_instances=max_browser_instances,
            download_dir=download_dir
        ))

        #TODO finish implementing algorithms

        await pbm.configure_proxies()