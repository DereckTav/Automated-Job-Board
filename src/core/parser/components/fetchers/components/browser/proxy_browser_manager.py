from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Union, TYPE_CHECKING

#TODO do I import both seleniumwire and selenium?
from selenium import webdriver
from seleniumwire import webdriver
from selenium_stealth import stealth

from src.core.logs import Logger
from src.core.parser.components.fetchers.components.browser.browser_manager import BrowserManager

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.services.proxy_service.proxy_manager import ProxyManager

LOGGER = Logger('app')

'''
        import tempfile
        download_dir = tempfile.mkdtemp(prefix=f'downloads_{int(time.time() * 1000)}_')
'''

# TODO finish tutorial to see if properly implemented
class ProxyBrowserManager(BrowserManager, Proxy):

    def __init__(
            self,
            proxy_manager: ProxyManager,
            headless: bool = True,
            max_browser_instances: int = 2,
            download_dir: Optional[str] = None,
    ):
        super().__init__(
            headless=headless,
            max_browser_instances=max_browser_instances,
            download_dir=download_dir,
            proxy_manager=proxy_manager
        )

        self._configured = False

    def _create_browser(
            self,
            download_dir: Optional[str],
            proxy: Optional[str] = None
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

            driver.set_page_load_timeout(300)

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

        tasks = []

        for i in range(self._max_browser_instances):
            tasks.append(self._loop.run_in_executor(None, lambda: self._create_browser(
                download_dir=f"{self._download_dir}_{i}" if self._download_dir else None,
                proxy=proxies[i])))

        drivers = await asyncio.gather(*tasks)

        for i, driver in enumerate(drivers):
            self._driver_to_idx[driver] = i
            self._drivers.append(driver)
            await self._browser_queue.put(driver)

        self._configured = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._configured:
            await super().__aexit__(exc_type, exc_val, exc_tb)

    @asynccontextmanager
    async def get_driver(self):
        if not self._configured:
            raise # error about driver not being a proxy

        driver = await self._browser_queue.get()

        try:
            yield driver
        finally:
            await self.proxy_manager.request_new_proxy(self, driver=driver)

    async def get_persistent_driver(self) -> webdriver.Chrome:
        if not self._configured:
            raise

        return await super().get_persistent_driver()

    async def resolve_persistent_driver(self, driver: webdriver.Chrome):
        if not self._configured:
            raise # error about driver not being a proxy

        await self.proxy_manager.request_new_proxy(self, driver=driver)

    async def change_proxy(self, proxies: Union[str, List[str]], driver: webdriver.Chrome = None) -> None:
        if isinstance(proxies, list):
            raise

        idx = self._driver_to_idx[driver]

        try:
            driver.quit()
        except:
            pass

        tasks = []

        directory = f"{self._download_dir}_{idx}" if self._download_dir else None

        tasks.append(self._loop.run_in_executor(None, lambda: self._create_browser(
            download_dir=directory,
            proxy=proxies
        )))

        tasks.append(self._loop.run_in_executor(None, lambda: self._clear_dir(directory)))

        new_driver, _ = await asyncio.gather(*tasks)

        self._drivers[idx] = new_driver
        await self._browser_queue.put(driver)

    def type_required(self) -> type[str | list]:
        return str