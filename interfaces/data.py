from abc import abstractmethod, ABC
from typing import Dict, Any
import pandas as pd

class DataProcessor(ABC):
    """
    Abstraction for data processing steps.
    """

    @abstractmethod
    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """Process dataframe and return modified version"""
        pass

    @abstractmethod
    def applies_to(self, parser_type: str) -> bool:
        """Determine if this processor should run for given parser type"""
        pass
