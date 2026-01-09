import asyncio
from typing import Optional

from src.core.parser.components.fetchers.components.robots.cache import RobotsCache
from src.core.parser.components.fetchers.components.robots.parser import RobotsParser


class RobotsCacheRefresher:
    """
    Periodically refreshes cached robots.txt rules.
    """

    def __init__(self,
                 parser: RobotsParser,
                 cache: RobotsCache,
                 refresh_interval_hours: int = 24):
        self.parser = parser
        self.cache = cache
        self.refresh_interval = refresh_interval_hours * 60 * 60  # Convert to seconds
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background refresh task"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._refresh_loop())

    def stop(self):
        """Stop the background refresh task"""
        if self._task and not self._task.done():
            self._task.cancel()

    async def _refresh_loop(self):
        """
        Background task that periodically refreshes cached rules.
        """
        try:
            while True:
                await asyncio.sleep(self.refresh_interval)
                await self._refresh_cache()

        except asyncio.CancelledError:
            import src.core.logs as log
            log.info("robots cache refresher stopped")
            raise

    async def _refresh_cache(self):
        """
        Check all cached URLs and remove invalid ones.
        """
        urls_to_check = self.cache.get_all_urls()
        urls_to_remove = []

        for url in urls_to_check:
            cached_rules = self.cache.get(url)
            if cached_rules is None:
                continue

            # Re-check if URL is still fetchable
            is_valid = await self._validate_url(url, cached_rules.user_agent)

            if not is_valid:
                urls_to_remove.append(url)

            await asyncio.sleep(0)  # Yield to event loop

        # Remove invalid URLs
        for url in urls_to_remove:
            self.cache.remove(url)

    async def _validate_url(self, url: str, user_agent: str) -> bool:
        """
        Check if a URL is still fetchable according to robots.txt.
        """
        try:
            # Get fresh rules (won't use cache since we're validating)
            rules = await self.parser.parse_robots_txt(url, user_agent)

            return rules.can_fetch

        except Exception:
            return False