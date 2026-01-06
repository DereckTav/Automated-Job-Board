import asyncio
from abc import ABC, abstractmethod
from urllib.robotparser import RobotFileParser

from src.core.parser.components.fetchers.components.robots.robots_rules import RobotsRules
from src.core.parser.components.fetchers.components.robots.cache import RobotsCache

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

class RobotsTxtParser(RobotsParser):
    """
    Parses robots.txt files and caches results.
    """

    def __init__(self, cache: RobotsCache):
        self.cache = cache

    async def get_rules(self, url: str, base_url: str, user_agent: str) -> RobotsRules:
        """
        Get robots.txt rules for a URL.

        1. Check cache first
        2. If not cached, fetch and parse robots.txt
        3. Cache the result
        4. Return rules
        """
        try:
            # Check cache first
            if self.cache.has(url):
                return self.cache.get(url)

            # Parse robots.txt
            rules = await self._parse_robots_txt(url, base_url, user_agent)

            # Cache if allowed
            if rules.can_fetch:
                self.cache.set(url, rules)

            return rules

        except Exception:
            # Default to conservative rules on error
            return RobotsRules(
                can_fetch=False,
                crawl_delay=1.0,
                user_agent=user_agent
            )

    async def _parse_robots_txt(self, url: str, base_url: str, user_agent: str) -> RobotsRules:
        """
        Parse robots.txt file.
        """
        loop = asyncio.get_running_loop()

        robot_parser = RobotFileParser()
        robot_parser.set_url(url)

        await loop.run_in_executor(None, robot_parser.read)

        can_fetch = await loop.run_in_executor(None, robot_parser.can_fetch, user_agent, url)

        crawl_delay = robot_parser.crawl_delay(user_agent) or 1.0

        return RobotsRules(
            can_fetch=can_fetch,
            crawl_delay=float(crawl_delay),
            user_agent=user_agent
        )