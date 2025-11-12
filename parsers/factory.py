from typing import List

from parsers.base_parser import ParserDependencies
from interfaces.content import ContentFetcher
from parsers.parser_types import DownloadParser, StaticContentParser, JavaScriptContentParser, SeleniumDownloadParser
from processing.data_processor import ChangeDetectionProcessor, NameRegularizationProcessor, PositionNormalizationProcessor, \
    DateFilterProcessor, IgnoreDataWithFlagProcessor, ColumnRegularizationProcessor
from processing.fetchers import HttpContentFetcher, SeleniumContentFetcher, DownloadFetcher, AirtableSeleniumFetcher
from interfaces.data import DataProcessor
from processing.pipeline import ProcessingPipeline
from robots.cache import InMemoryRobotsCache
from robots.parser import RobotsTxtParser
from robots.refresher import RobotsCacheRefresher

from logs import logger as log

class ParserFactory:
    """
    Creates parsers with proper dependencies.
    """

    def __init__(self, session, browser_manager, tracker, user_agent_provider, enable_robots_refresh=None):
        self.session = session
        self.browser_manager = browser_manager
        self.tracker = tracker
        self.ua_provider = user_agent_provider

        self.robots_cache = InMemoryRobotsCache()
        self.robots_parser = RobotsTxtParser(self.robots_cache)

        # Optionally start background refresh
        self.robots_refresher = None

        if enable_robots_refresh:
            self.robots_refresher = RobotsCacheRefresher(
                self.robots_parser,
                self.robots_cache,
                refresh_interval_hours=24
            )
            self.robots_refresher.start()
            self.robots_refresher.set_global_instance(self.robots_refresher) # for auto clean up

    def create_download_parser(self, processors: List[DataProcessor] = None) -> DownloadParser:
        """
        Create a download parser with specified processors.

        Example usage:
            # Standard configuration
            parser = factory.create_download_parser()

            # Custom configuration with extra processor
            parser = factory.create_download_parser([
                DateFilterProcessor(),
                PositionNormalizationProcessor(),
                CustomEmailProcessor(include_parsers=['DOWNLOAD_PARSER'])
            ])
        """
        log.info("Creating download parser")
        fetcher = DownloadFetcher(self.session, self.ua_provider)

        if processors is None:
            # Default processors for download parser
            processors = [
                ColumnRegularizationProcessor(),
                DateFilterProcessor(),
                IgnoreDataWithFlagProcessor(),
                PositionNormalizationProcessor(),
                NameRegularizationProcessor(),
                ChangeDetectionProcessor(self.tracker)
            ]

        pipeline = ProcessingPipeline(processors)
        deps = ParserDependencies(fetcher, pipeline, self.tracker)

        return DownloadParser(deps)

    def create_static_parser(self, processors: List[DataProcessor] = None) -> StaticContentParser:
        """Create static parser with specified processors"""
        log.info("Creating static parser")
        fetcher = HttpContentFetcher(self.session, self.ua_provider, self.robots_parser)

        if processors is None:
            processors = [
                DateFilterProcessor(),
                IgnoreDataWithFlagProcessor(),
                PositionNormalizationProcessor(),
                NameRegularizationProcessor(),
                ChangeDetectionProcessor(self.tracker)
            ]

        pipeline = ProcessingPipeline(processors)
        deps = ParserDependencies(fetcher, pipeline, self.tracker)

        return StaticContentParser(deps)

    def create_js_parser(self, processors: List[DataProcessor] = None) -> JavaScriptContentParser:
        """Create JS parser with specified processors"""
        log.info("Creating JS parser")
        fetcher = SeleniumContentFetcher(self.browser_manager, self.ua_provider, self.robots_parser)

        if processors is None:
            processors = [
                DateFilterProcessor(),
                IgnoreDataWithFlagProcessor(),
                PositionNormalizationProcessor(),
                NameRegularizationProcessor(),
                ChangeDetectionProcessor(self.tracker)
            ]

        pipeline = ProcessingPipeline(processors)
        deps = ParserDependencies(fetcher, pipeline, self.tracker)

        return JavaScriptContentParser(deps)

    def create_selenium_download_parser(
            self,
            fetcher: ContentFetcher = None,
            processors: List[DataProcessor] = None
    ) -> SeleniumDownloadParser:
        """
        Create Airtable Selenium download parser.

        This parser uses Selenium to click UI buttons and download CSV files
        from Airtable, then processes them like DownloadParser.
        """
        # Create Airtable-specific fetcher
        log.info("Creating Selenium download parser")
        if fetcher is None:
            fetcher = AirtableSeleniumFetcher(self.browser_manager)

        if processors is None:
            processors = [
                ColumnRegularizationProcessor(),
                DateFilterProcessor(),
                IgnoreDataWithFlagProcessor(),
                PositionNormalizationProcessor(),
                NameRegularizationProcessor(),
                ChangeDetectionProcessor(self.tracker)
            ]

        pipeline = ProcessingPipeline(processors)
        deps = ParserDependencies(fetcher, pipeline, self.tracker)

        return SeleniumDownloadParser(deps)