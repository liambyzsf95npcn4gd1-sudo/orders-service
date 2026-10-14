# Orders Normalizer & Client Deduplication Service

A high-performance, deterministic HTTP service built with **Python 3.10+**, **FastAPI**, and **Pydantic v2**. The service fetches raw orders from an upstream API, normalizes Russian phone numbers to strict international `+7XXXXXXXXXX` format, removes invalid records, resolves duplicates through a prioritized cascade, and returns clean client entities along with balanced accounting statistics.

---

## 1. Architecture & Design Principles

```
orders-service/
├── app/
│   ├── __init__.py
│   ├── config.py             # Settings (upstream URL, timeouts, network options)
│   ├── models.py             # Pydantic schemas (RawOrder, ClientItem, Stats, OrdersResponse)
│   ├── normalizer.py         # Russian phone normalization & character validation
│   ├── deduplicator.py       # Grouping, tie-breaking priority cascade, accounting invariants
│   ├── client.py             # Resilient async HTTP client with finite timeouts & error translation
│   └── main.py               # FastAPI application entrypoint with GET / and GET /health
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures and sample data loader
│   ├── fixtures/
│   │   └── upstream_orders_sample.json # Canonical 17-record upstream fixture
│   ├── test_normalizer.py    # Unit tests for all valid/invalid phone permutations
│   ├── test_deduplicator.py  # Unit tests for priority cascade, edge cases, invariants
│   ├── test_api.py           # Integration tests for FastAPI endpoints with mocks
│   └── test_live_smoke.py    # Live smoke test against live upstream API
├── Dockerfile                # Multi-stage production container configuration (python:3.11-slim)
├── .dockerignore
├── pytest.ini                # Pytest markers configuration (isolating live tests)
├── requirements.txt          # Pinned dependency manifest
├── CONTRACT_AND_ASSUMPTIONS.md # Detailed specification of contract and reconciliation
└── README.md
```

### Key Architectural Invariants
1. **Stateless & Non-mutating**: The service never mutates raw input data or persists to a database.
2. **Determinism**: The same input payload always produces the exact same output. Clients are sorted in ascending order by normalized phone (`+7XXXXXXXXXX`).
3. **Fail-Closed Upstream Handling**: Upstream network timeouts, HTTP errors (4xx/5xx), or non-conforming JSON payloads immediately raise explicit gateway errors (`502 Bad Gateway` or `504 Gateway Timeout`). The service never silently fabricates empty successful responses on failure.
4. **Strict Atomic Record Integrity**: The winning duplicate record is retained as an atomic unit. No fields (e.g. email) are merged or borrowed from losing duplicate records.

---

## 2. Russian Phone Normalization Policy

Russian numbers adhere to ITU-T E.164 and the national numbering plan (+7 country code, 10-digit national number starting with 3–9):

1. **Character Whitelist**: Only digits and standard formatting characters are permitted: `+`, ` `, `(`, `)`, `-`, `.`. Any string containing Latin/Cyrillic letters or unexpected punctuation (e.g., `"не указан"`, `"call me"`, `"123-abc"`) is **strictly dropped as invalid**, rather than silently stripping the text.
2. **11-digit numbers starting with `8`**: Normalized to start with `+7` (e.g., `8 (999) 123 45 67` -> `+79991234567`).
3. **11-digit numbers starting with `7`**: Normalized to start with `+7` (e.g., `+7 999 123-45-67` or `79991234567` -> `+79991234567`).
4. **10-digit Russian national numbers starting with `3–9`**: Prepend country code `+7` (e.g., `9005551212` -> `+79005551212`).
5. **All other formats**: Less than 10 digits, 10 digits starting with `0, 1, 2`, 11 digits with non-Russian prefixes, 12+ digits, or empty/null values are rejected (`invalid_dropped += 1`).

**Normalized phone format**: Exactly 12 characters matching `^\+7[3-9]\d{9}$` (e.g. `+79005551212`).

---

## 3. Deduplication & Priority Rules

Valid records are grouped by their normalized phone number (`+7XXXXXXXXXX`). Within each group, exactly one record is selected:
1. **Highest `amount`**: Primary sorting criteria. (e.g., `amount: 5000` beats `amount: 1000`).
2. **Latest `created_at`**: If amounts are equal, the newest ISO 8601 timestamp wins.
3. **Deterministic tie-breaker**: If both amount and timestamp are identical, highest record `id` (`max(id)`) wins.

---

## 4. Accounting Invariant & Statistics

The top-level `stats` block tracks:
- `received`: Total raw orders received from upstream.
- `unique`: Number of retained unique client entities.
- `duplicates_merged`: Count of valid duplicate records discarded.
- `invalid_dropped`: Count of records rejected due to phone or schema validation.

$$\text{received} \equiv \text{unique} + \text{duplicates\_merged} + \text{invalid\_dropped}$$

On the upstream 17-record dataset:
- `received`: 17
- `unique`: 8
- `duplicates_merged`: 5
- `invalid_dropped`: 4
- Conservation: $8 + 5 + 4 = 17$ (Invariant holds).

> **Note on Statistical Discrepancy**: Some informal examples in problem statements may mistakenly quote `duplicates_merged: 4` by counting *groups* of duplicate numbers rather than individual *merged duplicate records*. In our dataset, phone `+79991234567` contains 3 records (1 retained, 2 merged), and 3 other numbers contain 2 records each (1 retained, 1 merged each). The total number of duplicate records discarded is $2 + 1 + 1 + 1 = 5$. Counting groups ($4$) violates the invariant ($8 + 4 + 4 = 16 \neq 17$). Our code dynamically enforces the strict record-level accounting invariant without hardcoding.

---

## 5. Local Installation & Startup

### Environment & Python Versions
- **Container Environment**: Dockerfile is pinned to `python:3.11-slim`.
- **Local Development**: Tested on Python 3.11, 3.12, 3.14.

### Installation
```bash
git clone <repository-url>
cd orders-service
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Running Locally
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000/](http://localhost:8000/) to view the output.
Health check: [http://localhost:8000/health](http://localhost:8000/health).

### Running with Docker
```bash
docker build -t orders-service .
docker run -p 8000:8000 orders-service
```

---

## 6. Automated Testing

The automated test suite contains unit, integration, and live smoke tests covering:
- Valid 10-digit and 11-digit phone formats with `+7XXXXXXXXXX` verification.
- Alphabetic noise, empty strings, short numbers, and invalid area code prefixes.
- 3+ duplicate records, amount precedence over recency, timestamp resolution, deterministic ID tie-breaking, and zero amounts.
- Preservation of empty email strings without cross-record merging.
- Invariant validation across synthetic and edge-case datasets.
- Deterministic response idempotency and mock upstream failure modes (HTTP 500, timeout, malformed JSON).
- Separation of hermetic unit tests from live network tests.

Run hermetic test suite (offline/fast):
```bash
pytest -v
```

Run live network smoke test against `https://test.ooobs.ru/api/orders`:
```bash
pytest -v -m live
```

---

## 7. API Specification

### Endpoint: `GET /`

#### Response: `200 OK`
```json
{
  "clients": [
    {
      "name": "Павел Орлов",
      "phone": "+79005551212",
      "email": "pavel@example.com",
      "amount": 300
    },
    {
      "name": "Олег Кузнецов",
      "phone": "+79031112233",
      "email": "",
      "amount": 7500
    },
    {
      "name": "Мария С.",
      "phone": "+79160000001",
      "email": "maria@example.com",
      "amount": 200
    },
    {
      "name": "Дмитрий Лебедев",
      "phone": "+79164455667",
      "email": "dmitry@example.com",
      "amount": 12000
    },
    {
      "name": "Анна В.",
      "phone": "+79219998877",
      "email": "",
      "amount": 1500
    },
    {
      "name": "Елена Морозова",
      "phone": "+79261234567",
      "email": "elena@example.com",
      "amount": 9000
    },
    {
      "name": "Сергей Зайцев",
      "phone": "+79991110000",
      "email": "sergey@example.com",
      "amount": 450
    },
    {
      "name": "Иван П.",
      "phone": "+79991234567",
      "email": "",
      "amount": 5000
    }
  ],
  "stats": {
    "received": 17,
    "unique": 8,
    "duplicates_merged": 5,
    "invalid_dropped": 4
  }
}
```
