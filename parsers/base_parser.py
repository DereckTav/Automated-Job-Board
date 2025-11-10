from dataclasses import dataclass

from parsers.output import Result
from interfaces.tracker import ChangeTracker
from interfaces.content import ContentFetcher
from processing.pipeline import ProcessingPipeline

from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
import pandas as pd

@dataclass
class ParserDependencies:
    """
    Container for dependencies.
    """
    fetcher: ContentFetcher
    pipeline: ProcessingPipeline
    tracker: ChangeTracker


class BaseParser(ABC):
    """
    Base parser following SOLID principles.
    """

    def __init__(self, dependencies: ParserDependencies, parser_type: str):
        self.fetcher = dependencies.fetcher
        self.pipeline = dependencies.pipeline
        self.tracker = dependencies.tracker
        self.parser_type = parser_type

    @abstractmethod
    async def _extract_data(self, content: Any, selectors: Dict[str, str]) -> Dict[str, List[str]]:
        """Parse raw content into structured data. Subclasses implement this."""
        pass

    async def parse(self, config: dict) -> Optional['Result']:
        """
        Main parsing flow - same for all parsers!
        """
        selectors = config['selectors']

        if not selectors:
            return None

        # Step 1: Fetch content (strategy depends on injected fetcher)
        content = await self.fetcher.fetch(**config)
        if not content:
            return None

        # Step 2: Extract data (strategy depends on subclass)
        extracted_data = await self._extract_data(content, selectors)
        if not extracted_data or not any(extracted_data.values()):
            return None

        # Step 3: Convert to dataframe
        df = pd.DataFrame(extracted_data)

        # Step 4: Run processing pipeline
        df = await self.pipeline.execute(df, config, self.parser_type)

        if df.empty:
            return None

        # Step 5: Return result
        from parsers.output import Result
        return Result(self.parser_type, **(df.to_dict(orient='list')))
