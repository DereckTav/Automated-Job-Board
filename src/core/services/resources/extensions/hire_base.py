from datetime import datetime, timedelta

from src.core.logs import Logger, APP
from ..resource_manager import ResourceManager
from ..proxy_service.proxy_manager import ProxyManager

from typing import Any, Optional

LOGGER = Logger(APP)

class HireBaseMixin:
    def __init__(
            self,
            hire_base_api: str,
            api_key: str,
            types: list[str],
            defaults: dict[str, Any],
            query_postfix: str = "",
            days_ago: Optional[int] = 2,
            api_limit: Optional[int] = 10,
            **kwargs
    ):
        self.hire_base_api = hire_base_api
        self.api_key = api_key

        if len(types) > api_limit:
            LOGGER.warning(f"(HIRE_BASE_MIXIN) Rate Limit Risk: You have {len(types)} job types but only 10 requests/day.")
            LOGGER.warning(f"(HIRE_BASE_MIXIN) Truncating to first {api_limit} types to prevent API ban.")
            self.types = types[:api_limit]

        self.defaults = defaults
        self.query_postfix = query_postfix
        self.days_ago = days_ago

        super().__init__(**kwargs)

    def _construct_requests(self) -> list[dict[str, Any]]:
        payloads = []

        date_posted = (datetime.now() - timedelta(days=self.days_ago)).strftime('%Y-%m-%d')

        for job_query in self.types:
            payload = self.defaults.copy()
            payload["query"] = f"{job_query} {self.query_postfix}".strip()
            payload["date_posted"] = date_posted

            payloads.append(payload)

        return payloads

    def get_api_endpoint(self) -> str:
        return self.hire_base_api

    def get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }

    def get_requests(self) -> list[dict[str, Any]]:
        return self._construct_requests()

class HireBaseManager(HireBaseMixin, ResourceManager):
    pass


class HireBaseProxyManager(HireBaseMixin, ProxyManager):
    pass