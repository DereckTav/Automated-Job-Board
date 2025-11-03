import asyncio
from typing import Optional

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from LocalData.tracker import WebTracker
from Robots.robots_parser import RobotsTxtParser
from JobParser.output import Result

from JobParser.parsers.generic_parser import Parser
from JobParser.parsers.util import keep_relevant, normalize_position

import logs.logger as log

#if there is a job site that dynamically loads content and doesn't allow download make scroll version

class JavaScriptContentParser(Parser):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, headless: bool = True):
        if not self._initialized:
            self.headless = headless
            self.ua = UserAgent() # if performance problems make a singleton class for this
            self.tracker = WebTracker()
            self._initialized = True

    def _setup_driver_options(self, user_agent: str):
        """Setup Chrome driver options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--user-agent={user_agent}")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--memory-pressure-off")

        return chrome_options

    async def parse(self, config: dict) -> Optional[Result]:
        url = config['url']
        base_url = config['base_url']
        date_format = config['date_format']
        selectors = config['selectors']
        ignore_filters = config.get('ignore', {})  # Get ignore filters from config
        identifier = f'JS_parser({url})'
        log.info(identifier)

        user_agent = self.ua.random
        chrome_options = self._setup_driver_options(user_agent)
        driver = None

        try:
            rules = await RobotsTxtParser().get_rules(url, base_url, user_agent)
            if not rules.can_fetch:
                log.warning(f"JS: can not fetch {url}")
                return None

            driver = asyncio.to_thread(webdriver.Chrome, options=chrome_options)
            await asyncio.sleep(rules.crawl_delay) # turn asyncio

            driver = await driver

            driver.set_page_load_timeout(30)
            driver.get(url)

            await asyncio.sleep(10) #content loads

            extracted_data = {}
            if selectors:
                for key, selector in selectors.items():
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if key == "application_link":
                            extracted_data[key] = [
                                elem.get_attribute("href") or elem.text.strip()
                                for elem in elements
                            ]
                        else:
                            extracted_data[key] = [elem.text.strip() for elem in elements if elem.text.strip()]

                        await asyncio.sleep(0)  # this should work assuming that there is another task in the cycle
                    except Exception:
                        extracted_data[key] = []
            else:
                return None

            log.info(f"{identifier}: extracted data")

            if not any(extracted_data.values()): # might be causing out-of-bounds error when empty (Not important)
                log.info(f'{identifier}: empty extracted data')
                return None

            df = keep_relevant(extracted_data, date_format, url, self.tracker, ignore_filters)
            df = normalize_position(df)

            log.info(f"{identifier}: got relevant data")

            if df is None or df.empty:
                return None

            return Result(**(df.to_dict(orient='list')))

        except Exception as e:
            log.error(f"Error parsing content from {url}: {e}")
            return None

        finally:
            if driver:
                driver.quit()

