import asyncio
import atexit
import random
import yaml
import sys
from typing import Dict, Optional

from fake_useragent import UserAgent

from Database.notion import NotionDatabase, MessageBus
import logs.logger as log

from net.shared_browser_manager import SharedBrowserManager
from net.http_client import Session
from parsers.base_parser import BaseParser

from parsers.factory import ParserFactory
from processing.tracker import Tracker

'''
PARSER TYPES (now cleaner!)
    - "DOWNLOAD"         → HTTP CSV download
    - "SEL_DOWNLOAD" → Airtable Selenium download
    - "STATIC"           → Static HTML parsing
    - "JS"               → JavaScript-rendered content
'''

TIMEOUT_3HOURS = 3 * 60 * 60
TIMEOUT_24HOURS = 24 * 60 * 60

def verify(websites: dict):
    """
    Verify website configuration.
    """
    for website_name, website_config in websites.items():
        if not website_config.get('url'):
            print(f"Warning: No url found for {website_name}")
            sys.exit()

        if not website_config.get('date_format'):
            print(f"Warning: No date_format found for {website_name}")
            sys.exit()

        if not website_config.get('parser_type'):
            print(f"Warning: No parser_type found for {website_name}")
            sys.exit()

        if website_config.get('parser_type').upper() not in ['DOWNLOAD', 'SEL_DOWNLOAD']:
            if not website_config.get('base_url'):
                print(f"Warning: No base_url found for {website_name}")
                sys.exit()

        if website_config.get('parser_type').upper() in ['DOWNLOAD', 'SEL_DOWNLOAD']:
            if not website_config.get('accept'):
                print(f"Warning: No accept found for {website_name}")
                sys.exit()

        if not website_config.get('selectors', {}):
            print(f"Warning: No selectors found for {website_name}")
            sys.exit()


class Manager:
    """
    Manages parser lifecycle and coordination.
    """

    def __init__(
            self,
            websites_file='websites.yaml',
            test_flag=False
    ):
        self.websites_file = websites_file
        self.running = False
        self.clearing_flag = False
        self.tasks = {}  # website_name : asyncio.Task
        self.bus = MessageBus()
        self.test_flag = test_flag
        self.active_count = 0

        # Create parsers using factory
        self.parsers = self._create_parsers()

    def _create_parsers(self) -> Dict[str, 'BaseParser']:
        """
        Create all parser instances using the factory.
        """
        session = Session()
        tracker = Tracker()
        browser_manager = SharedBrowserManager()
        user_agent_provider = UserAgent()
        parser_factory = ParserFactory(session, user_agent_provider, browser_manager, tracker, True)

        return {
            'DOWNLOAD': parser_factory.create_download_parser(),
            'SEL_DOWNLOAD': parser_factory.create_selenium_download_parser(),
            'STATIC': parser_factory.create_static_parser(),
            'JS': parser_factory.create_js_parser()
        }

    @classmethod
    def set_global_instance(cls, instance):
        """Set the global manager instance for cleanup."""
        global _manager_instance
        _manager_instance = instance

    def _process_websites(self):
        """
        Load and validate website configuration.
        """
        with open(self.websites_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        websites = config['websites']
        verify(websites)

        return websites

    def _create_website_parsers(self):
        """
        Create parser tasks for each website.

        Returns:
            List of asyncio tasks
        """
        websites = self._process_websites()
        tasks = []

        for website_name, website_config in websites.items():
            parser_type = website_config.get('parser_type').upper()

            # Get parser instance (already created)
            parser = self.parsers.get(parser_type)

            if not parser:
                log.warning(f"Unknown parser type: {parser_type} for {website_name}")
                continue

            # Determine timeout
            if parser_type in ['DOWNLOAD', 'SEL_DOWNLOAD']:
                timeout = TIMEOUT_24HOURS
            else:
                timeout = TIMEOUT_3HOURS

            # Create task
            if self.test_flag:
                task = asyncio.create_task(
                    self.test_process(parser, website_config, timeout),
                    name=f"parser-{website_name}"
                )
            else:
                task = asyncio.create_task(
                    self._process(parser, website_config, timeout),
                    name=f"parser-{website_name}"
                )

            self.tasks[website_name] = task
            tasks.append(task)

        return tasks

    async def _process(self, parser, config, timeout):
        """
        Main processing loop for a website.
        """
        sleep = False
        while self.running:
            if sleep:
                log.info(f'SLEEPING: {config["url"]}')
                offset = random.randint(-45 * 60, 45 * 60)  # ±45 min
                await asyncio.sleep(timeout + offset)
                sleep = False

            while self.clearing_flag:  # if database is still being cleared wait
                await asyncio.sleep(12 * 60)  # 12 min

            self.active_count += 1
            try:
                result = await parser.parse(config)

                if result is None:
                    sleep = True
                    continue

                await self.bus.publish(result)
            finally:
                self.active_count -= 1

            if self.active_count == 0:
                while not self.bus.queue.empty():
                    await asyncio.sleep(5 * 60)  # 5 min

                self.clearing_flag = True
                log.info(f'CLEARING: duplicates')
                await NotionDatabase().clear_duplicates()
                log.info(f'FINISH CLEARING: duplicates')
                self.clearing_flag = False

            offset = random.randint(-45 * 60, 45 * 60)  # ±45 min
            await asyncio.sleep(timeout + offset)

    async def test_process(self, parser, config, timeout):
        """
        test processing loop (no duplicate clearing).
        """
        sleep = False
        while self.running:
            if sleep:
                offset = random.randint(-45 * 60, 45 * 60)  # ±45 min
                await asyncio.sleep(timeout + offset)
                sleep = False

            self.active_count += 1
            try:
                result = await parser.parse(config)

                if result is None:
                    sleep = True
                    continue

                await self.bus.publish(result)
            finally:
                self.active_count -= 1

            break

    async def is_idle(self) -> bool:
        """
        Check if manager is idle.
        """
        while not self.bus.queue.empty():
            await asyncio.sleep(1)
        return self.active_count == 0

    async def start(self):
        """
        Start all parser tasks.
        """
        if not self.running:
            self.running = True
            tasks = self._create_website_parsers()

            if not tasks:
                print("No valid parser tasks created")
                return

            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                pass
            finally:
                await self.stop()

    async def stop(self):
        """
        Stop all parser tasks.
        """
        print("Stopping all parser tasks...")
        if not self.running:
            return

        self.running = False

        # Cancel all running tasks
        for website_name, task in self.tasks.items():
            if not task.done():
                print(f"Cancelling task for {website_name}")
                task.cancel()

        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

_manager_instance = None

async def cleanup():
    """Cleanup on shutdown"""
    if _manager_instance:
        await _manager_instance.stop()


def shutdown_handler():
    """Handle shutdown gracefully"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

atexit.register(shutdown_handler)