from WebsiteManager import Manager
import asyncio

if __name__ == "__main__":
    manager = Manager()
    asyncio.run(manager.start())