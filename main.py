from WebsiteManager import Manager
import asyncio

async def main():
    manager = Manager()
    manager.set_global_instance(manager) # for clean up
    await manager.start()


if __name__ == "__main__":
    asyncio.run(main())