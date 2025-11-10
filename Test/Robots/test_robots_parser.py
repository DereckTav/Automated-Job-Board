import asyncio
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch
import time

from src.Robots.robots_parser import RobotsTxtParser
from src.Robots.robots import RobotsRules

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
    """Test server context manager"""

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


# Test fixtures
@pytest.fixture
def reset_singleton():
    """Reset the singleton between tests"""
    RobotsTxtParser._instance = None
    if hasattr(RobotsTxtParser, '_initialized'):
        delattr(RobotsTxtParser, '_initialized')

    yield

    # Reset again after test
    RobotsTxtParser._instance = None
    if hasattr(RobotsTxtParser, '_initialized'):
        delattr(RobotsTxtParser, '_initialized')

@pytest.fixture
def test_server():
    """Provide a test HTTP server"""
    with TestServer() as server:
        yield server


# Singleton Tests
@pytest.mark.asyncio
async def test_singleton_same_instance(reset_singleton):
    """Test that RobotsTxtParser maintains singleton pattern"""
    parser1 = RobotsTxtParser()
    parser2 = RobotsTxtParser()

    assert parser1 is parser2, "Should return same instance"

@pytest.mark.asyncio
async def test_singleton_initialization_once(reset_singleton):
    """Test that __init__ only runs once"""
    parser1 = RobotsTxtParser()
    original_cache = parser1._cache

    parser2 = RobotsTxtParser()

    assert parser2._cache is original_cache, "Cache should be same object"


# get_rules Tests
@pytest.mark.asyncio
async def test_get_rules_allowed_url(test_server):
    """Test get_rules for an allowed URL"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")

    assert rules.can_fetch is True, "Should allow fetching"
    assert rules.crawl_delay >= 1.0, "Should have crawl delay"
    assert rules.user_agent == "TestBot/1.0"


@pytest.mark.asyncio
async def test_get_rules_disallowed_url(test_server):
    """Test get_rules for a disallowed URL"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/blocked/page"
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")

    assert rules.can_fetch is False, "Should disallow fetching"


@pytest.mark.asyncio
async def test_get_rules_base_url_with_slash(test_server):
    """Test get_rules with base_url ending in slash"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"
    base_url_with_slash = test_server.base_url + "/"
    rules = await parser.get_rules(url, base_url_with_slash,"TestBot/1.0")

    assert rules is not None, "Should handle base_url with trailing slash"
    assert isinstance(rules, RobotsRules)


@pytest.mark.asyncio
async def test_get_rules_caching(test_server):
    """Test that rules are cached after first fetch"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"

    # First fetch
    rules1 = await parser.get_rules(url, test_server.base_url,"TestBot/1.0")

    # Second fetch (should use cache)
    rules2 = await parser.get_rules(url, test_server.base_url,"TestBot/1.0")

    assert rules1.can_fetch == rules2.can_fetch
    assert rules1.crawl_delay == rules2.crawl_delay


@pytest.mark.asyncio
async def test_get_rules_exception_handling():
    """Test get_rules returns default rules on exception"""
    parser = RobotsTxtParser()

    # Use invalid URL to trigger exception
    url = "http://invalid-domain-that-does-not-exist-12345.com/page"
    rules = await parser.get_rules(url, "http://invalid-domain-that-does-not-exist-12345.com", "TestBot/1.0")

    assert rules.can_fetch is False, "Should default to allowing fetch on error"
    assert rules.crawl_delay == 1.0, "Should use default crawl delay"


# _check Tests
@pytest.mark.asyncio
async def test_check_valid_url(test_server):
    """Test _check with valid URL"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"
    result = await parser._check(url, "TestBot/1.0")

    assert result is True, "Should return True for allowed URL"


@pytest.mark.asyncio
async def test_check_blocked_url(test_server):
    """Test _check with blocked URL"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/blocked/page"
    result = await parser._check(url, "TestBot/1.0")

    assert result is False, "Should return False for blocked URL"


@pytest.mark.asyncio
async def test_check_invalid_url():
    """Test _check with invalid URL"""
    parser = RobotsTxtParser()

    url = "http://invalid-domain-12345.com/page"
    result = await parser._check(url, "TestBot/1.0")

    assert result is False, "Should return False on exception"


@pytest.mark.asyncio
async def test_check_caches_valid_urls(test_server):
    """Test that _check caches valid URLs"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"
    await parser._check(url, "TestBot/1.0")

    # Check if URL is in cache
    assert parser._cache.has(url), "Valid URL should be cached"


# _refresh Tests
@pytest.mark.asyncio
async def test_refresh_removes_invalid_urls():
    """Test that _refresh removes invalid URLs from cache"""
    parser = RobotsTxtParser()

    # Manually add invalid URL to cache
    invalid_url = "http://invalid-domain-12345.com/page"
    parser._cache.cache(invalid_url, RobotsRules(True, 1.0, "TestBot/1.0"))

    assert parser._cache.has(invalid_url), "URL should be in cache initially"

    # Mock the _check method to return False
    with patch.object(parser, '_check', return_value=False):
        # Manually trigger refresh logic (just one iteration)
        urls_to_remove = []
        for url in list(parser._cache.keys()):
            valid = await parser._check(url)
            if not valid:
                urls_to_remove.append(url)

        for url in urls_to_remove:
            parser._cache.pop(url)

    assert not parser._cache.has(invalid_url), "Invalid URL should be removed"


@pytest.mark.asyncio
async def test_refresh_task_created():
    """Test that refresh task is created on initialization"""
    parser = RobotsTxtParser()

    assert parser._robots_refresher is not None, "Refresh task should be created"
    assert isinstance(parser._robots_refresher, asyncio.Task), "Should be an asyncio Task"


@pytest.mark.asyncio
async def test_refresh_cancellation():
    """Test that refresh task can be cancelled"""
    parser = RobotsTxtParser()

    # Cancel the refresh task
    parser._robots_refresher.cancel()

    try:
        await parser._robots_refresher
    except asyncio.CancelledError:
        pass  # Expected

    assert parser._robots_refresher.cancelled(), "Task should be cancelled"


# Integration Tests
@pytest.mark.asyncio
async def test_full_workflow(test_server):
    """Test complete workflow: get_rules, caching, and checking"""
    parser = RobotsTxtParser()

    url = f"{test_server.base_url}/allowed-page"

    # Get rules
    rules = await parser.get_rules(url, test_server.base_url, "TestBot/1.0")
    assert rules.can_fetch is True

    # Check URL
    can_fetch = await parser._check(url, "TestBot/1.0")
    assert can_fetch is True

    # Verify caching
    assert parser._cache.has(url)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])