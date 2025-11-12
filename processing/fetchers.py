from interfaces.content import  ContentFetcher
from typing import Optional, Any, List
import asyncio

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from interfaces.robots import RobotsParser
from logs import logger as log


async def respect_robots(base_url: str, url: str, user_agent: str, robots_parser: RobotsParser) -> bool:
    # Check robots.txt
    rules = await robots_parser.get_rules(url, base_url, user_agent)

    if not rules.can_fetch:
        log.warning(f"Robots.txt disallows fetching: {url}")
        return False

    # Respect crawl delay
    await asyncio.sleep(rules.crawl_delay)
    return rules.can_fetch


class HttpContentFetcher(ContentFetcher):
    """
    Fetches content via HTTP.
    """

    def __init__(self, session, user_agent_provider, robots_parser):
        self.session = session
        self.ua_provider = user_agent_provider
        self.robots_parser = robots_parser

    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        can_parse = await respect_robots(kwargs.get('base_url'), url, self.ua_provider.random, self.robots_parser)

        if not can_parse:
            return None

        accept = kwargs.get('accept', 'text/html')
        headers = {
            "User-Agent": self.ua_provider.random,
            "Accept": accept
        }

        try:
            log.info(f"HttpContentFetcher: Fetching Content from {url}")
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            log.error(f"Error fetching {url}: {e}")
            return None


class SeleniumContentFetcher(ContentFetcher):
    """
    Fetches content via Selenium/browser.
    """

    def __init__(self, browser_manager, user_agent_provider, robots_parser):
        self.robots_parser = robots_parser
        self.browser_manager = browser_manager
        self.ua_provider = user_agent_provider

    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        can_parse = await respect_robots(kwargs.get('base_url'), url, self.ua_provider.random, self.robots_parser)

        if not can_parse:
            return None

        try:
            driver = await self.browser_manager.create_browser()
            driver.get(url)
            await asyncio.sleep(10) #wait for content to load

            log.info(f"HttpContentFetcher: Fetching Content (driver) for {url}")
            return driver

        except Exception as e:
            log.error(f"Error fetching with Selenium {url}: {e}")
            try:
                await self.browser_manager.close_tab()
            except:
                pass
            return None


class DownloadFetcher(ContentFetcher):
    """
    Fetches content via HTTP.
    """

    def __init__(self, session, user_agent_provider):
        self.session = session
        self.ua_provider = user_agent_provider

    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        accept = kwargs.get('accept', 'text/csv')
        headers = {
            "User-Agent": self.ua_provider.random,
            "Accept": accept
        }

        response = None
        try:
            log.info(f"DownloadFetcher: fetching content from {url}")
            # If page is no longer accessible download should not work
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            return content
        except Exception as e:

            log.error(f"(Download Parser) Error fetching : {url}: {e}")
            return None

# may want to add use_thread: bool if number of instances of fetcher is more then cpu cores
class AirtableSeleniumFetcher(ContentFetcher):
    """
    Fetches CSV data from Airtable by clicking download button and reading file.
    """

    def __init__(self, browser_manager):
        self.browser_manager = browser_manager

    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        """
        Fetch CSV content by clicking Airtable's download button.
        """
        wait_time = 10
        download_dir = None
        driver = None
        try:
            log.info(f"(Airtable Selenium) Opening browser for: {url[:75]}...")

            download_dir = self._create_download_dir()

            # Open page
            driver = await self.browser_manager.create_browser(
                download_dir=download_dir
            )

            driver.get(url)

            # Wait for page to load
            log.info(f"(Airtable Selenium) Waiting {wait_time} seconds for page load...")
            await asyncio.sleep(wait_time)

            log.info(f"(Airtable Selenium) Page title: {driver.title}")

            # Click through UI to download CSV
            csv_content = await self._download_csv(driver, download_dir)

            # Cleanup
            await self.cleanup(driver, download_dir)

            return csv_content

        except Exception as e:
            log.error(f"(Airtable Selenium) Error fetching: {url}: {e}")
            import traceback
            log.error(traceback.format_exc())
            if driver:
                await self.cleanup(driver, download_dir)
            return None

    async def _download_csv(self, driver, download_dir) -> Optional[Any]:
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
            if not await self._click_menu_button(driver):
                return None

            # Step 2: Click Download button
            if not await self._click_download_csv_button(driver):
                return None

            # Step 3: Wait for file and read content
            csv_content = await self._wait_and_read_file(download_dir)

            return csv_content

        except Exception as e:
            log.error(f"(Airtable Selenium) Download failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            return None

    async def _click_menu_button(self, driver) -> bool:
        """
        Click the 3-dot menu button (More view options).
        """
        log.info("(Airtable Selenium) Looking for 3-dot menu button...")
        try:
            # Look for menu button in both French and English
            menu_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, 'viewMenuButton')]")
                )
            )
            log.info("(Airtable Selenium) Found menu button! Clicking...")
            menu_button.click()

            # Wait for menu to appear
            log.info("(Airtable Selenium) Waiting 2 seconds for menu to appear...")
            await asyncio.sleep(2)

            return True

        except Exception as e:
            log.error(f"(Airtable Selenium) Failed to click menu button: {e}")
            return False

    async def _click_download_csv_button(self, driver) -> bool:
        """
        Click the "Download CSV" button in the menu (single button version).
        """
        log.info("(Airtable Selenium) Looking for 'Download CSV' button...")
        try:
            # Debug: Show available menu items
            try:
                menu_items = driver.find_elements(
                    By.XPATH,
                    "//button[contains(@role, 'menuitem')] | //div[@role='menuitem']"
                )
                if menu_items:
                    log.info(f"(Airtable Selenium) Found {len(menu_items)} menu items")
                    for i, item in enumerate(menu_items[:15]):
                        text = item.text.strip()
                        if text:
                            log.info(f"  {i}: {text}")
            except:
                pass

            # Find and click "Download CSV" button (French or English)
            # Look for exact text or aria-label
            download_csv_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//*[contains(text(), 'Download') or contains(text(), 'Télécharger')]")
                )
            )
            log.info("(Airtable Selenium) Found 'Download' button! Clicking...")
            download_csv_btn.click()

            # Brief wait after click
            await asyncio.sleep(10)

            return True

        except Exception as e:
            log.error(f"(Airtable Selenium) Failed to click 'Download CSV' button: {e}")
            return False

    async def _wait_and_read_file(self, download_dir) -> Optional[str]:
        """
        Wait for CSV file to be downloaded and read its content.

        Args:
            timeout: Maximum seconds to wait for download
        """
        log.info(f"(Airtable Selenium) downloading")
        import os

        await asyncio.sleep(30)

        files = os.listdir(download_dir)
        csv_files = [f for f in files if f.endswith('.csv') and not f.endswith('.crdownload')]

        if csv_files:
            csv_file = csv_files[0]
            log.info(f"(Airtable Selenium) SUCCESS! Downloaded: {csv_file}")

            # Read file content
            csv_path = os.path.join(download_dir, csv_file)

            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Delete the file
                os.remove(csv_path)
                log.info(f"(Airtable Selenium) Cleaned up downloaded file")

                return content

            except Exception as e:
                log.error(f"(Airtable Selenium) Failed to read file: {e}")
                return None

        log.error(f"(Airtable Selenium) Files in download directory: {files}")
        return None

    async def cleanup(self, driver, download_dir) -> None:
        """
        Cleanup driver
        """
        # Close browser
        if driver:
            try:
                await self.browser_manager.close_browser(driver)
            except:
                pass

        if download_dir:
            try:
                import shutil
                shutil.rmtree(download_dir, ignore_errors=True)
                log.info(f"(Airtable Fetcher) Cleaned up download directory")
            except Exception as e:
                log.warning(f"Failed to remove {download_dir}: {e}")

    def _create_download_dir(self) -> str:
        """Create and return download directory path"""
        import tempfile
        import time
        download_dir = tempfile.mkdtemp(prefix=f'downloads_{int(time.time() * 1000)}_')
        log.info(f"(Airtable Fetcher) Download directory: {download_dir}")
        return download_dir