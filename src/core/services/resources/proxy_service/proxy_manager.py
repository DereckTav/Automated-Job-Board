from __future__ import annotations

import asyncio
import tempfile
import time
from typing import TYPE_CHECKING, Optional

import aiohttp

from src.core.parser.components.fetchers.components.session.aioproxy import AioProxy
from src.core.services.resources.proxy_service.formatter.proxy_formatter import BasicProxyFormatter, \
    SeleniumWireProxyFormatter
from src.core.services.resources.core.base_resource_management import BaseResourceManager

if TYPE_CHECKING:
    from src.core.services.resources.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.components.browser.proxy_browser_manager import ProxyBrowserManager

class ProxyManager(BaseResourceManager):

    def __init__(self, proxy_pool: list[str], **kwargs):
        super().__init__(**kwargs)
        self._proxy_pool = proxy_pool
        self._index = 0

        self._session: Optional[AioProxy] = None
        self._proxy_browser_manager: Optional[ProxyBrowserManager] = None

        self._session_lock = asyncio.Lock()
        self._pbm_lock = asyncio.Lock()

    def _get_next_raw_proxy(self) -> str:
        if not self._proxy_pool:
            raise ValueError("Proxy pool is empty.")

        proxy = self._proxy_pool[self._index]
        # Increment index and wrap around if at the end (Round Robin)
        self._index = (self._index + 1) % len(self._proxy_pool)
        return proxy

    async def request_new_proxy(self, proxy_obj: Proxy, **kwargs):
        required_type = proxy_obj.type_required()

        if isinstance(required_type, list):
            new_proxies = [self._get_next_raw_proxy() for _ in range(proxy_obj.number_of_proxies_needed())]
        else:
            new_proxies = self._get_next_raw_proxy()

        await proxy_obj.change_proxy(new_proxies, **kwargs)

    async def get_session(self, **kwargs) -> aiohttp.ClientSession:
        if self._session:
            return self._session

        async with self._session_lock:
            if self._session:
                return self._session

            proxy = self._get_next_raw_proxy()
            self._session = await self._stack.enter_async_context(AioProxy(
                proxy=proxy,
                proxy_manager=self,
                proxy_formatter=BasicProxyFormatter()
            ))

            return self._session

    async def get_browser_manager(self,
        headless: bool = True,
        max_browser_instances: int = 2,
        use_download_dir: Optional[bool] = False,
        **kwargs
    ) -> ProxyBrowserManager:
        if self._proxy_browser_manager:
            return self._proxy_browser_manager

        async with self._pbm_lock:
            if self._proxy_browser_manager:
                return self._proxy_browser_manager

            from src.core.parser.components.fetchers.components.browser.proxy_browser_manager import ProxyBrowserManager

            download_dir = None
            if use_download_dir:
                download_dir = await self._loop.run_in_executor(None, lambda: tempfile.mkdtemp(
                    prefix=f'downloads_{int(time.time() * 1000)}'
                )) # type: ignore

            self._proxy_browser_manager = await self._stack.enter_async_context(ProxyBrowserManager(
                proxy_manager=self,
                proxy_formatter=SeleniumWireProxyFormatter(),
                headless=headless,
                max_browser_instances=max_browser_instances,
                download_dir=download_dir
            ))

            new_proxies = [self._get_next_raw_proxy() for _ in range(max_browser_instances)]
            await self._proxy_browser_manager.configure_proxies(new_proxies)

            return self._proxy_browser_manager