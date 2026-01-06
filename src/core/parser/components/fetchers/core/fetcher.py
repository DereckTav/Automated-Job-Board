from abc import abstractmethod, ABC
from typing import Optional, Any


class ContentFetcher(ABC):
    """
    Abstraction for fetching content.
    """

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> Optional[Any]:
        pass