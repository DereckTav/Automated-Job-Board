from dataclasses import dataclass

import pandas as pd

from src.core.parser.components.pipelines.data_processing.trackers.tracker import ChangeTracker
from src.core.parser.components.fetchers.core.fetcher import ContentFetcher
from src.core.parser.components.pipelines.pipeline import ProcessingPipeline

from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod

from src.core.parser.core.exceptions.no_selectors_provided_exception import NoSelectorsProvidedException

@dataclass
class ParserDependencies:
    """
    Container for dependencies.
    """
    fetcher: ContentFetcher
    pipeline: ProcessingPipeline
    tracker: ChangeTracker

class BaseParser(ABC):

    def __init__(self, dependencies: ParserDependencies):
        self.fetcher = dependencies.fetcher
        self.pipeline = dependencies.pipeline
        self.tracker = dependencies.tracker

    @abstractmethod
    async def _extract_data(
            self,
            content: Any,
            selectors: Dict[str, str],
            url: str
    ) -> Dict[str, List[str]]:
        """Parse raw content into structured data. Subclasses implement this.
            url: for logging
        """
        pass

    async def parse(
            self,
            config: Dict[str, Any],
            filters: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        Main parsing flow - same for all parser!
        """
        selectors = config['selectors']
        url = config['url']

        if not selectors:
            raise NoSelectorsProvidedException("No selectors provided")

        # Step 1: Fetch content (strategy depends on injected fetcher)
        content = await self.fetcher.fetch(url, **config)
        if not content:
            return None

        # Step 2: Extract data (strategy depends on subclass)
        extracted_data = await self._extract_data(content, selectors, url[:25])
        if not extracted_data or not any(extracted_data.values()): # type: ignore
            return None

        df = pd.DataFrame(extracted_data)

        # Step 4: Run processing pipeline
        df = await self.pipeline.execute(df, config, filters, self.__class__.__name__)

        if df.empty:
            return None

        return df
