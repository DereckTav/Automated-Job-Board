from abc import ABC, abstractmethod
from typing import Optional

from JobParser.output import Result


class Parser(ABC):

    @abstractmethod
    async def parse(self, config: dict) -> Optional[Result]:
        pass





