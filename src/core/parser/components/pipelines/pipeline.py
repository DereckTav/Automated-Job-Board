from src.core.logs import Logger
from src.core.parser.components.pipelines.data_processing.data_processor import DataProcessor
from typing import List, Dict, Any
import pandas as pd

LOGGER = Logger('App')

class ProcessingPipeline:
    """
    Executes processors in order.
    """

    def __init__(self, processors: List[DataProcessor]):
        self.processors = processors

    async def execute(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            parser_type: str,
            **kwargs
    ) -> pd.DataFrame:
        """Run all applicable processors in sequence"""

        for processor in self.processors:

            if processor.applies_to(parser_type):

                df = await processor.process(
                    df=df,
                    config=config,
                    filters=filters,
                    url=config['url'][:25],
                    parser_type=parser_type,
                    **kwargs
                )

                if df.empty:
                    break  # Short circuit if no data left

        return df
