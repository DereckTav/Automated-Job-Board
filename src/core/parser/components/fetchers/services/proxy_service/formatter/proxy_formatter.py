from abc import ABC, abstractmethod
from typing import Any

class ProxyFormatter(ABC):

    @abstractmethod
    def apply_format(self, proxies: str | list[str]) -> Any:
        pass

class BasicProxyFormatter(ProxyFormatter):
    def apply_format(self, proxies: str | list[str]) -> str | list[str]:
        return proxies

class SeleniumWireProxyFormatter(ProxyFormatter):
    def apply_format(self, proxies: str | list[str]) -> dict[str, str] | list[dict[str, str]]:

        def _build_dict(url: str) -> dict[str, Any]:
            return {
                    'http': f"http://{url}",
                    'https': f"https:/{url}"
            }

        if isinstance(proxies, list):
            return [_build_dict(proxy) for proxy in proxies]

        return _build_dict(proxies)