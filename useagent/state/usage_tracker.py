from collections import defaultdict

from loguru import logger
from pydantic import validate_call
from pydantic_ai.usage import Usage

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


class UsageTracker:
    """
    Small helper that extends a simple `dict` logic for storing the sub-agent usages.
    This helps us to just add `search_agent_result.usage` under the key `search` while keeping track of the individual calls.
    """

    # Dev Note:
    # Pydantic_AI does intentionally not report monetary costs, because the plattform providers change their costs quite often.
    # They did not want to maintain a list or lookup for that, and instead just report the raw usage.
    # This consists of tokens, requests, etc. and a field `details` that the providers can use to show other things.
    # For reporting in a Paper, we need to look at our usage and look up the prices ourselves.
    # TODO: Investigate what is in the `details` for which model, and what of that we want to use for ourselves.

    def __init__(self) -> None:
        self.usage: dict[NonEmptyStr, Usage] = {}
        self.counts: defaultdict[str, int] = defaultdict(int)
        logger.debug("Initialized a new UsageTracker")

    @validate_call
    def add(self, name: NonEmptyStr, usage: Usage) -> None:
        """
        Adds a given usage to the tracker.
        The given key will be 'extended' by adding a incrementing number of how often this tool was seen.
        """
        self.counts[name] += 1
        call_name = f"{name}-call-no-{self.counts[name]}"
        self.usage[call_name] = usage
        logger.debug(
            f"Added an entry for {name} to UsageTracker - this was entry {self.counts[name]} for {name} and there are {len(list(self.usage.keys()))} entries in total"
        )

    def group(self) -> "UsageTracker":
        """
        Groups and Sums the usages in this tracker based on their origin.
        """
        grouped = UsageTracker()
        for full_name, usage in self.usage.items():
            base_name = full_name.split("-call-")[0]
            if base_name not in grouped.usage:
                grouped.usage[base_name] = usage
            else:
                # DevNote: This works because pydantics usage implements `__add__`
                grouped.usage[base_name] += usage
        return grouped

    def to_json(self) -> dict[NonEmptyStr, dict[str, int | dict[str, int] | None]]:
        return {
            name: {
                "requests": usage.requests,
                "request_tokens": usage.request_tokens,
                "response_tokens": usage.response_tokens,
                "total_tokens": usage.total_tokens,
                "details": usage.details,
            }
            for name, usage in self.usage.items()
        }

    @classmethod
    def from_json(
        cls, data: dict[str, dict[str, int | dict[str, int] | None]]
    ) -> "UsageTracker":
        """
        Constructs a UsageTracker form a given json dict.
        Important: The incremental tracker will NOT be instantiated or updated, so consider objects derived from here as `read only`.
        This is meant e.g. if you do later analysis and want to run scripts that prefer to use this object.
        """
        tracker = cls()
        for name, usage_data in data.items():
            usage = Usage(
                requests=usage_data.get("requests", 0),  # pyright: ignore
                request_tokens=usage_data.get("request_tokens"),  # pyright: ignore
                response_tokens=usage_data.get("response_tokens"),  # pyright: ignore
                total_tokens=usage_data.get("total_tokens"),  # pyright: ignore
                details=usage_data.get("details"),  # pyright: ignore
            )
            tracker.usage[name] = usage
        return tracker
