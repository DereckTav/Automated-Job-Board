"""
A class representing an object that is meant to automatically change its own proxy after every request
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from src.core.parser.components.fetchers.services.proxy_service.formatter.proxy_formatter import ProxyFormatter

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy_manager import ProxyManager

class Proxy(ABC):
    def __init__(self, proxy_manager: ProxyManager, proxy_formatter: ProxyFormatter):
        self.proxy_manager = proxy_manager
        self.proxy_formatter = proxy_formatter

    @abstractmethod
    def type_required(self) -> type[str | list]:
        pass

    async def _request_new_proxy(self, **kwargs) -> None:
        await self.proxy_manager.request_new_proxy(self, **kwargs)

    @abstractmethod
    async def change_proxy(self, proxies: str | list[str], **kwargs: Any) -> None:
        """
        replaces resource and attached resources with a different proxy.
        """
        pass
