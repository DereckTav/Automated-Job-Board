import pytest
from net.http_client import Session
# check if singleton

# check if session is up (so on)

# check if close works

# check if I delete it and do gc.collect does it take care of background task

@pytest.mark.asyncio
async def test_singleton():
    async with Session() as s1:
        async with Session() as s2:
            assert s1 is s2

@pytest.mark.asyncio
async def test_session_up():
    async with Session() as s1:
        assert s1 is not None

