import asyncio
import tempfile
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import logs.logger as log


class BrowserManager:
    """
    Simple browser manager - just tracks browsers for cleanup.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._browsers: Dict[str, webdriver.Chrome] = {}  # browser_id -> driver
            self._lock = asyncio.Lock()
            self._creation_semaphore = asyncio.Semaphore(2) # max 2 browser at a time
            BrowserManager._initialized = True
            log.info("(BrowserManager) Initialized")

    async def create_browser(
            self,
            download_dir: Optional[str] = None,
            headless: bool = True
    ) -> webdriver.Chrome:
        """
        Create a browser and return the driver.

        Returns:
            driver - use it however you want
        """
        async with self._creation_semaphore:
            try:
                chrome_options = Options()

                if headless:
                    chrome_options.add_argument("--headless")

                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--disable-plugins")
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")

                # User data directory
                user_data_dir = tempfile.mkdtemp(prefix='browser_')
                chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)

                # Configure downloads if needed
                if download_dir:
                    prefs = {
                        "download.default_directory": download_dir,
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "profile.default_content_settings.popups": 0
                    }
                    chrome_options.add_experimental_option("prefs", prefs)

                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(300)
                driver.set_script_timeout(300)

                # Track it
                async with self._lock:
                    browser_id = str(id(driver))
                    self._browsers[browser_id] = driver

                log.info(f"(BrowserManager) Created browser {browser_id}")
                return driver

            except Exception as e:
                log.error(f"(BrowserManager) Failed to create browser: {e}")
                raise

    async def close_browser(self, driver: webdriver.Chrome):
        """
        Close a specific browser.
        """
        try:
            browser_id = str(id(driver))

            driver.quit()

            async with self._lock:
                self._browsers.pop(browser_id, None)

            log.info(f"(BrowserManager) Closed browser {browser_id}")

        except Exception as e:
            log.error(f"(BrowserManager) Error closing browser: {e}")

    async def close_all_browsers(self):
        """
        Close ALL browsers.
        """
        log.info(f"(BrowserManager) Closing {len(self._browsers)} browser(s)...")

        async with self._lock:
            drivers = list(self._browsers.values())
            self._browsers.clear()

        for driver in drivers:
            try:
                driver.quit()
            except Exception as e:
                log.error(f"(BrowserManager) Error closing browser: {e}")

        log.info("(BrowserManager) All browsers closed")
