from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, TYPE_CHECKING, Dict

from seleniumwire import webdriver
from selenium_stealth import stealth

from src.core.logs import Logger, APP
from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager
from src.core.parser.components.fetchers.components.browser.exceptions.not_configured_exception import ProxyBrowsersNotConfigured
from src.core.services.resources.proxy_service.exceptions.Invalid_number_of_proxies import InvalidNumberOfProxies
from src.core.services.resources.proxy_service.formatter.proxy_formatter import SeleniumWireProxyFormatter

if TYPE_CHECKING:
    from src.core.services.resources.proxy_service.proxy import Proxy
    from src.core.services.resources.proxy_service.proxy_manager import ProxyManager

LOGGER = Logger(APP)

class ProxyBrowserManager(BrowserManager, Proxy):

    def __init__(
            self,
            proxy_manager: ProxyManager,
            proxy_formatter: SeleniumWireProxyFormatter,
            headless: bool = True,
            max_browser_instances: int = 2,
            download_dir: Optional[str] = None,
            **kwargs
    ):
        super().__init__(
            headless=headless,
            max_browser_instances=max_browser_instances,
            download_dir=download_dir,
            proxy_manager=proxy_manager,
            proxy_formatter=proxy_formatter,
            **kwargs
        )

        self._configured = False

    def _create_browser(
            self,
            download_dir: Optional[str],
            proxy: Dict[str, str] = None,
            **kwargs
    ) -> webdriver.Chrome:
        """
        Create a browser with proxy and return the driver.
        """

        try:
            chrome_options = self._get_options(self._headless, download_dir=download_dir)

            driver = webdriver.Chrome(
                options=chrome_options,
                seleniumwire_options={
                    'proxy': proxy,
                }
            )

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

    async def configure_proxies(self, proxies: List[str]) -> None:
        if len(proxies) != self._max_browser_instances:
            raise

        proxies = self.proxy_formatter.apply_format(proxies)

        tasks = []

        for i in range(self._max_browser_instances):
            tasks.append(self._loop.run_in_executor(None, lambda: self._create_browser(
                download_dir=f"{self._download_dir}_{i}" if self._download_dir else None,
                proxy=proxies[i]))) # type: ignore  (the formatter should return the right type)

        drivers = await asyncio.gather(*tasks)

        for i, driver in enumerate(drivers):
            self._driver_to_idx[driver] = i
            self._drivers.append(driver)
            await self._browser_queue.put(driver)

        self._configured = True

        LOGGER.info(f"(BrowserManager) Successfully configured proxies: {self._max_browser_instances}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._configured:
            await super().__aexit__(exc_type, exc_val, exc_tb)
            LOGGER.info("(BrowserManager) Closed")

    @asynccontextmanager
    async def get_driver(self):
        if not self._configured:
            raise ProxyBrowsersNotConfigured("Proxy Manager not configured")

        driver = await self._browser_queue.get()

        try:
            yield driver
        finally:
            await self.proxy_manager.request_new_proxy(self, driver=driver)

    async def get_persistent_driver(self) -> webdriver.Chrome:
        if not self._configured:
            raise ProxyBrowsersNotConfigured("Proxy Manager not configured")

        return await super().get_persistent_driver() # type: ignore

    async def resolve_persistent_driver(self, driver: webdriver.Chrome):
        if not self._configured:
            raise ProxyBrowsersNotConfigured("Proxy Manager not configured")

        await self.proxy_manager.request_new_proxy(self, driver=driver)

    async def change_proxy(self, proxies: str | list[str], driver: webdriver.Chrome = None) -> None:
        if isinstance(proxies, list):
            LOGGER.warning(f"(BrowserManager) Change proxies: {proxies}, required: 1")
            raise InvalidNumberOfProxies("Invalid number of proxies")

        LOGGER.info(f"(BrowserManager) changing proxies")

        directory = self.get_download_directory(driver)

        driver.proxy = self.proxy_formatter.apply_format(proxies)

        await self._loop.run_in_executor(None, lambda: self._clear_dir(directory))

        await self._browser_queue.put(driver)

    def type_required(self) -> type[str | list]:
        return str

    def number_of_proxies_needed(self):
        return 1