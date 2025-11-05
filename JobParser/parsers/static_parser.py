import asyncio
from typing import Optional

from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from Http.http_client import Session
from LocalData.tracker import WebTracker
from Robots.robots_parser import RobotsTxtParser
from JobParser.output import Result
from JobParser.parsers.util import keep_relevant, normalize_position, regularize_name

import logs.logger as log

class StaticContentParser:
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.ua = UserAgent() # if performance problems make a singleton class for this
            self.tracker = WebTracker()
            self.session = Session()
            self._initialized = True

    async def parse(self, config: dict) -> Optional[Result]:
        url = config['url']
        base_url = config['base_url']
        date_format = config['date_format']
        selectors = config['selectors']
        ignore_filters = config.get('ignore', {})
        identifier = f'static_parser({url})'
        log.info(identifier)

        user_agent = self.ua.random

        headers = {
            'User-Agent': user_agent
        }

        try:
            rules = await RobotsTxtParser().get_rules(url, base_url, user_agent)
            if not rules.can_fetch:
                log.warning(f"static: can not fetch {url}")
                return None

            await asyncio.sleep(rules.crawl_delay)

            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            soup = BeautifulSoup(content, 'html.parser')

            extracted_data = {}
            if selectors:
                for key, selector in selectors.items():
                    elements = soup.select(selector)
                    if elements:
                        if key == "application_link":
                            extracted_data[key] = [
                                elem.get("href") if elem.has_attr("href")
                                else elem.get_text(strip=True)
                                for elem in elements
                            ]
                        else:
                            extracted_data[key] = [elem.get_text(strip=True) for elem in elements]
                    await asyncio.sleep(0) #this should work assuming that there is another task in the cycle
            else:
                return None

            log.info(f"{identifier}: extracted data")

            if not any(extracted_data.values()):
                log.info(f'{identifier}: empty extracted data')
                return None

            df = keep_relevant(extracted_data, date_format, url, self.tracker, ignore_filters)
            df = normalize_position(df, 'position')

            list_of_nans = config.get('regularize', {}).get('chars', None)

            if list_of_nans:
                df = regularize_name(df, 'company_name', list_of_nans)

            log.info(f"{identifier}: got relevant data")

            if df is None or df.empty:
                return None

            return Result("STATIC_PARSER",**(df.to_dict(orient='list')))

        except Exception as e:
            log.error(f"Error parsing content from {url}: {e}")
            return None