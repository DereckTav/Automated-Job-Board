from typing import Dict
import pandas as pd
from datetime import datetime
from LocalData.tracker import WebTracker

def keep_relevant(extracted_data: Dict, date_format: str, url: str, tracker: WebTracker):
    df = pd.DataFrame(extracted_data)

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