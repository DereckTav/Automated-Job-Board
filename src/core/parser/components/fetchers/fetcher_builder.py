from src.core.parser.components.fetchers.components.robots.parser import RobotsParser
from src.core.parser.components.fetchers.core.builder import Builder
from src.core.parser.components.fetchers.core.fetcher_types import (
    HttpContentFetcher, SeleniumContentFetcher, DownloadContentFetcher, AirtableSeleniumContentFetcher
)
from src.core.services.resources.core.resource_management import ResourceManager


class FetcherBuilder(Builder):
    def __init__(self, resource_management: ResourceManager, robots_parser: RobotsParser, browser_manager=None, session=None, **kwargs):
        super().__init__(resource_management, **kwargs)
        self._robots_parser = robots_parser
        self._browser_manager = browser_manager
        self._session = session

    @classmethod
    async def create(cls, resource_management: ResourceManager, robots_parser: RobotsParser, **kwargs):
        """
        Async Factory: Creates and initializes resources BEFORE instantiating the class.
        """

        browser_manager = await resource_management.get_browser_manager()
        session = await resource_management.get_session()

        return cls(
            resource_management=resource_management,
            robots_parser=robots_parser,
            browser_manager=browser_manager,
            session=session,
            **kwargs
        )

    def build_http_content_fetcher(self):
        return HttpContentFetcher(
            self._session,
            self.resource_management.get_random_user_agent(),
            self._robots_parser
        )

    def build_selenium_content_fetcher(self):
        return SeleniumContentFetcher(
            self._browser_manager,
            self.resource_management.get_random_user_agent(),
            self._robots_parser
        )

    def build_download_content_fetcher(self):
        return DownloadContentFetcher(
            self._session,
            self.resource_management.get_random_user_agent()
        )

    def build_airtable_selenium_content_fetcher(self):
        return AirtableSeleniumContentFetcher(
            self._browser_manager
        )
