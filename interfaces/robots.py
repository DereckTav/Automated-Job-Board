from abc import abstractmethod, ABC
from typing import Optional, List

from robots.output import RobotsRules

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


class RobotsParser(ABC):
    """
    Abstraction for robots.txt parsing.
    """

    @abstractmethod
    async def get_rules(self, url: str, base_url: str, user_agent: str) -> RobotsRules:
        """Get robots.txt rules for a URL"""
        pass

    @abstractmethod
    async def _parse_robots_txt(self, url: str, base_url: str, user_agent: str) -> RobotsRules:
        """Parse robots.txt file"""
        pass
