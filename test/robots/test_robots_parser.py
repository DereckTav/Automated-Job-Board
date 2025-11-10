import asyncio
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch
import time

from robots.parser import RobotsTxtParser
from robots.output import RobotsRules
from robots.cache import InMemoryRobotsCache
from robots.refresher import RobotsCacheRefresher


# Mock HTTP Server for testing
class MockRobotsHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving robots.txt and test pages"""

    def log_message(self, format, *args):
        """Suppress server logs during testing"""
        pass

    def do_GET(self):
        if self.path == '/robots.txt':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            robots_content = """User-agent: TestBot
Disallow: /blocked/
Crawl-delay: 5
"""
            self.wfile.write(robots_content.encode())

        elif self.path == '/allowed-page':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body>Allowed page</body></html>')

        else:
            self.send_response(404)
            self.end_headers()


class TestServer:
    """test server context manager"""

    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None

    def __enter__(self):
        self.server = HTTPServer(('localhost', self.port), MockRobotsHandler) # type: ignore
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.5) # Give server time to start
        return self

    def __exit__(self, *args):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    @property
    def base_url(self):
        return f'http://localhost:{self.port}'

@pytest.fixture
def test_server():
    """Provide a test HTTP server"""
    with TestServer() as server:
        yield server

# get_rules Tests
@pytest.mark.asyncio
async def test_get_rules_allowed_url(test_server):
    """test get_rules for an allowed URL"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/allowed-page"
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")

    assert rules.can_fetch is True, "Should allow fetching"
    assert rules.crawl_delay >= 1.0, "Should have crawl delay"
    assert rules.user_agent == "TestBot/1.0"


@pytest.mark.asyncio
async def test_get_rules_disallowed_url(test_server):
    """test get_rules for a disallowed URL"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/blocked/page"
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")

    assert rules.can_fetch is False, "Should disallow fetching"


@pytest.mark.asyncio
async def test_get_rules_base_url_with_slash(test_server):
    """test get_rules with base_url ending in slash"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/allowed-page"
    base_url_with_slash = test_server.base_url + "/"
    rules = await parser.get_rules(url, base_url_with_slash,"TestBot/1.0")

    assert rules is not None, "Should handle base_url with trailing slash"
    assert isinstance(rules, RobotsRules)


@pytest.mark.asyncio
async def test_get_rules_caching(test_server):
    """test that rules are cached after first fetch"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/allowed-page"

    # First fetch
    rules1 = await parser.get_rules(url, test_server.base_url,"TestBot/1.0")

    # Second fetch (should use cache)
    rules2 = await parser.get_rules(url, test_server.base_url,"TestBot/1.0")

    assert rules1.can_fetch == rules2.can_fetch
    assert rules1.crawl_delay == rules2.crawl_delay


@pytest.mark.asyncio
async def test_get_rules_exception_handling():
    """test get_rules returns default rules on exception"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    # Use invalid URL to trigger exception
    url = "http://invalid-domain-that-does-not-exist-12345.com/page"
    rules = await parser.get_rules(url, "http://invalid-domain-that-does-not-exist-12345.com", "TestBot/1.0")

    assert rules.can_fetch is False, "Should default to allowing fetch on error"
    assert rules.crawl_delay == 1.0, "Should use default crawl delay"


# _check Tests
@pytest.mark.asyncio
async def test_check_valid_url(test_server):
    """test _check with valid URL"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/allowed-page"
    result = await RobotsCacheRefresher(parser, cache)._validate_url(url, "TestBot/1.0")

    assert result is True, "Should return True for allowed URL"


@pytest.mark.asyncio
async def test_check_blocked_url(test_server):
    """test _check with blocked URL"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = f"{test_server.base_url}/blocked/page"
    result = await RobotsCacheRefresher(parser, cache)._validate_url(url, "TestBot/1.0")

    assert result is False, "Should return False for blocked URL"


@pytest.mark.asyncio
async def test_check_invalid_url():
    """test _check with invalid URL"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    url = "http://invalid-domain-12345.com/page"
    result = await RobotsCacheRefresher(parser, cache)._validate_url(url, "TestBot/1.0")

    assert result is False, "Should return False on exception"

# _refresh Tests
@pytest.mark.asyncio
async def test_refresh_removes_invalid_urls():
    """test that _refresh removes invalid URLs from cache"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)

    # Manually add invalid URL to cache
    invalid_url = "http://invalid-domain-12345.com/page"
    cache.set(invalid_url, RobotsRules(True, 1.0, "TestBot/1.0"))

    assert cache.has(invalid_url), "URL should be in cache initially"

    # Manually trigger refresh logic (just one iteration)
    urls_to_remove = []
    for url in list(cache.get_all_urls()):
        valid = await RobotsCacheRefresher(parser, cache)._validate_url(url, "TestBot/1.0")
        if not valid:
            urls_to_remove.append(url)

    for url in urls_to_remove:
        cache.remove(url)

    assert not cache.has(invalid_url), "Invalid URL should be removed"


@pytest.mark.asyncio
async def test_refresh_task_created():
    """test that refresh task is created on initialization"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)
    refresh = RobotsCacheRefresher(parser, cache)
    refresh.start()

    assert refresh._task is not None, "Refresh task should be created"
    assert isinstance(refresh._task, asyncio.Task), "Should be an asyncio Task"


@pytest.mark.asyncio
async def test_refresh_cancellation():
    """test that refresh task can be cancelled"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)
    refresh = RobotsCacheRefresher(parser, cache)
    refresh.start()

    # Cancel the refresh task
    refresh.stop()

    try:
        await refresh._task
    except asyncio.CancelledError:
        pass  # Expected

    assert refresh._task.cancelled(), "Task should be cancelled"


# Integration Tests
@pytest.mark.asyncio
async def test_full_workflow(test_server):
    """test complete workflow: get_rules, caching, and checking"""
    cache = InMemoryRobotsCache()
    parser = RobotsTxtParser(cache)
    refresh = RobotsCacheRefresher(parser, cache)

    url = f"{test_server.base_url}/allowed-page"

    # Get rules
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")
    assert rules.can_fetch is True

    # Check URL
    can_fetch = await refresh._validate_url(url, "TestBot/1.0")
    assert can_fetch is True

    # Verify caching
    assert cache.has(url)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])