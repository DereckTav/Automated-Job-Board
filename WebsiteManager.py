import asyncio
import atexit
import random

import yaml
import sys

from JobParser.parsers.js_parser import JavaScriptContentParser
from JobParser.parsers.static_parser import StaticContentParser
from JobParser.parsers.download_parser import DownloadParser
from JobParser.parsers.browser_download_parser import SeleniumDownloader
from JobParser.parsers.generic_parser import Parser

from Database.notion import NotionDatabase
from Database.notion import MessageBus

import logs.logger as log

'''
TYPES
    - "DOWNLOAD"
    - "JS"
    - "STATIC"
'''

TIMEOUT_3HOURS = 3 * 60 * 60
TIMEOUT_24HOURS = 24 * 60 * 60


def verify(websites: dict):
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

        if website_config.get('parser_type').upper() not in ['DOWNLOAD', 'BROWSER_DOWNLOAD']:
            if not website_config.get('base_url'):
                print(f"Warning: No base_url found for {website_name}")
                sys.exit()

        if website_config.get('parser_type').upper() in ['DOWNLOAD', 'BROWSER_DOWNLOAD']:
            if not website_config.get('accept'):
                print(f"Warning: No accept found for {website_name}")
                sys.exit()

        if not website_config.get('selectors', {}):
            print(f"Warning: No selectors found for {website_name}")
            sys.exit()

class Manager:
    _instance = None

    def __new__(cls, *args):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, websites_file='websites.yaml', test_flag=False):
        if not self._initialized:
            self.websites_file = websites_file
            self.running = False
            self.clearing_flag = False
            self.tasks = {}  # url : thread
            self.bus = MessageBus()
            self.test_flag = test_flag # for testing purposes

            self.static_parser = StaticContentParser()
            self.js_parser = JavaScriptContentParser()
            self.downloader = DownloadParser()
            self.sel_downloader = SeleniumDownloader()

            self.active_count = 0
            self._initialized = True

    def _process_websites(self):
        with open(self.websites_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        websites = config['websites']

        verify(websites)

        return websites

    def _create_website_parsers(self):
        websites = self._process_websites()
        tasks = []

        for website_name, website_config in websites.items():
            parser_type = website_config.get('parser_type').upper()


            if parser_type == 'STATIC':
                parser = self.static_parser
                timeout = TIMEOUT_3HOURS

            elif parser_type == 'JS':
                parser = self.js_parser
                timeout = TIMEOUT_3HOURS

            elif parser_type == 'DOWNLOAD':
                parser = self.downloader
                timeout = TIMEOUT_24HOURS

            elif parser_type == 'BROWSER_DOWNLOAD':
                parser = self.sel_downloader
                timeout = TIMEOUT_24HOURS

            else:
                continue

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

    async def _process(self, parser: Parser, config, timeout):
        sleep = False
        while self.running:
            if sleep:
                log.info(f'SLEEPING: {config['url']}')
                offset = random.randint(-45 * 60, 45 * 60)  # ±45 min
                await asyncio.sleep(timeout + offset)
                sleep = False

            while self.clearing_flag: # if database is still being cleared wait
                await asyncio.sleep(12 * 60) # 12 min

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
                    await asyncio.sleep(5 * 60) # 5 min (here time isn't important)

                self.clearing_flag = True
                log.info(f'CLEARING: duplicates')
                await NotionDatabase().clear_duplicates()
                log.info(f'FINISH CLEARING: duplicates')
                self.clearing_flag = False

            offset = random.randint(-45 * 60, 45 * 60)  # ±45 min
            await asyncio.sleep(timeout + offset)

    async def test_process(self, parser: Parser, config, timeout): #for testing - gets rid of clear_duplicates
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
        while not self.bus.queue.empty():
            await asyncio.sleep(1) # wait 1 second (here time is important, one reason is because of testing)
        return self.active_count == 0

    async def start(self):
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

async def cleanup():
    await Manager().stop()

def shutdown_handler():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

atexit.register(shutdown_handler)