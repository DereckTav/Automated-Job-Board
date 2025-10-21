import asyncio
import logging
from typing import Optional

from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from Http.http_client import Session
from LocalData.tracker import WebTracker
from Robots.robots_parser import RobotsTxtParser
from JobParser.output import Result
from JobParser.parsers.util import keep_relevant

from pathlib import Path

# Get the directory where the current script lives
base_dir = Path(__file__).resolve().parent

# Create a logs directory if it doesn't exist
logs_dir = base_dir / "logs"
logs_dir.mkdir(exist_ok=True)

# Full path to the log file
log_file = logs_dir / "parser.log"


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

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

        user_agent = self.ua.random

        headers = {
            'User-Agent': user_agent
        }

        try:
            rules = await RobotsTxtParser().get_rules(url, base_url, user_agent)
            if not rules.can_fetch:
                logging.error(f"can not fetch {url}")
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

            df= keep_relevant(extracted_data, date_format, url, self.tracker)

            return Result(**(df.to_dict(orient='list')))

        except Exception as e:
            logging.error(f"Error parsing content from {url}: {e}")
            return None