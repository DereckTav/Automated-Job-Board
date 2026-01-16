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

class DownloadParser(BaseParser):
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
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")
        df = await asyncio.to_thread(pd.read_csv, StringIO(content))
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) DONE extracting data")
        return df.to_dict(orient='list')


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
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

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
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

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
                        LOGGER.info(
                            f"{url}... --- ({self.__class__.__name__}) failed to extract data: \n {e} \n")
                        extracted_data[key] = []

            return extracted_data
        finally:
            await BrowserManager().resolve_persistent_driver(driver)


class SeleniumDownloadParser(BaseParser):
    """
    Parser for Airtable CSV downloads via Selenium.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies)

    async def _extract_data(
            self,
            content: str,
            selectors: Dict[str, str],
            url: str
    ) -> Dict[str, List[str]]:
        """
        Extract data from CSV content.
        """
        LOGGER.info(f"{url}... --- ({self.__class__.__name__}) Extracting based off selectors: {selectors.keys()}")

        if not content:
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
            LOGGER.info(f"{url}... --- ({self.__class__.__name__}) failed to extract data from csv: \n {e} \n")
            return {}

# Todo JobSpy parser
