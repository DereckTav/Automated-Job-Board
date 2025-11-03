from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime
from LocalData.tracker import WebTracker

def keep_relevant(
        extracted_data: Dict,
        date_format: str,
        url: str,
        tracker: WebTracker,
        ignore_filters: Optional[Dict[str, List[str]]] = None
) -> Optional[pd.DataFrame]:
    df = pd.DataFrame.from_dict(extracted_data, orient='index').T

    if df.empty:
        return None

        # Normalize text in all string columns to handle encoding issues
        for col in df.columns:
            if df[col].dtype == 'object':  # String columns
                df[col] = df[col].apply(lambda x: normalize_text(x) if pd.notna(x) and x else x)

    for field in ['application_link', 'company_name', 'position']:
        df = df[df[field].notna() & (df[field].astype(str).str.strip() != '')]

    # Apply ignore filters
    if ignore_filters:
        df = apply_ignore_filters(df, ignore_filters)

        if df.empty:
            return None

    if "-relative" in date_format:
        df['date'] = df['date'].str.extract(r'(\d+)').astype(int)
        df_filtered = df[df['date'].isin([0, 1])] # 0 is today and 1 is yesterday

    else:
        df['date'] = pd.to_datetime(df['date'], format=date_format)
        today = pd.Timestamp(datetime.today().date())
        yesterday = today - pd.Timedelta(days=1)
        df_filtered = df[df['date'].isin([today, yesterday])]

    hash_val = tracker.get(url)  # this was the first row of the dataframe from the most recent call before
    content_hash = str(df_filtered.iloc[0].tolist())  # This is the first row of the dataframe

    final_df = None
    if hash_val is None:  # First time seeing data
        tracker.track(url, content_hash)
        final_df = df_filtered

    elif hash_val == content_hash:  # Nothing changed in data
        return None

    else:  # Something changed, figure out what's new
        tracker.track(url, content_hash)

        match_mask = df_filtered.apply(lambda row: str(row.tolist()) == hash_val, axis=1)

        if match_mask.any():
            match_idx = match_mask.idxmax()
            final_df = df_filtered.loc[:match_idx - 1] if match_idx > 0 else pd.DataFrame(columns=df.columns)

    return final_df


def apply_ignore_filters(df: pd.DataFrame, ignore_filters: Dict[str, List[str]]) -> pd.DataFrame:
    filtered_df = df.copy()

    for column, ignore_terms in ignore_filters.items():
        if column not in filtered_df.columns:
            continue

        if not ignore_terms:
            continue

        # Create a boolean mask for rows to keep
        # We'll mark rows as False (to remove) if they contain any ignore term
        mask = pd.Series([True] * len(filtered_df), index=filtered_df.index)

        for term in ignore_terms:
            # Case-insensitive partial match
            term_lower = str(term).lower()
            column_mask = filtered_df[column].astype(str).str.lower().str.contains(term_lower, na=False)
            mask = mask & ~column_mask

        filtered_df = filtered_df[mask]

        if filtered_df.empty:
            break

    return filtered_df