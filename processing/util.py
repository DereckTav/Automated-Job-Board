import pandas as pd
import numpy as np

def normalize_position(df: pd.DataFrame, position: str) -> pd.DataFrame:
    if df.empty:
        return df

    if position in df.columns:
        df = df.copy()
        df[position] = (df[position].str.replace(",", " -", regex=False)
                        .str.replace("，", " -", regex=False)
                        .str.replace("、", " -", regex=False))

    return df

def regularize_name(df: pd.DataFrame, list_of_nans) -> pd.DataFrame:
    if df.empty:
        return df

    for nan in list_of_nans:
        df = df.copy()
        df['company_name'] = df['company_name'].replace(nan, np.nan)
        df['company_name'] = df['company_name'].ffill()

    return df