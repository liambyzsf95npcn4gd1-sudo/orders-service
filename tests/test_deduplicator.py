"""Unit tests for deduplication, priority rules, and statistics accounting."""

import copy
import pytest
from app.deduplicator import deduplicate_and_calculate_stats


class TestDeduplicator:
    def test_canonical_sample_data(self, sample_upstream_orders):
        """Test with canonical 17-record sample data."""
        original_copy = copy.deepcopy(sample_upstream_orders)
        result = deduplicate_and_calculate_stats(sample_upstream_orders)

        # 1. Non-mutation of input data
        assert sample_upstream_orders == original_copy

        # 2. Accounting invariant
        stats = result.stats
        assert stats.received == 17
        assert stats.unique == 8
        assert stats.duplicates_merged == 5
        assert stats.invalid_dropped == 4
        assert stats.received == stats.unique + stats.duplicates_merged + stats.invalid_dropped

        # 3. Sorted by phone ascending
        phones = [c.phone for c in result.clients]
        assert phones == sorted(phones)

        # 4. Check specific winners
        by_phone = {c.phone: c for c in result.clients}

        # ID 2 won over ID 1 and ID 3 with max amount (5000)
        assert by_phone["79991234567"].amount == 5000
        assert by_phone["79991234567"].name == "Иван П."
        assert by_phone["79991234567"].email == ""  # Empty email preserved

        # ID 5 won over ID 4 with equal amount (200) by latest timestamp
        assert by_phone["79160000001"].amount == 200
        assert by_phone["79160000001"].name == "Мария С."

        # ID 10 won over ID 11 with higher amount (9000 vs 100) despite older timestamp
        assert by_phone["79261234567"].amount == 9000
        assert by_phone["79261234567"].name == "Елена Морозова"

        # ID 8 won over ID 7 (amount 1500 vs 0)
        assert by_phone["79219998877"].amount == 1500
        assert by_phone["79219998877"].name == "Анна В."
        assert by_phone["79219998877"].email == ""

        # ID 9 (10-digit number) successfully normalized and retained
        assert "79005551212" in by_phone

    def test_three_or_more_records_sharing_same_phone(self):
        records = [
            {"id": 10, "name": "A", "phone": "89990000001", "email": "a@ex.com", "amount": 100, "created_at": "2026-01-01T00:00:00Z"},
            {"id": 20, "name": "B", "phone": "+7 999 000-00-01", "email": "b@ex.com", "amount": 500, "created_at": "2026-01-02T00:00:00Z"},
            {"id": 30, "name": "C", "phone": "79990000001", "email": "c@ex.com", "amount": 250, "created_at": "2026-01-03T00:00:00Z"},
            {"id": 40, "name": "D", "phone": "8 (999) 000 00 01", "email": "d@ex.com", "amount": 50, "created_at": "2026-01-04T00:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.stats.received == 4
        assert res.stats.unique == 1
        assert res.stats.duplicates_merged == 3
        assert res.stats.invalid_dropped == 0
        assert len(res.clients) == 1
        assert res.clients[0].name == "B"
        assert res.clients[0].amount == 500

    def test_larger_amount_wins_over_newer_timestamp(self):
        records = [
            {"id": 1, "name": "Older Rich", "phone": "89991112233", "email": "rich@ex.com", "amount": 10000, "created_at": "2025-01-01T00:00:00Z"},
            {"id": 2, "name": "Newer Poor", "phone": "+79991112233", "email": "poor@ex.com", "amount": 10, "created_at": "2026-10-10T00:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients[0].name == "Older Rich"
        assert res.clients[0].amount == 10000

    def test_equal_amounts_resolved_by_latest_timestamp(self):
        records = [
            {"id": 1, "name": "First", "phone": "89991112233", "email": "", "amount": 500, "created_at": "2026-01-01T12:00:00Z"},
            {"id": 2, "name": "Second", "phone": "+79991112233", "email": "", "amount": 500, "created_at": "2026-01-02T12:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients[0].name == "Second"

    def test_equal_amount_and_timestamp_resolved_by_max_id(self):
        records = [
            {"id": 101, "name": "Lower ID", "phone": "89991112233", "email": "", "amount": 500, "created_at": "2026-01-01T12:00:00Z"},
            {"id": 202, "name": "Higher ID", "phone": "+79991112233", "email": "", "amount": 500, "created_at": "2026-01-01T12:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients[0].name == "Higher ID"

    def test_zero_valued_amounts(self):
        records = [
            {"id": 1, "name": "Zero A", "phone": "89991112233", "email": "a@ex.com", "amount": 0, "created_at": "2026-01-01T00:00:00Z"},
            {"id": 2, "name": "Zero B", "phone": "89991112233", "email": "b@ex.com", "amount": 0, "created_at": "2026-01-02T00:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients[0].name == "Zero B"
        assert res.clients[0].amount == 0
        assert res.stats.unique == 1
        assert res.stats.duplicates_merged == 1

    def test_empty_email_preserved_and_no_merging_from_losers(self):
        records = [
            {"id": 1, "name": "Winner", "phone": "89991112233", "email": "", "amount": 1000, "created_at": "2026-01-01T00:00:00Z"},
            {"id": 2, "name": "Loser", "phone": "89991112233", "email": "donor@example.com", "amount": 100, "created_at": "2026-01-01T00:00:00Z"},
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients[0].name == "Winner"
        assert res.clients[0].email == ""  # Must NOT be donor@example.com

    def test_empty_input_dataset(self):
        res = deduplicate_and_calculate_stats([])
        assert res.clients == []
        assert res.stats.received == 0
        assert res.stats.unique == 0
        assert res.stats.duplicates_merged == 0
        assert res.stats.invalid_dropped == 0

    def test_all_invalid_records(self):
        records = [
            {"id": 1, "phone": "invalid"},
            {"id": 2, "phone": "123"},
            {"id": 3, "phone": ""},
            "not a dict",
        ]
        res = deduplicate_and_calculate_stats(records)
        assert res.clients == []
        assert res.stats.received == 4
        assert res.stats.unique == 0
        assert res.stats.duplicates_merged == 0
        assert res.stats.invalid_dropped == 4
        assert res.stats.received == res.stats.unique + res.stats.duplicates_merged + res.stats.invalid_dropped
