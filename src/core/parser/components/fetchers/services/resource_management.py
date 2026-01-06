'''
outputs resources like sessions
or browserManagers
'''

from abc import ABC

class ResourceManager(ABC):

    async def get_session(self):
        pass

    async def get_browser_manager(self):
        pass
