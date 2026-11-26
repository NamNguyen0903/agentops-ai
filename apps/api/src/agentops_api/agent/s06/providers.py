"""Application-owned offline search provider."""

from typing import Protocol
from .budgets import acquisition_boundary

from .contracts import (
    SearchRequest,
    SearchResult,
    validate_contract,
)
from .budgets import Budget
from .errors import AcquisitionError, ErrorCode
from .network_policy import validate_url


class SearchProvider(Protocol):
    def search(
        self,
        request: SearchRequest,
        *,
        timeout: float,
    ) -> object: ...


class FixtureSearchProvider:
    def search(self, request, *, timeout):
        return {
            "hits": (
                {
                    "title": "Synthetic research fixture",
                    "url": "https://example.com/fixture",
                    "snippet": "Synthetic offline data.",
                },
            ),
            "synthetic": True,
        }


@acquisition_boundary("search")
def search_offline(
    request: SearchRequest,
    budget: Budget,
    *,
    provider=None,
) -> SearchResult:
    request = validate_contract(
        SearchRequest, request
    )

    if provider is None:
        provider = FixtureSearchProvider()

    if type(provider) is not FixtureSearchProvider:
        raise AcquisitionError(
            ErrorCode.EXTERNAL_DISABLED
        )

    if type(budget) is not Budget:
        raise AcquisitionError(
            ErrorCode.INVALID_INPUT
        )

    deadline = budget.operation_deadline()
    budget.reserve_search(deadline)

    timeout = budget.remaining(deadline)

    try:
        raw = provider.search(
            request,
            timeout=timeout,
        )
    except Exception:
        raise AcquisitionError(
            ErrorCode.PROVIDER_FAILURE
        ) from None

    budget.check(deadline)

    result = validate_contract(
        SearchResult,
        raw,
        output=True,
    )

    if len(result.hits) > request.max_results:
        raise AcquisitionError(
            ErrorCode.INVALID_RESPONSE
        )

    for hit in result.hits:
        validate_url(hit.url)

    return result
