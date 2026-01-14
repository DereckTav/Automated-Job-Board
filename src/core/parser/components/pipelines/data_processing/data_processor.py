from abc import abstractmethod, ABC
from typing import Dict, Any, List
import pandas as pd

class DataProcessor(ABC):
    """
    Abstraction for data processing steps.
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None, **kwargs):
        self.include = include_parsers  # If set, Apply to only this parser
        self.exclude = exclude_parsers or []  # Never apply to these

        self.kwargs = kwargs

    @abstractmethod
    async def process(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            **kwargs
    ) -> pd.DataFrame:
        """Process dataframe and return modified version"""
        pass

    def applies_to(
            self,
            parser_type: str
    ) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude
