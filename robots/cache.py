from interfaces.robots import RobotsCache
from output import RobotsRules
from typing import Optional, List

class InMemoryRobotsCache(RobotsCache):
    def __init__(self):
        self._cache: dict[str, RobotsRules] = {}

    def has(self, url: str) -> bool:
        return url in self._cache

    def get(self, url: str) -> Optional[RobotsRules]:
        return self._cache.get(url)

    def set(self, url: str, rules: RobotsRules) -> None:
        self._cache[url] = rules

    def remove(self, url: str) -> None:
        self._cache.pop(url, None)

    def get_all_urls(self) -> List[str]:
        return list(self._cache.keys())