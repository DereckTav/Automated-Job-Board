import sys
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

from fake_useragent import UserAgent

from net.http_client import Session
from net.browser_manager import BrowserManager
from parsers.factory import ParserFactory
from processing.tracker import Tracker

from contextlib import contextmanager

'''
if you run test case make sure to switch dates in test.html
to the current date or the date before the current date


note: tried to patch datetime didn't work which is why to run tests
the dates inside the html/csv files need to be changed
'''

PORT = 8080

config = {
    'url': f"http://localhost:{PORT}/allowed-page",
    'base_url': f"http://localhost:{PORT}",
    'date_format': '%Y-%m-%d',
    'selectors': {
        'company_name': "div.flex-auto.line-height-4",
        'position': "div.flex-auto.line-height-4 div.truncate",
        'application_link': "div.domain-class",
        'description': "div.description-class",
        'date': "div.date-class"
    }
}


alt_config = {
    'url': f"http://localhost:{PORT}/alternative",
    'base_url': f"http://localhost:{PORT}",
    'date_format': '%Y-%m-%d',
    'selectors': {
        'company_name': "div.flex-auto.line-height-4",
        'position': "div.flex-auto.line-height-4 div.truncate",
        'application_link': "div.domain-class",
        'description': "div.description-class",
        'date': "div.date-class"
    }
}

alternative_visit_count = 0

class MockHtmlHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global alternative_visit_count
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
            with open("test/jobparser/data/test.html", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/alternative':
            alternative_visit_count += 1

            if alternative_visit_count == 1:
                filename = "test/jobparser/data/alternative_test.html"
            else:
                filename = "test/jobparser/data/test.html"

            with open(filename, "r", encoding="utf-8") as f:
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

def get_factory():
    session = Session()
    tracker = Tracker()
    browser_manager = BrowserManager()
    user_agent_provider = UserAgent()
    factory = ParserFactory(session, browser_manager, tracker, user_agent_provider)
    return factory

#test parse
@pytest.mark.asyncio
async def test_parse(test_server, reset_singleton):
    factory = get_factory()
    result = await factory.create_static_parser().parse(config)

    assert result is not None
    print(result)

    assert len(result.company_name) > 0, "Company name should not be empty"
    assert len(result.position) > 0, "Position should not be empty"
    assert len(result.application_link) > 0, "Domain should not be empty"
    assert len(result.description) > 0, "Description should not be empty"

@pytest.mark.asyncio
async def test_parse_new_info(test_server, reset_singleton):
    factory = get_factory()
    parser = factory.create_static_parser()

    invalid_result = await parser.parse(alt_config)
    print(invalid_result)

    result = await parser.parse(alt_config)
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