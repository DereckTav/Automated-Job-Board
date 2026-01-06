import sys
import threading

import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import time

from fake_useragent import UserAgent

from old.net.http_client import Session

from contextlib import contextmanager

from src.core.parser.components.fetchers.components.browser import BrowserManager
from src.core.parser.parser_factory import Factory
from src.models.results import Result
from old.processing import Tracker

'''
if you run test case make sure to switch dates in test.html
to the current date or the date before the current date

note: tried to patch datetime didn't work which is why to run tests
teh dates inside the html/csv files need to be changed
'''

PORT = 8080

config = {
    'url': f"http://localhost:{PORT}/allowed-page",
    'accept': 'text/csv',
    'date_format': '%Y-%m-%d',
    'selectors': {
        'company_name': "company_name",
        'position': "position",
        'application_link': "domain", #this is technically also url
        'description': "description",
        'date': "date"
    }
}

config_2 = {
    'url': f"http://localhost:{PORT}/allowed-page-2",
    'accept': 'text/csv',
    'date_format': '%Y-%m-%d',
    'selectors': {
        'company_name': "company_name",
        'position': "position",
        'application_link': "domain", #this is technically also url
        'description': "description",
        'date': "date"
    }
}

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

        elif self.path == '/allowed-page':
            with open("test/jobparser/data/data.csv", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/allowed-page-2':
            with open("test/jobparser/data/data_date_out_of_range.csv", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
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
def reset_singleton():

    Session._instance = None
    if hasattr(Session, "_initialized"):
        delattr(Session, "_initialized")

    yield

    Session._instance = None
    if hasattr(Session, "_initialized"):
        delattr(Session, "_initialized")

@pytest.fixture
def test_server():
    with mock_server() as server:
        yield server

def get_factory_and_tracker():
    session = Session()
    tracker = Tracker()
    browser_manager = BrowserManager()
    user_agent_provider = UserAgent()
    factory = Factory(session, browser_manager, tracker, user_agent_provider)
    return factory, tracker

#test parse
@pytest.mark.asyncio
async def test_parse(test_server, reset_singleton):
    factory, _ = get_factory_and_tracker()
    result = await factory.create_download_parser().parse(config)


    assert result is not None
    print(result)

    assert len(result.company_name) > 0, "Company name should not be empty"
    assert len(result.position) > 0, "Position should not be empty"
    assert len(result.application_link) > 0, "Domain should not be empty"
    assert len(result.description) > 0, "Description should not be empty"

@pytest.mark.asyncio
async def test_parse_out_range(test_server, reset_singleton):
    factory, _ = get_factory_and_tracker()
    result = await factory.create_download_parser().parse(config_2)

    assert result is None

@pytest.mark.asyncio
async def test_parse_new_info(test_server, reset_singleton):
    factory, tracker = get_factory_and_tracker()
    parser = factory.create_download_parser()

    df = pd.read_csv("test/jobparser/data/data.csv")
    df['date'] = pd.to_datetime(df['date'], format=config.get('date_format'))
    tracker.track(config.get('url'), str(df.iloc[3].tolist()))
    df = df.iloc[3:]

    extracted_data = {}

    selectors = config.get('selectors')

    for key, selector in selectors.items():
        if selector in df.columns:
            extracted_data[key] = df[selector].astype(str).tolist()

    invalid_result = Result(**extracted_data)
    print(invalid_result)

    result = await parser.parse(config)

    assert result is not None
    print(result)

    for item in result.company_name:
        assert item not in invalid_result.company_name

    for item in result.position:
        assert item not in invalid_result.position

    for item in result.application_link:
        assert item not in invalid_result.application_link

    for item in result.description:
        assert item not in invalid_result.description

    assert len(result.company_name) > 0, "Company name should not be empty"
    assert len(result.position) > 0, "Position should not be empty"
    assert len(result.application_link) > 0, "Domain should not be empty"
    assert len(result.description) > 0, "Description should not be empty"

if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
    sys.exit()