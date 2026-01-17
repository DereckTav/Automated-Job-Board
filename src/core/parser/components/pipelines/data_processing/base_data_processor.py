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
from abc import abstractmethod, ABC
from typing import Dict, Any, List
import pandas as pd

class BaseDataProcessor(ABC):
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
        if self.include is not None and self.include:
            return parser_type in self.include
        return parser_type not in self.exclude
