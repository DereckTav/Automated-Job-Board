import asyncio
import os
import shutil
import tempfile
from asyncio import Queue
from contextlib import asynccontextmanager
from typing import Optional, Any

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

from src.core.logs import Logger

LOGGER = Logger('app')

class BrowserManager:
    def __init__(
            self,
            headless: bool = True,
            max_browser_instances: int = 2,
            download_dir: Optional[str] = None,
            **kwargs
    ):
        super().__init__(**kwargs)

        self._headless = headless
        self._max_browser_instances = max_browser_instances
        self._download_dir = download_dir

        self._loop = asyncio.get_event_loop()

        self._drivers = []
        self._driver_to_idx = {}

        self._browser_queue = Queue(maxsize=self._max_browser_instances)

        LOGGER.info("(BrowserManager) Initialized")

    @staticmethod
    def _get_options(headless, download_dir: Optional[str]) -> Options:
        chrome_options = Options()
        ua = UserAgent()

        # --- stealth / identity ---
        chrome_options.add_argument(f'--user-agent={ua.random}')
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # --- performance ---
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--force-device-scale-factor=1")

        # --- Automation Bypass ---
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User data directory
        user_data_dir = tempfile.mkdtemp(prefix='browser_')
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        # configure downloads
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "profile.default_content_settings.popups": 0
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # might add proxy rotation
        # chrome_options.add_argument(f'--proxy-server={proxy_ip_port}')

        return chrome_options

    def _create_browser(
            self,
            download_dir: Optional[str],
            **kwargs: Any
    ) -> webdriver.Chrome:
        """
        Create a browser and return the driver.
        """

        try:
            chrome_options = self._get_options(self._headless, download_dir=download_dir)

            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(300) # 5 mins

            stealth(driver,
                    languages=["en-US", "en"], # type: ignore
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                    webdriver=False
                    )

            return driver

        except Exception as e:
            LOGGER.error(f"(BrowserManager) Failed to create browser: {e}")
            raise

    # maybe later add timer, for now the page load should handle some of the responsibility of ending this resource
    async def get_persistent_driver(self) -> webdriver.Chrome:
        '''
        make sure to resolve the persistent driver
        '''
        driver = await self._browser_queue.get()
        return driver

    async def resolve_persistent_driver(self, driver: webdriver.Chrome):
        await self._browser_queue.put(driver)

    @asynccontextmanager
    async def get_driver(self):
        driver = await self._browser_queue.get()

        try:
            yield driver
        finally:
            if self._download_dir is not None:
                idx = self._driver_to_idx[driver]
                directory = f"{self._download_dir}_{idx}" if self._download_dir else None
                await self._loop.run_in_executor(None, self._clear_dir(directory)) # type: ignore

            await self._browser_queue.put(driver)

    async def __aenter__(self):
        for i in range(self._max_browser_instances):
            driver = self._create_browser(download_dir=f"{self._download_dir}_{i}" if self._download_dir else None)
            self._drivers.append(driver)
            self._driver_to_idx[driver] = i
            await self._browser_queue.put(driver)

        LOGGER.info(f'(BrowserManager) {self._max_browser_instances} Browsers created')

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        LOGGER.info(f'(BrowserManager) closed')

    async def close(self):
        await self._cleanup_directories()
        await self._cleanup_drivers()

    @staticmethod
    def _clear_dir(directory: str):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # Deletes file or symlink
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Deletes subdirectory
            except Exception as e:
                LOGGER.error("(BrowserManager) Failed to clean up directory '%s'" % file_path)
                pass

    async def _clear_directories(self) -> None:
        if self._download_dir is None:
            return

        task = []

        for i in range(self._max_browser_instances):
            directory = f"{self._download_dir}_{i}"
            task.append(self._loop.run_in_executor(None, lambda: self._clear_dir(directory=directory))) # type: ignore

        await asyncio.gather(*task)

        LOGGER.info(f'(BrowserManager) Cleared directories')


    async def _cleanup_directories(self):
        if self._download_dir is None:
            return

        tasks = []

        for i in range(self._max_browser_instances):
            tasks.append(self._loop.run_in_executor(None, lambda: shutil.rmtree(
                f"{self._download_dir}_{i}",
                ignore_errors=True)) # type: ignore
            )

        await asyncio.gather(*tasks)

        LOGGER.info(f'(BrowserManager) cleaned up directories')

    async def _cleanup_drivers(self):
        for driver in self._drivers:
            try:
                driver.quit()
            except:
                pass

        self._drivers.clear()

        LOGGER.info(f'(BrowserManager) cleaned up drivers')