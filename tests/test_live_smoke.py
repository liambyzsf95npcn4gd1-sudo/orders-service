"""Live smoke test against the actual upstream API."""

import pytest
from app.client import fetch_upstream_orders
from app.deduplicator import deduplicate_and_calculate_stats


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_upstream_smoke():
    """Verify live integration with https://test.ooobs.ru/api/orders."""
    raw_orders = await fetch_upstream_orders()
    assert isinstance(raw_orders, list)
    assert len(raw_orders) > 0

    result = deduplicate_and_calculate_stats(raw_orders)
    assert result.stats.received == len(raw_orders)
    assert result.stats.unique > 0
    assert (
        result.stats.received
        == result.stats.unique
        + result.stats.duplicates_merged
        + result.stats.invalid_dropped
    )
    assert len(result.clients) == result.stats.unique
    for client in result.clients:
        assert client.phone.startswith("+7")
        assert len(client.phone) == 12
        assert client.phone[1:].isdigit()
