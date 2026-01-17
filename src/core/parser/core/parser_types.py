"""
DESIGN Principle : Identity Wrappers
======================================

Problem:
    Specialized fetchers (like AirtableSeleniumContentFetcher) often require standard parsing logic
    (e.g., Download extraction) but need a unique identity for:
    1. Pipeline Filtering (Whitelisting/Blacklisting specific parsers).
    2. Observability (Logs should read 'AirtableSeleniumParser', not 'DownloadCSVParser').

Solution:
    Do not duplicate logic or manually wrap the class.
    Instead, create a subclass that inherits from the existing parser.

    Example:
        class SeleniumDownloadParser(DownloadCSVParser):
            pass
"""
from io import StringIO

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from src.core.logs import Logger, APP
from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager
from src.core.parser.core.base_parser import BaseParser, ParserDependencies
from typing import Dict, List, Any
import asyncio
import pandas as pd

LOGGER = Logger(APP)

class DownloadCSVParser(BaseParser):
    """
    CSV download parser.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies)

    async def _extract_data(
            self,
            content: Any,
            selectors: Dict[str, str],
            url: str
    ) -> Dict[str, List[str]]:
        """
            Extract data from CSV content.

            :param content: io.TextIOBase
            :param selectors: Mapping of { 'Output Column Name': 'csv column name' }.
        """
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

        if not content:
            LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Content is empty")
            return {}

        try:
            # Parse CSV
            df = await asyncio.to_thread(pd.read_csv, StringIO(content))

            # Extract columns based on selectors
            extracted_data = {}
            for key, selector in selectors.items():
                if selector in df.columns:
                    extracted_data[key] = df[selector].astype(str).tolist()

            LOGGER.info(f"{url}... --- ({self.__class__.__name__}) DONE extracting data")

            return extracted_data

        except Exception as e:
            LOGGER.error(f"{url}... --- ({self.__class__.__name__}) failed to extract data from csv: \n {e} \n")
            return {}


class SeleniumDownloadParser(DownloadCSVParser):
    """
        wrapper class of DownloadCSVParser for logging purposes and for pipelines
    """
    pass

class StaticContentParser(BaseParser):
    """
    BeautifulSoup-based parser.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies)

    async def _extract_data(
            self,
            content: Any,
            selectors: Dict[str, str],
            url: str
    ) -> Dict[str, List[str]]:
        """
            extract elements from html using beautiful-soup

            :param content: string that is a html
            :param selectors: Mapping of { 'Output Column Name': 'css selector' }.
        """
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

        if not content:
            LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Content is empty")
            return {}

        soup = BeautifulSoup(content, 'html.parser')

        extracted = {}
        for key, selector in selectors.items():
            elements = soup.select(selector)
            if elements:
                if key == "application_link":
                    extracted[key] = [
                        elem.get("href") if elem.has_attr("href")
                        else elem.get_text(strip=True)
                        for elem in elements
                    ]
                else:
                    extracted[key] = [elem.get_text(strip=True) for elem in elements]

        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) DONE extracting data")

        return extracted


class JavaScriptContentParser(BaseParser):
    """
    Selenium-based parser.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies)

    async def _extract_data(
            self,
            content: Any,
            selectors: Dict[str, str],
            url: str
    ) -> Dict[str, List[str]]:
        """
            extract elements from web page through driver

            :param content: selenium driver
            :param selectors: Mapping of { 'Output Column Name': 'csv column name' }.
        """
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

        if not content:
            LOGGER.info(f"{url}... --- ({self.__class__.__name__}) driver was not provided")
            return {}

        driver = content

        # Wait for content to load
        await asyncio.sleep(25)
        try:
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

                        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) DONE extracting data")

                        await asyncio.sleep(0)
                    except Exception as e:
                        LOGGER.error(
                            f"{url}... --- ({self.__class__.__name__}) failed to extract data: \n {e} \n")
                        extracted_data[key] = []

            return extracted_data
        finally:
            await BrowserManager().resolve_persistent_driver(driver)

class HireBaseParser(BaseParser):

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies)

    async def _extract_data(
            self,
            content: list[dict[str, Any]],
            selectors: dict[str, str],
            url: str
    ) -> dict[str, list[str]]:
        """
            Extracts data from a list of JSON API responses.

            :param content: A list of dictionaries, where each dict is a full API response containing a 'jobs' key.
            :param selectors: Mapping of { 'Output Column Name': 'JSON Key (selector)' }.
        """
        LOGGER.info(f"({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

        if not content:
            LOGGER.warning(f"({self.__class__.__name__}) Content is empty")
            return {}

        extracted_data = {key: [] for key in selectors.keys()}

        for response_page in content:
            jobs_list = response_page.get("jobs", [])

            for job in jobs_list:
                for key, selector in selectors.items():
                    raw_value = self._get_json_value(job, selector)

                    # recursively format it into a clean string
                    formatted_value = self._format_value(raw_value)

                    extracted_data[key].append(formatted_value)

        LOGGER.info(f"({self.__class__.__name__}) DONE extracting data")

        return extracted_data

    def _format_value(self, value: Any) -> str:
        """
        Recursively decodes complex structures into formatted strings.
        - None -> ""
        - List -> "Item 1, Item 2"
        - Dict -> "Key: Value\nKey2: Value2"
        - Int/Str -> String representation
        """
        if value is None:
            return ""

        # Handle Lists: Join with comma
        if isinstance(value, list):
            return ", ".join([self._format_value(item) for item in value])

        # Handle Dicts: Join with newlines
        if isinstance(value, dict):
            lines = []
            for k, v in value.items():
                # Recursively format the value inside the dict
                formatted_v = self._format_value(v)
                lines.append(f"{k}: {formatted_v}")
            return "\n".join(lines)

        # Handle Primitives (int, float, bool, str)
        return str(value)

    @staticmethod
    def _get_json_value(data: dict, key_path: str) -> Any:
        """
        Helper to fetch values from nested JSON using dot notation.
        """
        if not key_path:
            return None

        keys = key_path.split('.')
        current_val = data

        for key in keys:
            if isinstance(current_val, dict):
                current_val = current_val.get(key)
            elif isinstance(current_val, list):
                # Handle numeric indices like 'jobs.0.title'
                if key.isdigit() and int(key) < len(current_val):
                    current_val = current_val[int(key)]
                else:
                    return None
            else:
                return None

        return current_val