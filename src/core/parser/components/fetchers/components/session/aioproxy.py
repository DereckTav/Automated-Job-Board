from __future__ import annotations
from typing import Any, Union, List, TYPE_CHECKING
import aiohttp
from aiohttp.typedefs import StrOrURL
from aiohttp.client import _RequestContextManager

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.services.proxy_service.proxy_manager import ProxyManager

class AioProxy(aiohttp.ClientSession, Proxy):

    def __init__(self, proxy: str, proxy_manager: ProxyManager):
        super().__init__(proxy_manager=proxy_manager)
        self.proxy = proxy

    def _request(
            self,
            method: str,
            str_or_url: StrOrURL,
            **kwargs: Any
    ) -> _RequestContextManager:

        kwargs.setdefault("proxy", self.proxy)

        self._request_new_proxy()

        return _RequestContextManager(
            super()._request(method, str_or_url, **kwargs)
        )

    def type_required(self) -> type[str | list]:
        return str

    async def change_proxy(self, proxies: Union[str, List[str]], **kwargs: Any) -> None:
        if isinstance(proxies, list):
            raise # TODO comeback to this
        else:
            self.proxy = proxies