# Phase 0: Contract and Assumptions Specification

## 1. Upstream Contract Inspection

Endpoint: `https://test.ooobs.ru/api/orders`
Method: `GET`
Protocol: HTTPS / HTTP/1.1
Observed Response Content-Type: `application/json; charset=utf-8`

### Upstream Order Record Schema

Each item in the upstream list represents a customer order with the following structure:

```json
{
  "id": 1,
  "name": "Иван Петров",
  "phone": "+7 999 123-45-67",
  "email": "ivan@example.com",
  "amount": 1000,
  "created_at": "2026-10-01T10:00:00Z"
}
```

Fields:
- `id`: Integer uniquely identifying the raw order. Used as a deterministic tie-breaker (higher ID wins if amount and created_at are identical).
- `name`: String containing client name.
- `phone`: Raw string input for the phone number (may contain formatting, national prefixes, invalid text, or empty values).
- `email`: String containing client email address; may be empty (`""`).
- `amount`: Numeric (integer or float); may be zero (`0`) or positive.
- `created_at`: ISO 8601 formatted timestamp string in UTC (e.g. `YYYY-MM-DDTHH:MM:SSZ`).

---

## 2. Phone Normalization Rules

The service strictly adheres to the recommended Russian phone policy:

1. **Character Validation**:
   - Only digits (`0-9`) and standard phone formatting characters are permitted:
     - Plus signs (`+`)
     - Spaces (` `)
     - Parentheses (`(`, `)`)
     - Hyphens (`-`)
     - Dots (`.`)
   - If any alphabetic character, Cyrillic letter, or other arbitrary text is present (e.g., `"не указан"`, `"call me"`), the record is **strictly rejected as invalid**, rather than silently stripping characters.

2. **Digit Extraction & Prefix Normalization**:
   - Strip all allowed formatting characters to extract the raw digit sequence.
   - **11 digits starting with `8`**: Normalize to 11 digits starting with `7` (e.g. `8 (999) 123 45 67` -> `79991234567`).
   - **11 digits starting with `7`**: Retain as-is (e.g. `+7 999 123-45-67` -> `79991234567`).
   - **10 digits starting with `3` through `9`**: Valid Russian national number without country prefix; normalize by prepending `7` (e.g. `9005551212` -> `79005551212`).
   - **All other formats**:
     - Less than 10 digits (e.g., `"123"`, `"+7 999"`): Rejected.
     - 10 digits starting with `0`, `1`, or `2`: Rejected (not standard Russian DEF/ABC area codes).
     - 11 digits starting with digits other than `7` or `8`: Rejected.
     - 12 or more digits: Rejected.
     - Empty string, whitespace-only, or `null`: Rejected.

3. **Output Format**:
   - The normalized phone is always an 11-digit string matching regex `^7[3-9]\d{9}$`.

---

## 3. Deduplication and Selection Rules

1. Group all valid records by their normalized 11-digit phone number.
2. For each phone group, select exactly **one** winning source record using the following priority cascade:
   - **Primary rule**: Highest `amount` (numeric comparison; e.g. `5000 > 1000`).
   - **Secondary rule**: If amounts are equal, latest `created_at` timestamp (parsed as UTC datetime).
   - **Deterministic tie-breaker**: If both `amount` and `created_at` are equal, highest record `id` (`max(id)`).
3. **Record Integrity & No Merging**:
   - The winning record is preserved as an atomic unit.
   - Values are never merged or cherry-picked from losing records. Specifically, if the winning record has an empty email `""`, it must be returned as `""`, even if losing duplicate records contained non-empty email addresses.
4. **Output Transformation**:
   - Each retained client contains only: `name`, `phone` (the normalized phone), `email`, `amount`.
   - Results are deterministically sorted by `phone` in ascending lexicographical order.

---

## 4. Statistics Rules and the Accounting Invariant

The top-level `stats` object tracks four discrete metrics:

- `received`: Total number of raw input records fetched from the upstream API.
- `unique`: Total number of retained clients (equal to the number of distinct valid normalized phones).
- `duplicates_merged`: Total number of valid records that were discarded because a higher-priority record won for that phone. Calculated as $\sum (\text{len}(\text{group}) - 1)$ across all valid phone groups.
- `invalid_dropped`: Total number of records that were rejected by phone validation (or malformed record structure).

### Fundamental Accounting Invariant

$$\text{received} \equiv \text{unique} + \text{duplicates\_merged} + \text{invalid\_dropped}$$

Every input record is partitioned into exactly one of three disjoint sets:
1. Retained as the winner for a valid phone group (`unique`).
2. Discarded as a duplicate within a valid phone group (`duplicates_merged`).
3. Discarded due to invalid phone format or malformed structure (`invalid_dropped`).

Counters are calculated dynamically from the processed data and must never be hardcoded or fabricated.

---

## 5. Inconsistency Analysis on Sample Upstream Data

Inspection of the 17 actual upstream records yields:

| ID | Name | Raw Phone | Amount | Created At | Normalization Result | Classification |
|---|---|---|---|---|---|---|
| 1 | Иван Петров | +7 999 123-45-67 | 1000 | 2026-10-01T10:00:00Z | 79991234567 | Duplicate (lost to ID 2 by amount) |
| 2 | Иван П. | 8 (999) 123 45 67 | 5000 | 2026-10-02T11:00:00Z | 79991234567 | **Winner** (max amount 5000) |
| 3 | И. Петров | 79991234567 | 3000 | 2026-10-03T09:00:00Z | 79991234567 | Duplicate (lost to ID 2 by amount) |
| 4 | Мария Сидорова | 8-916-000-00-01 | 200 | 2026-10-01T12:00:00Z | 79160000001 | Duplicate (lost to ID 5 by created_at) |
| 5 | Мария С. | +7 (916) 000 00 01 | 200 | 2026-10-05T12:00:00Z | 79160000001 | **Winner** (equal amount 200, newer date) |
| 6 | Олег Кузнецов | 8 903 111 22 33 | 7500 | 2026-10-04T08:30:00Z | 79031112233 | **Winner** (single record) |
| 7 | Анна Волкова | +79219998877 | 0 | 2026-10-02T14:00:00Z | 79219998877 | Duplicate (lost to ID 8 by amount 0 < 1500) |
| 8 | Анна В. | 8 921 999 88 77 | 1500 | 2026-10-06T16:00:00Z | 79219998877 | **Winner** (max amount 1500) |
| 9 | Павел Орлов | 9005551212 | 300 | 2026-10-01T09:15:00Z | 79005551212 | **Winner** (10-digit normalized to 79005551212) |
| 10 | Елена Морозова | +7-926-123-45-67 | 9000 | 2026-10-03T13:00:00Z | 79261234567 | **Winner** (max amount 9000 beats newer ID 11) |
| 11 | Елена М. | 8 (926) 123-45-67 | 100 | 2026-10-07T10:00:00Z | 79261234567 | Duplicate (lost to ID 10 by amount 100 < 9000) |
| 12 | Сергей Зайцев | 8 999 111 00 00 | 450 | 2026-10-02T18:00:00Z | 79991110000 | **Winner** (single record) |
| 13 | Дмитрий Лебедев | +7 916 445 56 67 | 12000 | 2026-10-08T11:30:00Z | 79164455667 | **Winner** (single record) |
| 14 | Без телефона | 123 | 999 | 2026-10-01T00:00:00Z | None | **Invalid Dropped** (too short) |
| 15 | Пустой телефон | | 999 | 2026-10-01T00:00:00Z | None | **Invalid Dropped** (empty string) |
| 16 | Текст в поле | не указан | 999 | 2026-10-01T00:00:00Z | None | **Invalid Dropped** (alphabetic text) |
| 17 | Слишком коротко | +7 999 | 999 | 2026-10-01T00:00:00Z | None | **Invalid Dropped** (too short) |

### Reconciled Metrics:
- `received`: 17
- `unique`: 8
- `duplicates_merged`: 5 (ID 1, ID 3, ID 4, ID 7, ID 11)
- `invalid_dropped`: 4 (ID 14, ID 15, ID 16, ID 17)
- **Check**: $8 + 5 + 4 = 17 \equiv 17$.

### Pitfalls and Potential Inconsistencies Addressed:
1. **Counting duplicate groups vs duplicate records**: There are 4 phone numbers that have duplicates, but 5 records were merged because phone `79991234567` had 3 records (1 winner + 2 duplicates). Counting groups instead of records ($4$ instead of $5$) breaks the conservation invariant ($8 + 4 + 4 = 16 \neq 17$). Our code computes individual merged records.
2. **10-digit national numbers**: Record 9 (`9005551212`) has 10 digits starting with `9`. Naive 11-digit-only regex would drop it as invalid. Under our explicit policy, it is normalized to `79005551212`.
3. **Empty emails**: Winning records ID 2 and ID 8 have empty string emails. They must remain empty strings without borrowing from losing records.
4. **Older timestamp with larger amount**: Record 10 (`2026-10-03`, amount `9000`) beats Record 11 (`2026-10-07`, amount `100`) because amount takes precedence over recency.
