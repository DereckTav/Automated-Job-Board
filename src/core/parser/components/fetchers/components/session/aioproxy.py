from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
import aiohttp
from aiohttp.typedefs import StrOrURL
from aiohttp.client import _RequestContextManager

from src.core.parser.components.fetchers.services.proxy_service.exceptions.Invalid_number_of_proxies import InvalidNumberOfProxies
from src.core.parser.components.fetchers.services.proxy_service.formatter.proxy_formatter import BasicProxyFormatter

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.services.proxy_service.proxy_manager import ProxyManager

class AioProxy(aiohttp.ClientSession, Proxy):

    def __init__(self, proxy: str, proxy_manager: ProxyManager, proxy_formatter: BasicProxyFormatter):
        super().__init__(proxy_manager=proxy_manager, proxy_formatter=proxy_formatter)
        self.semaphore = asyncio.Semaphore()
        self.proxy = proxy

    async def _request(
            self,
            method: str,
            str_or_url: StrOrURL,
            **kwargs: Any
    ) -> _RequestContextManager:

        kwargs.setdefault("proxy", self.proxy)

        await self._request_new_proxy()

        return _RequestContextManager(
            super()._request(method, str_or_url, **kwargs)
        )

    def type_required(self) -> type[str | list]:
        return str

    async def change_proxy(self, proxies: str | list[str], **kwargs: Any) -> None:
        async with self.semaphore:
            if isinstance(proxies, list):
                raise InvalidNumberOfProxies("Invalid number of proxies")
            else:
                self.proxy = self.proxy_formatter.apply_format(proxies)