import aiohttp

from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager
from src.core.parser.components.fetchers.core.exceptions.robots_txt_not_provided import RobotsTxtNotProvided
from src.core.parser.components.fetchers.core.fetcher import  ContentFetcher
from typing import Optional, Any
import asyncio

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.core.parser.components.fetchers.components.robots.parser import RobotsParser
from src.core.logs import Logger, APP

LOGGER = Logger(APP)

async def respect_robots(
        robots_url: str,
        user_agent: str,
        robots_parser: RobotsParser
) -> bool:
    """
    Raises:
        RobotsTxtNotProvided: If 'robots_url' is None
    """
    if not robots_url:
        raise RobotsTxtNotProvided("robots.txt not provided")

    # Check robots.txt
    rules = await robots_parser.get_rules(robots_url, user_agent)

    if not rules.can_fetch:
        return False

    # Respect crawl delay
    await asyncio.sleep(rules.crawl_delay)
    return rules.can_fetch


class HttpContentFetcher(ContentFetcher):
    """
    Fetches content via HTTP.
    """
    # might be problem with this type hint
    def __init__(
            self,
            session: aiohttp.ClientSession,
            user_agent: str,
            robots_parser: RobotsParser
    ):
        self.session = session
        self.user_agent = user_agent
        self.robots_parser = robots_parser

    async def fetch(
            self,
            url: str,
            **kwargs
    ) -> Optional[str]:
        robots_url = kwargs.get('robots_url')

        if not robots_url:
            raise ValueError(f"{self.__class__.__name__}.fetch() missing required keyword argument: 'robots_url'")

        try:
            can_parse = await respect_robots(robots_url, self.user_agent, self.robots_parser)

            if not can_parse:
                LOGGER.warning(f"Robots.txt disallows fetching: {url}")
                return None

        except RobotsTxtNotProvided:
            LOGGER.warning(f"Robots.txt not given for website: {url}")

        accept = kwargs.get('accept', 'text/html')
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept
        }

        try:
            LOGGER.info(f"{url} --- (HttpContentFetcher) Fetching Content")
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            LOGGER.error(f"{url} --- (HttpContentFetcher) Error fetching: {e}")
            return None

class SeleniumContentFetcher(ContentFetcher):
    """
    Fetches content via Selenium/browser.
    """

    def __init__(
            self,
            browser_manager: BrowserManager,
            user_agent: str,
            robots_parser: RobotsParser
    ):
        self.robots_parser = robots_parser
        self.browser_manager = browser_manager
        self.user_agent = user_agent

    # provide param robots_url
    async def fetch(
            self,
            url: str,
            **kwargs
    ) -> Optional[WebDriver]:
        robots_url = kwargs.get('robots_url')

        if not robots_url:
            raise ValueError(f"{self.__class__.__name__}.fetch() missing required keyword argument: 'robots_url'")

        try:
            can_parse = await respect_robots(robots_url, self.user_agent, self.robots_parser)

            if not can_parse:
                LOGGER.warning(f"Robots.txt disallows fetching: {url}")
                return None

        except RobotsTxtNotProvided:
            LOGGER.warning(f"Robots.txt not given for website: {url}")

        driver = None
        try:
            driver = await self.browser_manager.get_persistent_driver()
            # persistent because driver is required for extractor
            driver.get(url)
            await asyncio.sleep(10) #wait for content to load

            LOGGER.info(f"{url} --- (SeleniumContentFetcher) Fetching Content")
            return driver

        except Exception as e:
            try:
                if driver:
                    await self.browser_manager.resolve_persistent_driver(driver)
                LOGGER.error(f"{url} --- (SeleniumContentFetcher) Error fetching: {e}")

            except Exception as e:
                LOGGER.error(f"{url} --- (SeleniumContentFetcher) Error fetching: {e}")

            return None


class DownloadContentFetcher(ContentFetcher):
    """
    Fetches content via HTTP.
    """

    def __init__(
            self,
            session: aiohttp.ClientSession,
            user_agent: str
    ):
        self.session = session
        self.user_agent = user_agent

    async def fetch(
            self,
            url: str,
            **kwargs
    ) -> Optional[str]:
        accept = kwargs.get('accept', 'text/csv')
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept
        }

        try:
            LOGGER.info(f"{url} --- (DownloadContentFetcher) fetching content")
            # If page is no longer accessible download should not work
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            return content
        except Exception as e:
            LOGGER.error(f"{url} --- (DownloadContentFetcher) Error fetching: {e}")
            return None


class AirtableSeleniumContentFetcher(ContentFetcher):
    """
    Fetches CSV data from Airtable by clicking download button and reading file.
    """

    def __init__(
            self,
            browser_manager: BrowserManager,
            wait_time: int = 10,
            timeout: int = 10
    ):
        self.browser_manager = browser_manager
        self.wait_time = wait_time
        self.timeout = timeout

    async def fetch(
            self,
            url: str,
            **kwargs
    ) -> Optional[str]:
        """
        Fetch CSV content by clicking Airtable's download button.
        """

        try:
            LOGGER.info(f"{url[:25]}... --- (Airtable Selenium) Opening browser")

            async with self.browser_manager.get_driver() as driver:
                driver.get(url)

                LOGGER.info(f"{url[:25]}... --- (Airtable Selenium) Waiting {self.wait_time} seconds for page load...")
                await asyncio.sleep(self.wait_time)

                LOGGER.info(f"{url[:25]}... --- (Airtable Selenium) Page title: {driver.title}")

                # Click through UI to download CSV
                csv_content = await self._download_csv(url[:25], driver)

            return csv_content

        except Exception as e:
            LOGGER.error(f"{url[:25]}... --- (Airtable Selenium) Error fetching: {e}")
            import traceback
            LOGGER.error(traceback.format_exc())
            return None

    async def _download_csv(
            self,
            url: str,
            driver
    ) -> Optional[str]:
        """
        Click through Airtable UI to download CSV and read content.

        Flow:
        1. Click 3-dot menu (More view options)
        2. Click "Download CSV" button
        4. Wait for file to download
        5. Read file content
        6. Delete file
        """

        try:
            # Step 1: Click 3-dot menu
            if not await self._click_menu_button(driver, url):
                return None

            # Step 2: Click Download button
            if not await self._click_download_csv_button(driver, url):
                return None

            # Step 3: Wait for file and read content
            csv_content = await self._wait_and_read_file(self.browser_manager.get_download_directory(driver), url)

            return csv_content

        except Exception as e:
            LOGGER.error(f"{url}... --- (Airtable Selenium) Download failed: {e}")
            import traceback
            LOGGER.error(traceback.format_exc())
            return None

    @staticmethod
    async def _click_menu_button(
            driver,
            url: str
    ) -> bool:
        """
        Click the 3-dot menu button (More view options).
        """
        try:
            # Look for menu button in both French and English
            menu_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, 'viewMenuButton')]")
                )
            )

            LOGGER.info(f"{url}... --- (Airtable Selenium) Found menu button! Clicking...")
            menu_button.click()

            await asyncio.sleep(2)

            return True

        except Exception as e:
            LOGGER.error(f"{url}... --- (Airtable Selenium) Failed to click menu button: {e}")
            return False

    @staticmethod
    async def _click_download_csv_button(
            driver,
            url: str
    ) -> bool:
        """
        Click the "Download CSV" button in the menu (single button version).
        """
        LOGGER.info("(Airtable Selenium) Looking for 'Download CSV' button...")
        try:
            # Debug: Show available menu items
            try:
                menu_items = driver.find_elements(
                    By.XPATH,
                    "//button[contains(@role, 'menuitem')] | //div[@role='menuitem']"
                )
                if menu_items:
                    LOGGER.info(f"(Airtable Selenium) Found {len(menu_items)} menu items")
                    for i, item in enumerate(menu_items[:15]):
                        text = item.text.strip()
                        if text:
                            LOGGER.info(f"  {i}: {text}")
            except Exception as e:
                LOGGER.error(f"{url[:25]}... --- (Airtable Selenium) Failed to find 'Download CSV' button: {e}")
                return False

            # Find and click "Download CSV" button (French or English)
            # Look for exact text or aria-label
            download_csv_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//*[contains(text(), 'Download') or contains(text(), 'Télécharger')]")
                )
            )
            LOGGER.info(f"{url}... --- (Airtable Selenium) Found 'Download' button! Clicking...")
            download_csv_btn.click()

            # Brief wait after click
            await asyncio.sleep(10)

            return True

        except Exception as e:
            LOGGER.error(f"{url}... --- (Airtable Selenium) Failed to click 'Download CSV' button: {e}")
            return False

    async def _wait_and_read_file(
            self,
            download_dir: str,
            url: str
    ) -> Optional[str]:
        """
        Wait for CSV file to be downloaded and read its content.
        """
        LOGGER.info(f"{url}... --- (Airtable Selenium) downloading")
        import os

        await asyncio.sleep(30)

        seconds_elapsed = 0
        csv_files = []

        while seconds_elapsed < self.timeout:
            files = os.listdir(download_dir) # could add loop & executor here

            # Check if any partial downloads are still active
            if any(f.endswith('.crdownload') for f in files):
                await asyncio.sleep(1)
                continue

            # Check if the final .csv exists
            csv_files = [f for f in files if f.endswith('.csv')]

            await asyncio.sleep(1)
            seconds_elapsed += 1

        if seconds_elapsed > self.timeout:
            LOGGER.error(f"{url}... --- (Airtable Selenium) download timed out")
            return None

        if csv_files:
            csv_file = csv_files[0]
            LOGGER.info(f"{url}... --- (Airtable Selenium) SUCCESS! Downloaded: {csv_file}")

            # Read file content
            csv_path = os.path.join(download_dir, csv_file)

            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                return content

            except Exception as e:
                LOGGER.error(f"{url}... --- (Airtable Selenium) Failed to read file: {e}")
                return None

        LOGGER.error(f"{url}... --- (Airtable Selenium) Error with files in download directory: {download_dir}")
        return None

class HireBaseContentFetcher(ContentFetcher):
    """
    Fetches API content that returns a List of Json objects (one for each request payload).
    """

    def __init__(
            self,
            session: aiohttp.ClientSession,
            headers: dict[str, str],
            requests_payloads: list[dict[str, Any]]
    ):
        self.session = session
        self.headers = headers
        self.requests_payloads = requests_payloads

    async def fetch(
            self,
            url: str,
            **kwargs
    ) -> Optional[list[dict[str, Any]]]:

        if not self.requests_payloads:
            LOGGER.warning("(HireBaseContentFetcher) No requests provided.")
            return []

        valid_responses = []
        total = len(self.requests_payloads)

        LOGGER.info(f"{url} --- (HireBaseContentFetcher) Starting fetch of {total} requests")

        for i, payload in enumerate(self.requests_payloads):
            query_name = payload.get('query', f'Request #{i + 1}')

            try:
                LOGGER.info(f"(HireBaseContentFetcher) Processing request {i + 1}/{total}... ['{query_name}']")

                result = await self._fetch_single(url, self.headers, payload)

                if result:
                    valid_responses.append(result)

                if i < total - 1:
                    await asyncio.sleep(1) # rate limit

            except Exception as e:
                LOGGER.error(f"(HireBaseContentFetcher) FAILED Request '{query_name}': {e}")

        LOGGER.info(f"(HireBaseContentFetcher) Finished. Success: {len(valid_responses)}/{total}")
        return valid_responses

    async def _fetch_single(self, url: str, headers: dict, payload: dict) -> Optional[dict[str, Any]]:
        """
        Helper method to handle a single POST request safely.
        """
        async with self.session.post(url, json=payload, headers=headers) as response:
            response.raise_for_status()
            return await response.json()