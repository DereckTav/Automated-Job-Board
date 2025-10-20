import pytest
from LocalData.cache import Cache

@pytest.fixture()
def reset_singleton():
    Cache._instance = None
    if hasattr(Cache, "_initialized"):
        delattr(Cache, '_initialized')
    yield
    Cache._instance = None
    if hasattr(Cache, "_initialized"):
        delattr(Cache, '_initialized')

@pytest.mark.asyncio
def test_singleton_implementation(reset_singleton):
    c1 = Cache()
    c2 = Cache()

    assert c1 is c2

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])