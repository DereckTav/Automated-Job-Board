'''

Parsing Arguments: Reading command-line inputs or .env files.

Dependency Injection: Initializing components (like your BrowserPool, Database, or API clients).

Orchestration: Passing those components into a "Coordinator" or "Engine" class.

Teardown: Ensuring everything closes gracefully when the app finishes.

Initialize BrowserPool, load config, and call App.run().
'''



_refresh_instance = None

async def cleanup():
    """Cleanup on shutdown"""
    if _refresh_instance:
        await _refresh_instance.stop()

        try:
            await _refresh_instance._task
        except asyncio.CancelledError:
            pass


def shutdown_handler():
    """Handle shutdown gracefully"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cleanup())
    loop.close()

atexit.register(shutdown_handler)


from src.core.app import Manager
import asyncio
from src.integrations.scripts.fill_weights import initialize_weights

async def main():
    # 1. setup weights page
    initialize_weights()

    manager = Manager()
    manager.set_global_instance(manager) # for clean up
    await manager.start()


if __name__ == "__main__":
    asyncio.run(main())