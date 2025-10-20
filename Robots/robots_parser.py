import asyncio
import logging
from urllib.robotparser import RobotFileParser

from LocalData.cache import Cache
from Robots.robots import RobotsRules
from urllib.parse import urlparse

from pathlib import Path

# Get the directory where the current script lives
base_dir = Path(__file__).resolve().parent

# Create a logs directory if it doesn't exist
logs_dir = base_dir / "logs"
logs_dir.mkdir(exist_ok=True)

# Full path to the log file
log_file = logs_dir / "parser.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

class RobotsTxtParser:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance and not hasattr(cls, "_initialized"):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._robots_refresher = asyncio.create_task(self._refresh())
            self._cache = Cache()
            self._initialized = True

    async def get_rules(self, url: str, base_url: str, user_agent: str) -> RobotsRules:
        try:
            if base_url.endswith("/"):
                robots_url = base_url + 'robots.txt'

            else:
                robots_url = base_url + '/robots.txt'

            # Check cache first
            if self._cache.has(url):
                return self._cache.get(url)

            robot_parser = RobotFileParser()
            robot_parser.set_url(robots_url)
            robot_parser.read()

            can_fetch = await asyncio.to_thread(
                robot_parser.can_fetch,
                user_agent,
                url
            )

            crawl_delay = robot_parser.crawl_delay(user_agent) or 1.0

            rules = RobotsRules(
                can_fetch=can_fetch,
                crawl_delay=float(crawl_delay),
                user_agent=user_agent
            )

            self._cache.cache(url, rules)

            return rules

        except Exception:
            return RobotsRules(
                can_fetch=False,
                crawl_delay=1.0,
                user_agent=user_agent
            )

    async def _check(self, url: str, user_agent: str) -> bool:
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            if base_url.endswith("/"):
                robots_url = base_url + 'robots.txt'

            else:
                robots_url = base_url + '/robots.txt'

            robot_parser = RobotFileParser()
            robot_parser.set_url(robots_url)
            robot_parser.read()

            can_fetch = await asyncio.to_thread(
                robot_parser.can_fetch,
                user_agent,
                url
            )

            crawl_delay = robot_parser.crawl_delay(user_agent) or 1.0

            rules = RobotsRules(
                can_fetch=can_fetch,
                crawl_delay=float(crawl_delay),
                user_agent=user_agent
            )

            if rules.can_fetch:
                self._cache.cache(url, rules)
                return True

            return False

        except Exception:
            return False

    async def _refresh(self):
        try:
            while True:
                await asyncio.sleep(24 * 60 * 60) # every day

                urls_to_remove = []

                for url in list(self._cache.keys()):
                    user_agent = self._cache.get(url).user_agent
                    valid = await self._check(url, user_agent)
                    if not valid:
                        urls_to_remove.append(url)

                for url in urls_to_remove:
                    self._cache.pop(url)
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            logging.error("Cancelled robots refresher")
            raise