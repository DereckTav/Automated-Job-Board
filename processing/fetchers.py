from interfaces.content import  ContentFetcher
from typing import Optional, Any, List
import asyncio

from interfaces.robots import RobotsParser
from logs import logger as log


async def respect_robots(base_url: str, url: str, user_agent: str, robots_parser: RobotsParser) -> bool:
    # Check robots.txt
    rules = await robots_parser.get_rules(url, base_url, user_agent)

    if not rules.can_fetch:
        import logs.logger as log
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
            driver = await self.browser_manager.open_tab(url)
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
            # If page is no longer accessible download should not work
            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

            return content
        except Exception as e:
            import logs.logger as log
            log.error(f"(Download Parser) Error fetching : {url}: {e}")
            return None

# may want to add use_thread: bool if number of instances of fetcher is more then cpu cores
class AirtableSeleniumFetcher(ContentFetcher):
    """
    Fetches CSV data from Airtable by clicking download button and reading file.
    """

    def __init__(self, browser_manager, download_dir: Optional[str] = None):
        self.browser_manager = browser_manager

        import tempfile
        self.download_dir = download_dir or tempfile.mkdtemp(prefix='downloads_')

        self._current_driver = None
        self._cleanup_download_dir = download_dir is None  # Only cleanup if we created it

        log.info(f"(Airtable Fetcher) Download directory: {self.download_dir}")

    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        """
        Fetch CSV content by clicking Airtable's download button.
        """
        wait_time = kwargs.get('wait_time', 10)

        try:
            log.info(f"(Airtable Selenium) Opening tab for: {url[:75]}...")

            # Open page
            self.browser_manager.configure_downloads(self.download_dir)
            self._current_driver = await self.browser_manager.open_tab(url)

            # Wait for page to load
            log.info(f"(Airtable Selenium) Waiting {wait_time} seconds for page load...")
            await asyncio.sleep(wait_time)

            log.info(f"(Airtable Selenium) Page title: {self._current_driver.title}")

            # Click through UI to download CSV
            csv_content = await self._download_csv()

            # Cleanup
            await self.cleanup()

            return csv_content

        except Exception as e:
            log.error(f"(Airtable Selenium) Error fetching: {url}: {e}")
            import traceback
            log.error(traceback.format_exc())
            await self.cleanup()
            return None

    async def _download_csv(self) -> Optional[Any]:
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
            if not await self._click_menu_button():
                return None

            # Step 2: Click Download button
            if not await self._click_download_csv_button():
                return None

            # Step 3: Wait for file and read content
            csv_content = await self._wait_and_read_file()

            return csv_content

        except Exception as e:
            log.error(f"(Airtable Selenium) Download failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            return None

    async def _click_menu_button(self) -> bool:
        """
        Click the 3-dot menu button (More view options).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        log.info("(Airtable Selenium) Looking for 3-dot menu button...")
        try:
            # Look for menu button in both French and English
            menu_button = WebDriverWait(self._current_driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR,
                     "div[aria-label='Plus d\\'options de vue'], "
                     "div[aria-label='More view options']")
                )
            )
            log.info("(Airtable Selenium) Found menu button! Clicking...")
            await asyncio.to_thread(menu_button.click)

            # Wait for menu to appear
            log.info("(Airtable Selenium) Waiting 2 seconds for menu to appear...")
            await asyncio.sleep(2)

            return True

        except Exception as e:
            log.error(f"(Airtable Selenium) Failed to click menu button: {e}")
            return False

    async def _click_download_csv_button(self) -> bool:
        """
        Click the "Download CSV" button in the menu (single button version).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        log.info("(Airtable Selenium) Looking for 'Download CSV' button...")
        try:
            # Debug: Show available menu items
            try:
                menu_items = self._current_driver.find_elements(
                    By.XPATH,
                    "//button[@role='menuitem'] | //div[@role='menuitem']"
                )
                if menu_items:
                    log.info(f"(Airtable Selenium) Found {len(menu_items)} menu items")
                    for i, item in enumerate(menu_items[:10]):
                        text = item.text.strip()
                        if text:
                            log.info(f"  {i}: {text}")
            except:
                pass

            # Find and click "Download CSV" button (French or English)
            # Look for exact text or aria-label
            download_csv_btn = WebDriverWait(self._current_driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//button[contains(text(), 'Download CSV') or "
                     "contains(text(), 'Télécharger CSV') or "
                     "contains(text(), 'Download csv') or "
                     "contains(@aria-label, 'Download CSV') or "
                     "contains(@aria-label, 'Télécharger CSV')]")
                )
            )
            log.info("(Airtable Selenium) Found 'Download CSV' button! Clicking...")
            await asyncio.to_thread(download_csv_btn.click)

            # Brief wait after click
            await asyncio.sleep(1)

            return True

        except Exception as e:
            log.error(f"(Airtable Selenium) Failed to click 'Download CSV' button: {e}")
            return False

    async def _wait_and_read_file(self, timeout: int = 60) -> Optional[str]:
        """
        Wait for CSV file to be downloaded and read its content.

        Args:
            timeout: Maximum seconds to wait for download
        """
        log.info(f"(Airtable Selenium) Waiting up to {timeout} seconds for download...")

        # Get initial files
        initial_files = set(self._get_csv_files())

        import time
        import os

        start_time = time.time()
        while time.time() - start_time < timeout:
            await asyncio.sleep(1)

            current_files = set(self._get_csv_files())
            new_files = current_files - initial_files

            if new_files:
                csv_file = list(new_files)[0]
                log.info(f"(Airtable Selenium) SUCCESS! Downloaded: {csv_file}")

                # Read file content
                csv_path = os.path.join(self.download_dir, csv_file)

                try:
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # # Log preview
                    # lines = content.split('\n')[:3]
                    # log.info(f"(Airtable Selenium) CSV preview (first 3 lines):")
                    # for line in lines:
                    #     log.info(f"  {line[:100]}")

                    # Delete the file
                    os.remove(csv_path)
                    log.info(f"(Airtable Selenium) Cleaned up downloaded file")

                    return content

                except Exception as e:
                    log.error(f"(Airtable Selenium) Failed to read file: {e}")
                    return None

        # Timeout
        log.error(f"(Airtable Selenium) Download timed out after {timeout} seconds")
        files = os.listdir(self.download_dir)
        log.error(f"(Airtable Selenium) Files in download directory: {files}")
        return None

    def _get_csv_files(self) -> List[str]:
        """
        Get list of CSV files in download directory.

        Returns:
            List of CSV filenames
        """
        import os

        try:
            files = os.listdir(self.download_dir)
            return [f for f in files if f.endswith('.csv')]
        except Exception:
            return []

    async def cleanup(self):
        """
        Cleanup driver and optionally download directory.
        """
        # Close browser tab
        if self._current_driver:
            try:
                await self.browser_manager.close_tab()
            except:
                pass
            self._current_driver = None

        # Cleanup download directory if we created it
        if self._cleanup_download_dir:
            try:
                import shutil
                shutil.rmtree(self.download_dir, ignore_errors=True)
                log.info(f"(Airtable Fetcher) Cleaned up download directory")
            except:
                pass