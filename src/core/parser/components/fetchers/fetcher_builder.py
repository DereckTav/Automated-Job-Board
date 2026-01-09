import asyncio

from src.core.parser.components.fetchers.components.robots.cache import RobotsCache
from src.core.parser.components.fetchers.components.robots.parser import RobotsTxtParser
from src.core.parser.components.fetchers.core.builder import Builder
from src.core.parser.components.fetchers.core.fetcher_types import HttpContentFetcher, SeleniumContentFetcher, \
    DownloadContentFetcher, AirtableSeleniumContentFetcher
from src.core.parser.components.fetchers.services.resource_management import ResourceManager


class FetcherBuilder(Builder):
    def __init__(self, resource_management: ResourceManager, robots_cache: RobotsCache, **kwargs):
        super().__init__(resource_management, **kwargs)
        self._robots_parser = RobotsTxtParser(robots_cache)
        self._semaphore = asyncio.Semaphore()

        self._browser_manager = None
        self._session = None

        self._setup = False

    async def setup(self):
        if self._setup:
            return

        async with self._semaphore:
            if self._setup:
                return

            self._browser_manager = await self.resource_management.get_browser_manager()
            self._session =  await self.resource_management.get_session()

            self._setup = True

    async def build_http_content_fetcher(self):
        if not self._setup:
            await self.setup()

        return HttpContentFetcher(
            self._session,
            self.resource_management.get_random_user_agent(),
            self._robots_parser
        )

    async def build_selenium_content_fetcher(self):
        if not self._setup:
            await self.setup()

        return SeleniumContentFetcher(
            self._browser_manager,
            self.resource_management.get_random_user_agent(),
            self._robots_parser
        )

    async def build_download_content_fetcher(self):
        if not self._setup:
            await self.setup()

        return DownloadContentFetcher(
            self._session,
            self.resource_management.get_random_user_agent()
        )

    async def build_airtable_selenium_content_fetcher(self):
        if not self._setup:
            await self.setup()

        return AirtableSeleniumContentFetcher(
            self._browser_manager
        )