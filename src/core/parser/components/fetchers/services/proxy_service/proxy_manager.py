from __future__ import annotations

import asyncio
import tempfile
import time
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Optional

from src.core.logs import Logger
from src.core.parser.components.fetchers.components.session.aioproxy import AioProxy
from src.core.parser.components.fetchers.services.proxy_service.formatter.proxy_formatter import BasicProxyFormatter, \
    SeleniumWireProxyFormatter
from src.core.parser.components.fetchers.services.resource_management import ResourceManager

if TYPE_CHECKING:
    from src.core.parser.components.fetchers.services.proxy_service.proxy import Proxy
    from src.core.parser.components.fetchers.components.browser.proxy_browser_manager import ProxyBrowserManager

LOGGER = Logger('app')

class ProxyManager(ResourceManager):

    def __init__(self):
        self._stack = AsyncExitStack()
        self._loop = asyncio.get_event_loop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._stack.aclose()

    async def request_new_proxy(self, proxy_obj: Proxy, **kwargs):
        required_type = proxy_obj.type_required()

        if isinstance(required_type, list):
            new_proxies = []
        else:
            new_proxies = ""

        await proxy_obj.change_proxy(new_proxies, **kwargs)

    async def get_session(self):
        proxy = ""
        return AioProxy(proxy=proxy, proxy_manager=self, proxy_formatter=BasicProxyFormatter())

    async def get_browser_manager(self,
        headless: bool = True,
        max_browser_instances: int = 2,
        use_download_dir: Optional[bool] = False
    ):
        download_dir = None
        if use_download_dir:
            download_dir = await self._loop.run_in_executor(None, lambda: tempfile.mkdtemp(
                prefix=f'downloads_{int(time.time() * 1000)}'
            )) # type: ignore

        pbm = await self._stack.enter_async_context(ProxyBrowserManager(
            proxy_manager=self,
            proxy_formatter=SeleniumWireProxyFormatter(),
            headless=headless,
            max_browser_instances=max_browser_instances,
            download_dir=download_dir
        ))

        #TODO finish implementing algorithms

        await pbm.configure_proxies()

        '''
proxy_list = [
    {'http': '103.160.150.251:8080', 'https': '103.160.150.251:8080'},
    {'http': '38.65.174.129:80', 'https': '38.65.174.129:80'},
    {'http': '46.105.50.251:3128', 'https': '46.105.50.251:3128'},
    {'http': '103.23.199.24:8080', 'https': '103.23.199.24:8080'},
    {'http': '223.205.32.121:8080', 'https': '103.23.199.24:8080'}
]

        # create a proxy list and add your authentication credentials
proxy_list = [
    {
        'http': 'http://<YOUR_USERNAME>:<YOUR_PASSWORD>@192.168.10.100:8001',
        'https': 'https://<YOUR_USERNAME>:<YOUR_PASSWORD>@192.168.10.100:8001'
    },

    {
        'http': 'http://<YOUR_USERNAME>:<YOUR_PASSWORD>@134.796.13.101:8888',
        'https': 'https://<YOUR_USERNAME>:<YOUR_PASSWORD>@145.796.13.101:8888',
    },

    # ... more proxies
]


# configure the proxy
proxy_username = "<ZENROWS_PROXY_USERNAME>"
proxy_password = "<ZENROWS_PROXY_PASSWORD>"
proxy_address = "superproxy.zenrows.com"
proxy_port = "1337"

# formulate the proxy url with authentication
proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_address}:{proxy_port}"

# set selenium-wire options to use the proxy
seleniumwire_options = {
    "proxy": {"http": proxy_url, "https": proxy_url},
}
        '''