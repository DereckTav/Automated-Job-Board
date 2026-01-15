"""
recommended ordering:

ChangeDetectionProcessor
DateFilterProcessor
FiltersProcessor
PositionNormalizationProcessor

for agents version aka (url only)
changeDetectionProcessor
"""
import re

from src.core.logs import Logger, APP
from src.core.parser.components.pipelines.data_processing.data_processor import DataProcessor
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from src.core.parser.components.pipelines.data_processing.trackers.tracker import ChangeTracker
from src.core.parser.components.pipelines.data_processing.util import get_from

LOGGER = Logger(APP)

class DateFilterProcessor(DataProcessor):
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

        if "--relative" in date_format:
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) filtering based on relative date')
            return self.extract_relative(df, date_format.replace("--relative", "").strip())

        else:
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) filtering based date format regex')
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


class FiltersProcessor(DataProcessor):
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
            LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) Filtering based on ||{category}|| filters')
            strategy_func = strategies.get(category)

            if not strategy_func:
                continue  # Skip categories we haven't defined functions for yet

            for column, tags in column_map.items():
                if column in df_copy.columns:
                    df_copy = strategy_func(df_copy, column, tags)

        return df_copy

# required for position column in notion
class PositionNormalizationProcessor(DataProcessor):
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

        LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) Normalizing position column')

        if 'position' in df.columns:
            df = df.copy()
            df['position'] = (df['position'].str.replace(",", " -", regex=False)
                            .str.replace("，", " -", regex=False)
                            .str.replace("、", " -", regex=False))

        return df

class ChangeDetectionProcessor(DataProcessor):
    """
    Detects changes using hash tracking and filters to new rows only.
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

        LOGGER.info(f'{self.kwargs.get('url')}... -- ({self.kwargs.get('parser_type')}) filtering out scene rows')

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
