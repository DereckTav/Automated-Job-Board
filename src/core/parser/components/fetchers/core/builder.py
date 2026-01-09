from abc import ABC

from src.core.parser.components.fetchers.services.resource_management import ResourceManager


class Builder(ABC):

    def __init__(self, resource_management: ResourceManager, **kwargs):
        self.resource_management = resource_management

    async def build_http_content_fetcher(self):
        pass

    async def build_selenium_content_fetcher(self):
        pass

    async def build_download_content_fetcher(self):
        pass

    async def build_airtable_selenium_content_fetcher(self):
        pass