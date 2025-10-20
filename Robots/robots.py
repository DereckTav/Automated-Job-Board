from dataclasses import dataclass

@dataclass
class RobotsRules:
    can_fetch: bool
    crawl_delay: float
    user_agent: str