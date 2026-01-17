"""
recommended ordering:

ChangeDetectionProcessor
DateFilterProcessor
FiltersProcessor
PositionNormalizationProcessor

for agents version aka (url only)
changeDetectionProcessor

DESIGN PRINCIPLE: Optional Column Dependency
=============================================
Processors that rely on specific selectors (columns) which may not be present
in every dataset must implement "Graceful Degradation."

Implementation Requirements:
1. Check for Existence: Verify required columns exist before processing.
2. Pass-Through on Failure: If columns are missing, return the original DataFrame
   unmodified (Identity Transformation).
3. No Exceptions: Do NOT raise KeyErrors for missing optional columns.
4. Observability: Log a WARNING to alert the user that the step was skipped.

This ensures the pipeline remains robust even when partial data is fetched.

examples of Optional column dependency is:
'PositionNormalizationProcessor'

"""
import re

from src.core.logs import Logger, APP
from src.core.parser.components.pipelines.data_processing.base_data_processor import BaseDataProcessor
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from src.core.parser.components.pipelines.data_processing.exceptions.column_not_found_exception import \
    ColumnNotFoundException
from src.core.parser.components.pipelines.data_processing.trackers.tracker import ChangeTracker
from src.core.parser.components.pipelines.data_processing.util import get_from

LOGGER = Logger(APP)

class DateFilterProcessor(BaseDataProcessor):
    """
    Filters dataframe by date (today and yesterday).
    """

    async def process(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            **kwargs
    ) -> pd.DataFrame:
        if df.empty:
            return df

        date_format = config['date_format']

        if 'date' not in df.columns:
            LOGGER.warning(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) date column not found in dataframe')
            raise ColumnNotFoundException(f"date column not found in dataframe : {self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__})")

        if "--relative" in date_format:
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) filtering based on relative date')
            return self.extract_relative(df, date_format.replace("--relative", "").strip())

        else:
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) filtering based date format regex')
            df['date'] = pd.to_datetime(df['date'], format=date_format)
            today = pd.Timestamp(datetime.today().date())
            yesterday = today - pd.Timedelta(days=1)
            return df[df['date'].isin([today, yesterday])]

    @staticmethod
    def extract_relative(
            df: pd.DataFrame,
            template: str
    ) -> pd.DataFrame:
        # 1. Escape the template to handle random chars like ( ) [ ] ? * +
        # 2. Replace the escaped '{n}' with a digit capture group (\d+)
        # 3. Replace spaces in the template with \s* to handle "0 days" vs "0days"

        pattern = (re
                   .escape(template)
                   .replace(r'\{n\}', r'(\d+)')
                   .replace(r'\ ', r'\s*'))

        # Extract
        extracted = df['date'].str.strip().str.extract(f"(?i){pattern}")

        # Convert to numeric
        days_numeric = pd.to_numeric(extracted[0], errors='coerce')
        return df[days_numeric.isin([0, 1])].copy()


class FiltersProcessor(BaseDataProcessor):
    """applies filters from filters.yaml to dataframe."""

    @staticmethod
    def _apply_ignore(df, col, tags):
        pattern = '|'.join(re.escape(t) for t in tags)
        return df[~df[col].astype(str).str.lower().str.contains(pattern, na=False)]

    @staticmethod
    def _apply_scrub(df, col, tags):
        # Using assign to stay functional and avoid SettingWithCopy warnings
        return df.assign(**{col: df[col].replace(list(tags), pd.NA).ffill()})

    # ORDER IS IMPORTANT
    def get_strategies(self):
        return {
            'ignore': self._apply_ignore,
            'scrubAndFfill': self._apply_scrub
        }

    async def process(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            **kwargs
    ) -> pd.DataFrame:
        if df.empty:
            return df

        strategies = self.get_strategies()

        # Get categorized filters
        filters = get_from(
            filters,
            config.get('site_id'),
            list(config.get('selectors').keys()),
            list(strategies.keys())
        )

        df_copy = df.copy()

        # Iterate through categories and apply their specific strategy
        for category, column_map in filters.items():
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) Filtering based on ||{category}|| filters')
            strategy_func = strategies.get(category)

            if not strategy_func:
                continue  # Skip categories we haven't defined functions for yet

            for column, tags in column_map.items():
                if column not in df_copy.columns:
                    LOGGER.warning(
                        f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) date column not found in dataframe'
                    )

                    raise ColumnNotFoundException(f'{column} not found in dataframe : {self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__})')

                df_copy = strategy_func(df_copy, column, tags)

        return df_copy

# required for position column in notion
class PositionNormalizationProcessor(BaseDataProcessor):
    """
    Normalizes position column.
    """

    async def process(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            **kwargs
    ) -> pd.DataFrame:
        if df.empty:
            return df

        LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) Normalizing position column')

        if 'position' not in df.columns:
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) SKIPPED PROCESSOR ({self.__class__.__name__}) Normalizing position column')
            return df

        df = df.copy()
        df['position'] = (df['position'].str.replace(",", " -", regex=False)
                        .str.replace("，", " -", regex=False)
                        .str.replace("、", " -", regex=False))

        return df

class ChangeDetectionProcessor(BaseDataProcessor):
    """
    Detects new data by hashing rows and comparing them against a persistent history state.
    Filters the dataset to return ONLY rows that have not been seen before.

    Ideal Use Case:
        - Homogeneous, tabular data (e.g., a single CSV feed, a specific SQL query).
        - Data where the entire dataset represents one logical "stream" of information.

    Anti-Pattern (e.g., HireBaseParser):
        This processor is less effective for aggregators like HireBaseParser that
        batch multiple distinct queries (e.g., "Software" + "Quant" + "Data") into
        a single output list.

        it is difficult to use with Vector Search Aggregators like HireBase.

        Why? When distinct data streams are concatenated before processing:
        1. Granularity is lost: You cannot track "New rows for Query A" vs "New rows for Query B".
        2. Partial Failures: If one query fails but others succeed, the shared state
           becomes difficult to manage (partial state corruption).
    """

    def __init__(self, tracker: ChangeTracker, include_parsers: List[str] = None, exclude_parsers: List[str] = None, **kwargs):
        super().__init__(include_parsers, exclude_parsers, **kwargs)
        self.tracker = tracker

    async def process(
            self,
            df: pd.DataFrame,
            config: Dict[str, Any],
            filters: Dict[str, Any],
            **kwargs
    ) -> pd.DataFrame:
        if df.empty:
            return df

        url = config['url']

        hash_val = self.tracker.get(url)
        content_hash = str(df.iloc[0].tolist())

        LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) -- ({self.__class__.__name__}) filtering out scene rows')

        # First time seeing data
        if hash_val is None:
            self.tracker.track(url, content_hash)
            return df

        # Nothing changed
        if hash_val == content_hash:
            return pd.DataFrame(columns=df.columns)  # Empty

        # Something changed, find new rows
        self.tracker.track(url, content_hash)

        match_mask = df.apply(lambda row: str(row.tolist()) == hash_val, axis=1)

        if match_mask.any():
            match_idx = match_mask.idxmax()
            return df.loc[:match_idx - 1] if match_idx > 0 else pd.DataFrame(columns=df.columns)

        return df