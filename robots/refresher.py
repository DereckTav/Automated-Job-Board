import asyncio
import atexit
from typing import Optional
from urllib.parse import urlparse

from interfaces.robots import RobotsParser, RobotsCache


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

    @classmethod
    def set_global_instance(cls, instance):
        """Set the global manager instance for cleanup."""
        global _refresh_instance
        _refresh_instance = instance


    async def _refresh_loop(self):
        """
        Background task that periodically refreshes cached rules.
        """
        try:
            while True:
                await asyncio.sleep(self.refresh_interval)
                await self._refresh_cache()

        except asyncio.CancelledError:
            import logs.logger as log
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
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # Get fresh rules (won't use cache since we're validating)
            rules = await self.parser._parse_robots_txt(url, base_url, user_agent)

            return rules.can_fetch

        except Exception:
            return False

_refresh_instance = None

async def cleanup():
    """Cleanup on shutdown"""
    if _refresh_instance:
        await _refresh_instance.stop()

        try:
            await _refresh_instance._task
        except asyncio.CancelledError:
            pass


def shutdown_handler():
    """Handle shutdown gracefully"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

atexit.register(shutdown_handler)