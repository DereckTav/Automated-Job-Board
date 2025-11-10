from interfaces.data import DataProcessor
from typing import List, Dict, Any
import pandas as pd

class ProcessingPipeline:
    """
    Executes processors in order.
    """

    def __init__(self, processors: List[DataProcessor]):
        self.processors = processors

    async def execute(self, df: pd.DataFrame, config: Dict[str, Any], parser_type: str) -> pd.DataFrame:
        """Run all applicable processors in sequence"""
        for processor in self.processors:
            if processor.applies_to(parser_type):
                df = await processor.process(df, config)
                if df.empty:
                    break  # Short circuit if no data left
        return df