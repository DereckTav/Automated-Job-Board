from interfaces.data import DataProcessor
from interfaces.tracker import ChangeTracker
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd


class DateFilterProcessor(DataProcessor):
    """
    Filters dataframe by date (today and yesterday).
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None):
        self.include = include_parsers  # If set, only these parsers
        self.exclude = exclude_parsers or []  # Never apply to these

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        if df.empty:
            return df

        date_format = config['date_format']

        if "-relative" in date_format:
            df['date'] = df['date'].str.extract(r'(\d+)').astype(int)
            return df[df['date'].isin([0, 1])]  # 0 is today and 1 is yesterday

        else:
            df['date'] = pd.to_datetime(df['date'], format=date_format)
            today = pd.Timestamp(datetime.today().date())
            yesterday = today - pd.Timedelta(days=1)
            return df[df['date'].isin([today, yesterday])]


class IgnoreDataWithFlagProcessor(DataProcessor):
    """
    gets rid of rows where one of the columns have a valid flag
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None):
        self.include = include_parsers
        self.exclude = exclude_parsers or []

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        if df.empty:
            return df

        tags = config['selectors'].get('ignore', {})

        if not tags:
            return df

        df_copy = df.copy()

        for column, tags in tags.items():
            if column not in df_copy.columns:
                continue

            if not tags:
                continue

            # Create a boolean mask for rows to keep
            # We'll mark rows as False (to remove) if they contain any ignore term
            mask = pd.Series([True] * len(df_copy), index=df_copy.index)

            for term in tags:
                # Case-insensitive partial match
                term_lower = str(term).lower()
                column_mask = df_copy[column].astype(str).str.lower().str.contains(term_lower, na=False)
                mask = mask & ~column_mask

            df_copy = df_copy[mask]

            if df_copy.empty:
                break

        return df_copy

class PositionNormalizationProcessor(DataProcessor):
    """
    Normalizes position column.
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None):
        self.include = include_parsers
        self.exclude = exclude_parsers or []

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        from processing.util import normalize_position
        position_col = config['selectors'].get('position')
        return normalize_position(df, position_col)

class NameRegularizationProcessor(DataProcessor):
    """
    Regularizes company names.
    by treating certain chars as null.
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None):
        self.include = include_parsers
        self.exclude = exclude_parsers or []

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        from processing.util import regularize_name

        list_of_nans = config.get('regularize', {}).get('chars', None)
        if not list_of_nans:
            return df

        return regularize_name(df, list_of_nans)


class ColumnRegularizationProcessor(DataProcessor):
    """
    Regularizes column names to hard coded values
    """

    def __init__(self, include_parsers: List[str] = None, exclude_parsers: List[str] = None):
        self.include = include_parsers
        self.exclude = exclude_parsers or []

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        selectors = config['selectors']

        for column, selector in selectors.items():
            df.rename(columns={selector: column}, inplace=True)

        return df


class ChangeDetectionProcessor(DataProcessor):
    """
    Detects changes using hash tracking and filters to new rows only.
    """

    def __init__(self, tracker: ChangeTracker,
                 include_parsers: List[str] = None,
                 exclude_parsers: List[str] = None):
        self.tracker = tracker
        self.include = include_parsers
        self.exclude = exclude_parsers or []

    def applies_to(self, parser_type: str) -> bool:
        if self.include is not None:
            return parser_type in self.include
        return parser_type not in self.exclude

    async def process(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        if df.empty:
            return df

        url = config['url']

        hash_val = self.tracker.get(url)
        content_hash = str(df.iloc[0].tolist())

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