import sys
import threading

import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import time

from JobParser.parsers.download_parser import DownloadParser
from JobParser.output import Result
from LocalData.tracker import WebTracker
from Http.http_client import Session

from contextlib import contextmanager

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
            with open("Test/JobParser/data.csv", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/allowed-page-2':
            with open("Test/JobParser/data_date_out_of_range.csv", "r", encoding="utf-8") as f:
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
    DownloadParser._instance = None
    if hasattr(DownloadParser, "_initialized"):
        delattr(DownloadParser, "_initialized")

    WebTracker._instance = None
    if hasattr(WebTracker, "_initialized"):
        delattr(WebTracker, "_initialized")

    Session._instance = None
    if hasattr(Session, "_initialized"):
        delattr(Session, "_initialized")

    yield

    DownloadParser._instance = None
    if hasattr(DownloadParser, "_initialized"):
        delattr(DownloadParser, "_initialized")

    WebTracker._instance = None
    if hasattr(WebTracker, "_initialized"):
        delattr(WebTracker, "_initialized")

    Session._instance = None
    if hasattr(Session, "_initialized"):
        delattr(Session, "_initialized")

@pytest.fixture
def test_server():
    with mock_server() as server:
        yield server

# Singleton Tests
@pytest.mark.asyncio
async def test_singleton_same_instance(reset_singleton):
    """Test that static_parser maintains singleton pattern"""
    parser1 = DownloadParser()
    parser2 = DownloadParser()

    assert parser1 is parser2, "Should return same instance"

@pytest.mark.asyncio
async def test_singleton_initialization_once(reset_singleton):
    """Test that __init__ only runs once"""
    parser1 = DownloadParser()
    original_tracker = parser1.tracker

    parser2 = DownloadParser()

    assert parser2.tracker is original_tracker, "tracker should be same object"

#test parse
@pytest.mark.asyncio
async def test_parse(test_server, reset_singleton):
    result = await DownloadParser().parse(config)


    assert result is not None
    print(result)

    assert len(result.company_name) > 0, "Company name should not be empty"
    assert len(result.position) > 0, "Position should not be empty"
    assert len(result.application_link) > 0, "Domain should not be empty"
    assert len(result.description) > 0, "Description should not be empty"

@pytest.mark.asyncio
async def test_parse_out_range(test_server, reset_singleton):
    result = await DownloadParser().parse(config_2)

    assert result is None

@pytest.mark.asyncio
async def test_parse_new_info(test_server, reset_singleton):
    df = pd.read_csv("Test/JobParser/data.csv")
    df['date'] = pd.to_datetime(df['date'], format=config.get('date_format'))
    DownloadParser().tracker.track(config.get('url'), str(df.iloc[3].tolist()))
    df = df.iloc[3:]

    extracted_data = {}

    selectors = config.get('selectors')

    for key, selector in selectors.items():
        if selector in df.columns:
            extracted_data[key] = df[selector].astype(str).tolist()

    invalid_result = Result(**extracted_data)
    print(invalid_result)

    result = await DownloadParser().parse(config)

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