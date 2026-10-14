import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_upstream_orders():
    """Load the canonical 17-record sample data fetched from upstream."""
    sample_file = FIXTURES_DIR / "upstream_orders_sample.json"
    with open(sample_file, "r", encoding="utf-8") as f:
        return json.load(f)
