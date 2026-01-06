from dataclasses import dataclass

from src.models.results import Result
from src.core.parser.components.pipelines.Interfacetracker import ChangeTracker
from src.core.parser.components.fetchers.core.fetcher import ContentFetcher
from src.core.parser.components.pipelines.pipeline import ProcessingPipeline

from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod


@dataclass
class ParserDependencies:
    """
    Container for dependencies.
    """
    fetcher: ContentFetcher
    pipeline: ProcessingPipeline
    tracker: ChangeTracker

#TODO instead of parser_type use : class_name = self.__class__.__name__
class BaseParser(ABC):

    def __init__(self, dependencies: ParserDependencies, parser_type: str):
        self.fetcher = dependencies.fetcher
        self.pipeline = dependencies.pipeline
        self.tracker = dependencies.tracker
        self.parser_type = parser_type

    @abstractmethod
    async def _extract_data(self, content: Any, selectors: Dict[str, str]) -> List[str]:
        """Parse raw content into structured data. Subclasses implement this."""
        pass

    async def parse(self, config: dict) -> Optional['Result']:
        """
        Main parsing flow - same for all parser!
        """
        selectors = config['selectors']

        if not selectors:
            pass
            # assert exception

        # Step 1: Fetch content (strategy depends on injected fetcher)
        content = await self.fetcher.fetch(**config)
        if not content:
            return None

        # Step 2: Extract data (strategy depends on subclass)
        extracted_data = await self._extract_data(content, selectors)
        if not extracted_data or not any(extracted_data.values()):
            return None

        # Step 4: Run processing pipeline
        df = await self.pipeline.execute(df, config, self.parser_type)

        if df.empty:
            return None

        # Step 5: Return result
        from src.models.results import Result
        return Result(self.parser_type, **(df.to_dict(orient='list')))
