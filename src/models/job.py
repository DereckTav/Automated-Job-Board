from dataclasses import dataclass
from typing import Optional
import datetime

@dataclass(frozen=True)
class Job:
    company_name: str
    role: str
    type: str
    url: str
    pay: Optional[float]
    location: Optional[str]
    description: Optional[str]
    date: Optional[datetime.datetime]

    def __post_init__(self):
        """This replaces your 'corrupt/invalid' checks."""
        if len(self.company_name) < 2 or len(self.role) < 2:
            raise ValueError(f"Invalid data: {self.company_name}")