import sys
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

from JobParser.parsers.static_parser import StaticContentParser
from Http.http_client import Session
from LocalData.tracker import WebTracker

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
            with open("Test/JobParser/test.html", "r", encoding="utf-8") as f:
                html_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif self.path == '/alternative':
            alternative_visit_count += 1

            if alternative_visit_count == 1:
                filename = "Test/JobParser/alternative_test.html"
            else:
                filename = "Test/JobParser/test.html"

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
    StaticContentParser._instance = None
    if hasattr(StaticContentParser, "_initialized"):
        delattr(StaticContentParser, "_initialized")

    WebTracker._instance = None
    if hasattr(WebTracker, "_initialized"):
        delattr(WebTracker, "_initialized")

    Session._instance = None
    if hasattr(Session, "_initialized"):
        delattr(Session, "_initialized")

    yield

    StaticContentParser._instance = None
    if hasattr(StaticContentParser, "_initialized"):
        delattr(StaticContentParser, "_initialized")

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
    parser1 = StaticContentParser()
    parser2 = StaticContentParser()

    assert parser1 is parser2, "Should return same instance"

@pytest.mark.asyncio
async def test_singleton_initialization_once(reset_singleton):
    """Test that __init__ only runs once"""
    parser1 = StaticContentParser()
    original_tracker = parser1.tracker

    parser2 = StaticContentParser()

    assert parser2.tracker is original_tracker, "tracker should be same object"

# remember to switch dates in test files to either today or yesterday

#test parse
@pytest.mark.asyncio
async def test_parse(test_server, reset_singleton):
    result = await StaticContentParser().parse(config)

    assert result is not None
    print(result)

    assert len(result.company_name) > 0, "Company name should not be empty"
    assert len(result.position) > 0, "Position should not be empty"
    assert len(result.application_link) > 0, "Domain should not be empty"
    assert len(result.description) > 0, "Description should not be empty"

@pytest.mark.asyncio
async def test_parse_new_info(test_server, reset_singleton):
    invalid_result = await StaticContentParser().parse(alt_config)
    print(invalid_result)

    result = await StaticContentParser().parse(alt_config)
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