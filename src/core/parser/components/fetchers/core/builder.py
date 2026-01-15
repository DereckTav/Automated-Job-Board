from abc import ABC

from src.core.services.resources.core.resource_management import ResourceManager


class Builder(ABC):

    def __init__(self, resource_management: ResourceManager, **kwargs):
        self.resource_management = resource_management

    def build_http_content_fetcher(self):
        pass

    def build_selenium_content_fetcher(self):
        pass

    def build_download_content_fetcher(self):
        pass

    def build_airtable_selenium_content_fetcher(self):
        pass