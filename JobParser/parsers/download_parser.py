import asyncio
from datetime import datetime
from io import StringIO

from fake_useragent import UserAgent
from LocalData.tracker import WebTracker
from Http.http_client import Session

import pandas as pd

from JobParser.output import Result
from typing import Optional
from JobParser.parsers.generic_parser import Parser

from JobParser.parsers.util import normalize_position, regularize_name
import logs.logger as log

class DownloadParser(Parser):
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, "_initialized"):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.ua = UserAgent() # if performance problems make a singleton class for this
            self.tracker = WebTracker()
            self.session = Session()
            self._initialized = True

    async def _get(self, url: str, accept: str) -> Optional[str]:
        self.ua = UserAgent()
        headers = {
            "User-Agent": self.ua.random,
            "Accept": accept
        }

        response = None
        try:
            #If page is no longer accessible download should not work
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            return content
        except Exception as e:
            log.error(f"(Download Parser) Error fetching : {url}: {e}")

    async def parse(self, config: dict) -> Optional[Result]:
        url = config['url']
        accept = config['accept']
        date_format = config['date_format']
        selectors = config['selectors']
        log.info(f"Download_Parser ({url[:75]}...)")
        if not selectors:
            log.info("No selectors selected")
            return None

        date = selectors['date']

        body = await self._get(url, accept) or ""
        df = await asyncio.to_thread(pd.read_csv, StringIO(body))

        df[date] = pd.to_datetime(df[date], format=date_format)

        #filter by date
        today = pd.Timestamp(datetime.today().date())
        yesterday = today - pd.Timedelta(days=1)
        df_filtered = df[df[date].isin([today, yesterday])]

        df_filtered = normalize_position(df_filtered, selectors['position'])

        list_of_nans = config.get('regularize', {}).get('chars', None)

        if list_of_nans:
            df = regularize_name(df, selectors['company_name'], list_of_nans)

        if df_filtered.empty:
            return None

        #get hashes
        hash_val = self.tracker.get(url) #this was the first row of the dataframe from the most recent call before
        content_hash = str(df_filtered.iloc[0].tolist()) #This is the first row of the dataframe

        final_df = None
        if hash_val is None: # First time seeing data
            self.tracker.track(url, content_hash)
            final_df = df_filtered

        elif hash_val == content_hash: # Nothing changed in data
            log.info(f"Download_Parser ({url[:75]}...): empty")
            return None

        else: # Something changed, figure out what's new
            self.tracker.track(url, content_hash)

            match_mask = df_filtered.apply(lambda row: str(row.tolist()) == hash_val, axis=1)

            if match_mask.any():
                match_idx = match_mask.idxmax()
                final_df = df_filtered.loc[:match_idx - 1] if match_idx > 0 else pd.DataFrame(columns=df.columns)

        log.info(f"Download_Parser ({url[:75]}...): got relevant data")

        extracted_data = {}

        for key, selector in selectors.items():
            if selector in final_df.columns:
                await asyncio.sleep(0) # this should work assuming that there is another task in the cycle
                # reason: if dataframe that is being filtered is large
                # It's time for you to go lol
                extracted_data[key] = final_df[selector].astype(str).tolist()

        log.info(f"Download_Parser ({url[:75]}...): extracted data")

        return Result("DOWNLOAD_PARSER",**extracted_data)
