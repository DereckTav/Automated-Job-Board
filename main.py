from WebsiteManager import Manager
import asyncio

async def main():
    manager = Manager()
    await manager.start()


if __name__ == "__main__":
    asyncio.run(main())