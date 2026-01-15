from typing import Optional

from src.core.logs import APP, Logger
from src.core.parser.components.fetchers.components.robots.cache import (
    InMemoryRobotsCache,
    RobotsCache,
)
from src.core.parser.components.fetchers.components.robots.parser import (
    RobotsParser,
    RobotsTxtParser,
)
from src.core.parser.components.fetchers.components.robots.refreshers import (
    RobotsCacheRefresher,
)
from src.core.parser.components.fetchers.fetcher_builder import FetcherBuilder
from src.core.parser.components.pipelines.data_processing.data_processor import DataProcessor
from src.core.parser.components.pipelines.data_processing.data_processors import (
    ChangeDetectionProcessor,
    DateFilterProcessor,
    FiltersProcessor,
    PositionNormalizationProcessor,
)
from src.core.parser.components.pipelines.data_processing.trackers.tracker import (
	ChangeTracker,
    Tracker,
)
from src.core.parser.components.pipelines.pipeline import ProcessingPipeline
from src.core.parser.core.base_parser import ParserDependencies
from src.core.parser.core.parser_types import (
	DownloadParser,
	StaticContentParser,
	JavaScriptContentParser,
	SeleniumDownloadParser,
)
from src.core.services.resources.base_resource_manager import BaseResourceManager
from src.core.services.resources.core.resource_management import ResourceManager

LOGGER = Logger(APP)

"""
    Include acts as a whitelist.
    Exclude acts as a blacklist.

    Whitelist has priority over blacklist:
    - If there is a whitelist, the blacklist is essentially nonexistent.
    - If a parser is in both, the whitelist is prioritized.

    Fallback Logic:
    - If whitelist is empty or is None, anything will be accepted as long as it's not in the blacklist.

    Meaning that:
    - By allowing what you want in the whitelist, everything else is blocked.
    - By blocking what you want in the blacklist, everything else passes as long as long as there is NO WHITELIST.
"""

# put parser names example: 'DownloadParser'
CHANGE_DETECTION_PROCESSOR = {
    "include_parsers": [],
    "exclude_parsers": [],
}

DATE_FILTER_PROCESSOR = {
    "include_parsers": [],
    "exclude_parsers": [],
}

FILTERS_PROCESSOR = {
    "include_parsers": [],
    "exclude_parsers": [],
}

POSITION_NORMALIZATION_PROCESSOR = {
    "include_parsers": [],
    "exclude_parsers": [],
}

class ParserBuilder:
    """
    Creates parser with proper dependencies.
    """

    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        robots_cache: Optional[RobotsCache] = None,
        robots_parser: Optional[RobotsParser] = None,
        processors: Optional[list[DataProcessor]] = None,
        tracker: Optional[ChangeTracker] = None,
        enable_robots_refresh: bool = False
    ):
        if resource_manager is None:
            self.resource_manager = BaseResourceManager()

        if robots_cache is None:
            self.robots_cache = InMemoryRobotsCache()

        if robots_parser is None:
            self.robots_parser = RobotsTxtParser(self.robots_cache)

        self.fetcher_builder = FetcherBuilder(
            resource_management=self.resource_manager,
            robots_cache=self.robots_cache
        )

        # Optionally start background refresh
        self.robots_refresher = None
        if enable_robots_refresh:
            self.robots_refresher = RobotsCacheRefresher(
                self.robots_parser,
                self.robots_cache,
                refresh_interval_hours=168 # week
            )

        if tracker is None:
            self.tracker = Tracker()

        if processors is None:
            self.processors = self._build_default_processors()

        self.pipeline = ProcessingPipeline(self.processors)

    def _build_default_processors(self):
        """
        Factory method to construct the standard pipeline.
        This is the ONLY place you need to touch to add a new default step.
        """
        return [
            ChangeDetectionProcessor(
                self.tracker,
                include_parsers=CHANGE_DETECTION_PROCESSOR["include_parsers"],
                exclude_parsers=CHANGE_DETECTION_PROCESSOR["exclude_parsers"]
            ),

            DateFilterProcessor(
                include_parsers=DATE_FILTER_PROCESSOR["include_parsers"],
                exclude_parsers=DATE_FILTER_PROCESSOR["exclude_parsers"],
            ),

            FiltersProcessor(
                include_parsers=FILTERS_PROCESSOR["include_parsers"],
                exclude_parsers=FILTERS_PROCESSOR["exclude_parsers"],
            ),

            PositionNormalizationProcessor(
                include_parsers=POSITION_NORMALIZATION_PROCESSOR["include_parsers"],
                exclude_parsers=POSITION_NORMALIZATION_PROCESSOR["exclude_parsers"],
            ),
        ]

    async def __aenter__(self):
        if self.robots_refresher:
            await self.robots_refresher.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.robots_refresher:
            await self.robots_refresher.__aexit__(exc_type, exc_val, exc_tb)

    def build_download_parser(self) -> DownloadParser:
        LOGGER.info('(PARSER_BUILDER) building download_parser')
        download_fetcher = self.fetcher_builder.build_download_content_fetcher()

        deps = ParserDependencies(download_fetcher, self.pipeline)

        return DownloadParser(deps)

    def create_static_parser(self) -> StaticContentParser:
        LOGGER.info('(PARSER_BUILDER) building static_parser')
        html_fetcher = self.fetcher_builder.build_http_content_fetcher()

        deps = ParserDependencies(html_fetcher, self.pipeline)

        return StaticContentParser(deps)

    def create_js_parser(self) -> JavaScriptContentParser:
        LOGGER.info('(PARSER_BUILDER) building JavaScript_parser')
        selenium_fetcher = self.fetcher_builder.build_selenium_content_fetcher()

        deps = ParserDependencies(selenium_fetcher, self.pipeline)

        return JavaScriptContentParser(deps)

    def create_airtable_download_parser(self) -> SeleniumDownloadParser:
        LOGGER.info('(PARSER_BUILDER) building airtable_download_parser')

        airtable_fetcher = self.fetcher_builder.build_airtable_selenium_content_fetcher()

        deps = ParserDependencies(airtable_fetcher, self.pipeline)

        return SeleniumDownloadParser(deps)
