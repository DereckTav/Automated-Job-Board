import asyncio
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logs.logger as log


class SharedBrowserManager:
    """
    Singleton manager for a shared Selenium browser instance.
    All parsers use the same browser with different tabs/windows.
    Reduces memory and CPU usage significantly.
    """

    _instance = None
    _driver = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_driver(self):
        """Get or create the shared browser driver"""
        async with self._lock:
            if self._driver is None:
                await self._init_driver()
            return self._driver

    async def _init_driver(self):
        """Initialize the shared browser"""
        try:
            log.info("(SharedBrowser) Initializing shared browser instance...")

            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")

            # Create a unique user-data-dir
            user_data_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Set download preferences
            download_dir = tempfile.mkdtemp()
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.default_content_settings.popups": 0,
                "download.directory_upgrade": True
            }
            chrome_options.add_experimental_option("prefs", prefs)

            self._driver = await asyncio.to_thread(webdriver.Chrome, options=chrome_options)
            self._driver.set_page_load_timeout(30)
            self._driver.set_script_timeout(30)

            log.info("(SharedBrowser) Shared browser initialized successfully")
        except Exception as e:
            log.error(f"(SharedBrowser) Failed to initialize browser: {e}")
            raise

    async def open_tab(self, url: str):
        """Open a new tab and navigate to URL"""
        driver = await self.get_driver()
        try:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])

            # Navigate with timeout
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(driver.get, url),
                    timeout=30
                )
            except asyncio.TimeoutError:
                log.warning(f"(SharedBrowser) Page load timed out for {url[:50]}, continuing...")

            return driver
        except Exception as e:
            log.error(f"(SharedBrowser) Error opening tab: {e}")
            raise

    async def close_tab(self):
        """Close current tab"""
        driver = await self.get_driver()
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                log.info("(SharedBrowser) Tab closed")
        except Exception as e:
            log.error(f"(SharedBrowser) Error closing tab: {e}")

    async def quit(self):
        """Shutdown the shared browser"""
        async with self._lock:
            if self._driver:
                try:
                    await asyncio.to_thread(self._driver.quit)
                    log.info("(SharedBrowser) Shared browser shut down")
                except Exception as e:
                    log.error(f"(SharedBrowser) Error shutting down browser: {e}")
                finally:
                    self._driver = None

    def configure_downloads(self, download_dir: str):
        """
        Configure browser to download files to specified directory.

        Call this BEFORE opening any tabs.
        """
        if not hasattr(self, '_download_dir'):
            self._download_dir = download_dir

            # If using Chrome
            if hasattr(self, 'options'):
                prefs = {
                    "download.default_directory": download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                }
                self.options.add_experimental_option("prefs", prefs)
                log.info(f"(Browser Manager) Configured downloads to: {download_dir}")