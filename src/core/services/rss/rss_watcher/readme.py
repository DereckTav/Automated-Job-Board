import asyncio
from typing import Callable, Awaitable

import aiohttp

from src.core.logs import Logger, APP
from src.core.services.rss.rss_watcher.watcher import Watcher

LOGGER = Logger(APP)

class ReadmeFeedWatcher(Watcher):

    def __init__(self, session: aiohttp.ClientSession, feed_url: str,  poll_interval=300, ) -> None:
        self.session = session

        self.feed_url = feed_url
        self.poll_interval = poll_interval
        self.last_seen_sha = None

    async def poll(self, callback: Callable[[], Awaitable[None]]) -> None:
        while True:
            try:
                entries = await self.fetch_data(self.feed_url)

                if entries:
                    newest_sha_in_batch = entries[0].get('id')

                    for entry in entries:
                        sha = entry.get('id')
                        title = entry.get('title', '')

                        if sha == self.last_seen_sha:
                            break

                        if "README" in title.upper():
                            await callback()
                            break

                    if newest_sha_in_batch:
                        self.last_seen_sha = newest_sha_in_batch

            except Exception as e:
                LOGGER.error(f"(RSS_README_WATCHER) Error polling feed: {e}")

            await asyncio.sleep(self.poll_interval)

    async def fetch_data(self, url: str) -> list[dict]:
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()