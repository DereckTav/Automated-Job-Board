import asyncio
import threading
from unittest.mock import AsyncMock, patch

import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

from Database.notion import Gateway, NotionDatabase, MessageBus
from Http.http_client import Session
from JobParser.parsers.download_parser import DownloadParser
from JobParser.parsers.js_parser import JavaScriptContentParser
from JobParser.parsers.static_parser import StaticContentParser
from LocalData.tracker import WebTracker
from LocalData.test_cache import Cache
from WebsiteManager import Manager
from contextlib import contextmanager

'''
if you run test case make sure to switch dates in test.html
to the current date or the date before the current date

note: tried to patch datetime didn't work which is why to run tests
teh dates inside the html/csv files need to be changed
'''

PORT = 8080

class MockHtmlHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except ConnectionResetError:
            pass

    def do_GET(self):
        if self.path == '/robots.txt':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            robots_content = """User-agent: *
Disallow: /blocked/
Crawl-delay: 1
"""
            self.wfile.write(robots_content.encode())

        elif self.path == '/csv':
            with open("Test/JobParser/data.csv", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/static':
            with open("Test/JobParser/test.html", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/dynamic':
            with open("Test/JobParser/dynamic_test.html", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

@contextmanager
def mock_server(port=PORT):
    server = HTTPServer(('localhost', port), MockHtmlHandler) # type: ignore
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)

    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

@pytest.fixture
def test_server():
    with mock_server() as server:
        yield server

@pytest.fixture
def reset_singleton():

    for cls in [Gateway, NotionDatabase, MessageBus, DownloadParser, WebTracker, Session, JavaScriptContentParser,
                StaticContentParser, Manager, Cache]:
        cls._instance = None
        if hasattr(cls, "_initialized"):
            delattr(cls, "_initialized")

    yield

    for cls in [Gateway, NotionDatabase, MessageBus, DownloadParser, WebTracker, Session, JavaScriptContentParser,
                StaticContentParser, Manager, Cache]:
        cls._instance = None
        if hasattr(cls, "_initialized"):
            delattr(cls, "_initialized")


'''
if using test clear notion database

why? 
hard to check if what was added was the examples in our test files
'''
@pytest.mark.asyncio
async def test_manger(reset_singleton, test_server):
    with patch.object(NotionDatabase, "clear_duplicates", new_callable=AsyncMock) as mock_clear:
        mock_clear.return_value = None

        for cls in [Gateway, NotionDatabase, MessageBus, DownloadParser, WebTracker, Session, JavaScriptContentParser,
                    StaticContentParser, Manager, Cache]:
            cls._instance = None
            if hasattr(cls, "_initialized"):
                delattr(cls, "_initialized")

        manager = Manager("C:/Users/ds3/PycharmProjects/PythonProject/Test/test.yaml", True)
        await manager.start()

        while not await manager.is_idle():
            await asyncio.sleep(1)

        await asyncio.sleep(6) # min number of seconds for all listings to be processed
        pages = await NotionDatabase()._query_database()

        print(pages)
        if len(pages) < 18:
            await manager.stop()
            raise Exception("Something went wrong")

        elif len(pages) == 18:
            await manager.stop()
            assert True

        elif len(pages) > 18:
            await manager.stop()
            assert False

        else:
            assert False

        await asyncio.sleep(1)
        await NotionDatabase()._batch_delete_pages(pages[0:18])