from datetime import datetime, timedelta

from src.core.logs import Logger, APP
from ..resource_manager import ResourceManager
from ..proxy_service.proxy_manager import ProxyManager

from typing import Any, Optional

LOGGER = Logger(APP)

class HireBaseMixin:
    def __init__(
            self,
            api_key: str,
            types: list[str],
            defaults: dict[str, Any],
            query_postfix: str = "",
            posted_days_ago: Optional[int] = 1,
            api_limit: Optional[int] = 10,
            **kwargs
    ):
        """
        extension for resource managers.

        :param api_key:
            The authentication key required to access the HireBase API.

        :param types:
            A list of job categories or titles to search for (e.g., ['Software Engineer', 'Data Scientist']).
            Each item in this list will generate a separate API request.

        :param defaults:
            A dictionary containing default API parameters applied to every request.
            Typical keys include 'top_k', 'limit', 'accuracy', and 'search_type'.

        :param query_postfix:
            A string to append to every search query in the 'types' list.
            Useful for narrowing results (e.g., set to 'Intern' to turn 'Software Engineer' into 'Software Engineer Intern').
            Defaults to "".

        :param posted_days_ago:
            Filters jobs posted within the last N days.
            Calculates the specific date based on the current time and sends it to the API.
            Defaults to 1.

        :param api_limit:
            The maximum number of API requests allowed per run (or per day).
            Used to safely truncate the 'types' list to avoid hitting rate limits.
            Defaults to 10.

        :param kwargs:
            Additional arguments passed to the parent resource managers
        """
        self.api_key = api_key

        if len(types) > api_limit:
            LOGGER.warning(f"(HIRE_BASE_MIXIN) Rate Limit Risk: You have {len(types)} job types but only 10 requests/day.")
            LOGGER.warning(f"(HIRE_BASE_MIXIN) Truncating to first {api_limit} types to prevent API ban.")
            self.types = types[:api_limit]

        self.defaults = defaults
        self.query_postfix = query_postfix
        self.days_ago = posted_days_ago

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