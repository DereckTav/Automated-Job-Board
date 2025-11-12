import asyncio
import atexit
import json
import time
from datetime import datetime, timedelta, timezone
import os
from typing import Optional, Dict, Any

from Database.util import batch_zip

import aiohttp
from net.http_client import Session
from parsers.output import Result

from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID")

API_ENDPOINT = 'https://api.notion.com/v1/pages'
QUERY_ENDPOINT = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"

TIMEOUT_2DAYS = 2 * 24 * 60 * 60  # 2 days

import logs.logger as log

cleaner_active = False

# MessageBus and Gateway Initialization Flow
# ==========================================
#
# This runs when MessageBus().publish() is called:
# 1. MessageBus is initialized
# 2. First .publish() call initializes Gateway
# 3. Gateway.run() is executed (can only run once)
# 4. .run() initializes: db = await NotionDatabase
#
# Reason:
# -----------------
# NotionDatabase initialization starts a coroutine for cleaning old database entries.
#
# I didn't want to require explicit `db = await NotionDatabase` calls just to start
# the cleaner. Since NotionDatabase isn't meant to be used directly—only through
# MessageBus()—I abstracted this as an implementation detail. This keeps the public
# API clean without initialization boilerplate.
#
# Trade-off: This abstraction is clever but less obvious. NotionDatabase is
# intentionally internal and only handles duplicate cleanup behind the scenes.
#
# Summary: Use MessageBus.publish() for all interactions. Don't interact with
# NotionDatabase or Gateway directly, except for clearing_duplicates

'''
# for page
["properties"]["Position"]["multi_select"][0]["name"] # position
["properties"]["Status"]["status"]["name"] # status
["properties"]["Company Size"]["multi_select"][0]["name"] # company_size
["properties"]["Application Link"]["url"] # url
["properties"]["Company Name"]["title"][0]["text"]["content"] # company_name
'''

async def cleanup():
    notion = NotionDatabase()
    if notion.database_cleaner is not None:
        notion.database_cleaner.cancel()
        try:
            await notion.database_cleaner
        except asyncio.CancelledError:
            log.info("Cleaner task was cancelled")
            pass

def shutdown_handler():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

class NotionDatabase:
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, '_initialized'):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.headers = {
               "Authorization": f"Bearer {NOTION_API_KEY}",
               "Content-Type": "application/json",
               "Notion-Version": "2025-09-03"
            }

            self.api_endpoint = API_ENDPOINT
            self.query_endpoint = QUERY_ENDPOINT

            self._database_cleaner = None

            self.session = Session()

            atexit.register(shutdown_handler)

            self._initialized = True

    def __await__(self):
        return self._initialize().__await__()

    async def _initialize(self):
        if not self._database_cleaner:
            self._database_cleaner = asyncio.create_task(self._run_cleaner())
        return self

    @staticmethod
    def _generate_body(
            company_name: str, position: str,
            url: Optional[str], job_description: Optional[str], company_size: Optional[str]
        ) -> Dict[str, Any]:

        """ Rich text object -- text.content -- 2000 characters -- (make sure description is under 2000 chars)
            Any URL -- 2000 characters -- if url is not under 2000 just leave domain
            title.text.content -- 2000 chars -- (Title (company name)) slice so its under 2000
            Max characters per option name -- 100 characters -- (position) (slice) """

        if position:
            position = (position.replace(",", " -")
                        .replace("，", " -")
                        .replace("、", " -"))

        body = {
            "parent": {
                "database_id": DATABASE_ID
            },
            "properties": {
                "Company Name": {
                    "title": [{"type": "text", "text": {"content": company_name[:2000]}}],
                },
                "Position": {
                    "multi_select": [{"name": position[:100]}],
                },
                "Status": {
                    "status": {"name": "Pending"}
                }
            }
        }

        if job_description:
            children = []
            for i in range(0, len(job_description), 2000):
                chunk = job_description[i:i + 2000]
                if chunk.strip():  # Only add non-empty chunks
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}]
                        }
                    })

            if children:
                body["children"] = children

        if company_size:
            company_size = company_size.replace(",", " -")
            body["properties"]["Company Size"] = {"multi_select": [{"name": company_size[:100]}]}

        if url:
            if len(url) > 2000 or not url:
                parsed = urlparse(url)
                url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

            body["properties"]["Application Link"] = {"url": url}

        return body

    # for testing
    async def _post_return_response(
            self, company_name: str, position: str,
            url: Optional[str], job_description: Optional[str], company_size: Optional[str]
        ) -> Optional[dict]:

        body = self._generate_body(company_name, position, url, job_description, company_size)

        try:
            async with self.session.post(self.api_endpoint, json=body, headers=self.headers) as response:
                response_data = await response.json()
                response.raise_for_status()
                return response_data

        except aiohttp.ClientResponseError as e:
            print(f"Notion API error {response.status} for {company_name}: {url}: stack trace: {e}, \n\n "
                          f"response:{json.dumps(response_data, indent=4)}")
            log.error(f"Notion API error {response.status} for {company_name}: {url}: stack trace: {e}, \n\n "
                          f"response:{json.dumps(response_data, indent=4)}")
            return None

        except Exception:
            log.error(f"Notion API error for {company_name}: {url} : exception {json.dumps(response_data, indent=4)}")
            return None

    async def _post(
            self, company_name: str,
            position: str,
            url: Optional[str],
            job_description: Optional[str],
            company_size: Optional[str],
            parser_type: Optional[str] = None,
        ) -> Optional[dict]:
        body = self._generate_body(company_name, position, url, job_description, company_size)

        try:
            async with self.session.post(self.api_endpoint, json=body, headers=self.headers) as response:
                response_data = await response.json()
                response.raise_for_status()
                return

        except aiohttp.ClientResponseError as e:
            message = f"Notion API error {response.status} for {company_name}: {url}: stack trace: {e}, \n\n"\
                      f" response: {json.dumps(response_data, indent=4)}"
            log.error(f"[[{parser_type}]]" + message if parser_type else message)

            await MessageBus().publish(
                Result(
                    position=position,
                    application_link=url,
                    company_name=company_name,
                    parser_type=parser_type,
                    company_size=company_size,
                    description=job_description
                )
            )

            return

        except Exception as e:
            log.error(f"Notion API error for {company_name}: {url} : exception {json.dumps(response_data, indent=4)}")
            return

    async def batch_post(self, *data: dict, parser_type: Optional[str] = None) -> float:
        global cleaner_active
        if len(data) > 3:
            raise ValueError("Expected at most 3 dictionaries")

        if not cleaner_active:
            start_time = time.time()

            tasks = [
                self._post(
                    company_name=item.get('company_name'),
                    position=item.get('position'),
                    url=item.get('application_link'),
                    job_description=item.get('description'),
                    company_size=item.get('company_size'),
                    parser_type=parser_type
                )
                for item in data
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            # call cycle (per second):
                # 3 calls (then another) -> 3 calls -> repeat

            # Calculate remaining time to reach 1 second
            elapsed = time.time() - start_time
            remaining = max(0.0, 1.0 - elapsed)
            return remaining

        else:
            tasks = [
                self._post(
                    company_name=data[i].get('company_name'),
                    position=data[i].get('position'),
                    url=data[i].get('application_link'),
                    job_description=data[i].get('description'),
                    company_size=data[i].get('company_size'),
                    parser_type=parser_type
                )
                for i in range(min(2, len(data)))
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(1)

            start_time = time.time()

            # Send the 3rd one
            if len(data) > 2:
                asyncio.create_task(self._post(
                    company_name=data[2].get('company_name'),
                    position=data[2].get('position'),
                    url=data[2].get('application_link'),
                    job_description=data[2].get('description'),
                    company_size=data[2].get('company_size'),
                    parser_type=parser_type
                ))

            #possible call cycles (per second):
                # 2 calls (then another) -> 1 call -> repeat
                # 3 calls (then another) -> 1 call -> repeat
                # 2 calls (then another) -> 2 calls -> repeat

            elapsed = time.time() - start_time
            remaining = max(0.0, 1.0 - elapsed)
            return remaining

    async def _query_database_2(self):
        try:
            async with self.session.post(self.query_endpoint, headers=self.headers) as response:
                response_data = await response.json()
                response.raise_for_status()
                return response_data.get("results", [])

        except Exception:
            log.error(f"Notion API error can't retrieve query : {json.dumps(response_data, indent=4)}")
            return None

    async def _query_database(self):
        results = []
        has_more = True
        start_cursor = None

        try:
            delay = 1.0 / 3 # rate limit

            while has_more:
                payload = {"page_size": 100}

                if start_cursor:
                    payload["start_cursor"] = start_cursor

                async with self.session.post(self.query_endpoint, headers=self.headers, json=payload) as response:
                    body = await response.json()

                    response.raise_for_status()

                    results.extend(body.get("results", []))
                    has_more = body.get("has_more", False)
                    start_cursor = body.get("next_cursor")

                await asyncio.sleep(delay)

            return results
        except Exception:
            log.error(f"Notion API error can't retrieve query : {json.dumps(body, indent=4)}")
            return None

    async def _delete_page(self, page_id):
        url = self.api_endpoint + f"/{page_id}"
        try:
            async with self.session.patch(url, headers=self.headers, json={"archived": True}) as response:
                response_data = await response.json()
                response.raise_for_status()
                return response_data

        except Exception:
            log.error(f"Notion API error can't delete page : {json.dumps(response_data, indent=4)}")
            return None

    async def _delete_old_entries(self, days=2):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        pages = await self._query_database()
        tasks = []

        for page in pages:
            date = page["properties"]["Created time"]["created_time"]
            page_date = datetime.fromisoformat(str(date))

            if page_date < cutoff:
                await asyncio.sleep(1) # rate limits this to 1 per second
                tasks.append(asyncio.create_task(self._delete_page(page["id"])))

        await asyncio.gather(*tasks,return_exceptions=True)

    async def _run_cleaner(self):
        global cleaner_active
        try:
            while True:
                cleaner_active = False
                log.info(f"Cleaner active: {cleaner_active}")
                await asyncio.sleep(TIMEOUT_2DAYS)

                cleaner_active = True
                log.info(f"Cleaner active: {cleaner_active}")
                await self._delete_old_entries()
        except asyncio.CancelledError:
            log.info("cleaner cancelled")
            raise

    async def clear_duplicates(self):
        """
        should only be ran after all sites are done being parsed
        """
        pages = await self._query_database()

        ids, company_names, positions = list(zip(*[(
            page["id"],
            page["properties"]["Company Name"]["title"][0]["text"]["content"],
            page["properties"]["Position"]["multi_select"][0]["name"]
        ) for page in pages]))

        import pandas as pd

        df = pd.DataFrame({
            "id": ids,
            "company_name": company_names,
            "position": positions
        })

        duplicate_mask = df.duplicated(subset=["company_name", "position"], keep='first')
        duplicate_pages_id = df[duplicate_mask]['id'].tolist()

        tasks = []

        for page_id in duplicate_pages_id:
            await asyncio.sleep(1 / 2) # rate limits this to 2 per second
            tasks.append(asyncio.create_task(self._delete_page(page_id)))

        await asyncio.gather(*tasks, return_exceptions=True)

    #for testing
    async def _batch_delete_pages(self, pages: list) -> None:
        delay = 1.0 / 3  # rate limit
        for page in pages:
            await asyncio.sleep(delay)
            await self._delete_page(page["id"])

    #for testing
    async def _get_description(self, page_id) -> Optional[str]:
        endpoint = f'https://api.notion.com/v1/blocks/{page_id}/children'
        async with (self.session.get(endpoint, headers=self.headers) as response):
            response.raise_for_status()
            resp = await response.json()
            resp = resp.get("results", [])

            if resp:
                paragraphs = resp[0]["paragraph"]["rich_text"]

                text = [paragraph["text"]["content"] for paragraph in paragraphs]
                description = " ".join(text)
                return description

        return None

    @property
    def database_cleaner(self):
        return self._database_cleaner


class MessageBus:
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(MessageBus, "_initialized"):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.queue = asyncio.Queue()
            self.gateway = None
            self._initialized = True

    async def publish(self, result: Result):
        log.info('postings are being published')
        if not Gateway.is_initialized():
            self.gateway = Gateway()
            asyncio.create_task(self.gateway.run())

            await self.gateway.ready().wait()

        for message in batch_zip(result.keys(), *result.values()):
            self.queue.put_nowait((result.parser_type, message))

    async def subscribe(self): # each message is a tuple of 3 that can be done every second
        while True:
            message = await self.queue.get()
            yield message
            self.queue.task_done()

class Gateway:
    _ready = asyncio.Event()
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(Gateway, "_initialized"):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.database = None
            self.bus = None
            self._run_started = False
            self.initialized = True

    async def run(self):
        if self._run_started:
            return

        self._run_started = True

        self.database = await NotionDatabase()
        self.bus = MessageBus().subscribe()

        Gateway._ready.set()

        async for parser_type, message in self.bus:
            remaining_time = await self.database.batch_post(*message, parser_type=parser_type)
            await asyncio.sleep(remaining_time)

    def ready(self):
        return self._ready

    @staticmethod
    def is_initialized():
        return hasattr(Gateway, "_initialized")