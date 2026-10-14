"""Deduplication and statistics processing module."""

from datetime import datetime, timezone
from typing import Any, List, Tuple
from dateutil import parser as date_parser

from app.models import ClientItem, OrdersResponse, RawOrder, Stats
from app.normalizer import normalize_russian_phone


def parse_timestamp(created_at_str: str) -> float:
    """Safely parse an ISO-8601 timestamp string to POSIX timestamp float in UTC."""
    if not created_at_str or not isinstance(created_at_str, str):
        return 0.0
    try:
        dt = date_parser.isoparse(created_at_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def deduplicate_and_calculate_stats(raw_records: List[Any]) -> OrdersResponse:
    """Process raw order records: validate, normalize phone, deduplicate, and compute stats.

    Priority cascade for duplicate selection per normalized phone:
    1. Maximum amount (numeric comparison).
    2. Latest created_at timestamp.
    3. Maximum record id (deterministic tie-breaker).

    Accounting Invariant:
    received == unique + duplicates_merged + invalid_dropped
    """
    received_count = len(raw_records)
    invalid_dropped_count = 0
    phone_groups: dict[str, list[RawOrder]] = {}

    for item in raw_records:
        if not isinstance(item, dict):
            invalid_dropped_count += 1
            continue

        try:
            # Validate core record structure without mutating input item
            order = RawOrder(**item)
        except Exception:
            invalid_dropped_count += 1
            continue

        norm_phone = normalize_russian_phone(order.phone)
        if norm_phone is None:
            invalid_dropped_count += 1
            continue

        if norm_phone not in phone_groups:
            phone_groups[norm_phone] = []
        phone_groups[norm_phone].append(order)

    # Determine winners for each normalized phone group
    clients: list[ClientItem] = []
    duplicates_merged_count = 0

    for norm_phone, group in phone_groups.items():
        # Count losing duplicate records in this group
        duplicates_merged_count += len(group) - 1

        # Priority key: (amount, timestamp, id)
        def priority_key(o: RawOrder) -> Tuple[float, float, int]:
            return (float(o.amount), parse_timestamp(o.created_at), int(o.id))

        winner = max(group, key=priority_key)

        # Build clean client item; atomic record, no field merging
        clients.append(
            ClientItem(
                name=winner.name,
                phone=norm_phone,
                email=winner.email,
                amount=winner.amount,
            )
        )

    # Deterministic ascending sort by normalized phone number
    clients.sort(key=lambda c: c.phone)

    unique_count = len(clients)

    # Strict invariant check
    total_accounted = unique_count + duplicates_merged_count + invalid_dropped_count
    if received_count != total_accounted:
        raise ValueError(
            f"Accounting invariant violated: received ({received_count}) != "
            f"unique ({unique_count}) + duplicates_merged ({duplicates_merged_count}) + "
            f"invalid_dropped ({invalid_dropped_count}) = {total_accounted}"
        )

    stats = Stats(
        received=received_count,
        unique=unique_count,
        duplicates_merged=duplicates_merged_count,
        invalid_dropped=invalid_dropped_count,
    )

    return OrdersResponse(clients=clients, stats=stats)
