from abc import abstractmethod, ABC
from src.core.parser.components.fetchers.components.robots.robots_rules import RobotsRules
from typing import Optional, List

class RobotsCache(ABC):
    """
    Abstraction for caching robots.txt rules.
    """

    @abstractmethod
    def has(self, url: str) -> bool:
        """Check if URL is cached"""
        pass

    @abstractmethod
    def get(self, url: str) -> Optional[RobotsRules]:
        """Get cached rules for URL"""
        pass

    @abstractmethod
    def set(self, url: str, rules: RobotsRules) -> None:
        """Cache rules for URL"""
        pass

    @abstractmethod
    def remove(self, url: str) -> None:
        """Remove URL from cache"""
        pass

    @abstractmethod
    def get_all_urls(self) -> List[str]:
        """Get all cached URLs"""
        pass

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

