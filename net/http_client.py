import aiohttp
import asyncio
import atexit

class Session(aiohttp.ClientSession):
    _instance = None

    def __new__(cls):
        if not cls._instance and not hasattr(cls, '_initialized'):
                # or (hasattr(cls._instance, 'closed') and cls._instance.closed)): # just incase if it ever closes
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            super().__init__()
            self._initialized = True

async def cleanup():
    session = Session()
    if not session.closed:
        await session.close()

def shutdown_handler():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

atexit.register(shutdown_handler)