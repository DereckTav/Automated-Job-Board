from io import StringIO

from src.core.parser.components.fetchers.components.browser import BrowserManager
from src.core.parser.core.base_parser import BaseParser, ParserDependencies
from typing import Dict, List, Any
from src.core import logs as log
import asyncio
import pandas as pd

class DownloadParser(BaseParser):
    """
    CSV download parser.

    SRP: ONLY responsible for parsing CSV format.
    All other concerns handled by injected dependencies.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies, "DOWNLOAD_PARSER")

    async def _extract_data(self, content: Any, selectors: Dict[str, str]) -> Dict[str, List[str]]:
        df = await asyncio.to_thread(pd.read_csv, StringIO(content))

        return df.to_dict(orient='list')


class StaticContentParser(BaseParser):
    """
    BeautifulSoup-based parser.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies, "STATIC_PARSER")

    async def _extract_data(self, content: Any, selectors: Dict[str, str]) -> Dict[str, List[str]]:
        log.info(f"StaticContentParser: Extracting {selectors}")

        from bs4 import BeautifulSoup
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

        return extracted


class JavaScriptContentParser(BaseParser):
    """
    Selenium-based parser.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies, "JS_PARSER")

    async def _extract_data(self, content: Any, selectors: Dict[str, str]) -> Dict[str, List[str]]:
        log.info(f"JavaScriptContentParser: Extracting {selectors}")

        from selenium.webdriver.common.by import By
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

                        await asyncio.sleep(0)
                    except Exception:
                        extracted_data[key] = []

            return extracted_data
        finally:
            await BrowserManager().resolve_persistent_driver(driver)


class SeleniumDownloadParser(BaseParser):
    """
    Parser for Airtable CSV downloads via Selenium.
    """

    def __init__(self, dependencies: ParserDependencies):
        super().__init__(dependencies, "AIRTABLE_SELENIUM_PARSER")

    async def _extract_data(self, content: str, selectors: Dict[str, str]) -> Dict[str, List[str]]:
        """
        Extract data from CSV content.
        """
        if not content:
            return {}

        try:
            log.info(f"SeleniumDownloadParser: Extracting {selectors}")

            # Parse CSV
            df = await asyncio.to_thread(pd.read_csv, StringIO(content))

            # Extract columns based on selectors
            extracted_data = {}
            for key, selector in selectors.items():
                if selector in df.columns:
                    extracted_data[key] = df[selector].astype(str).tolist()

            return extracted_data

        except Exception as e:
            log.error(f"Failed to parse CSV: {e}")
            return {}

# Todo implement rss parser
# Todo JobSpy parser