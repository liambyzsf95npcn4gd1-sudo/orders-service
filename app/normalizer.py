"""Phone normalization module adhering to the documented Russian phone policy."""

import re
from typing import Optional

# Characters permitted in phone strings: digits and standard formatting characters
ALLOWED_CHARS_PATTERN = re.compile(r"^[0-9\+\s\(\)\-\.]+$")


def normalize_russian_phone(raw_phone: Optional[str]) -> Optional[str]:
    """Normalize a raw Russian phone number to an 11-digit string starting with 7.

    Rules:
    1. Allow digits and common formatting characters: +, spaces, (), -, .
    2. Reject alphabetic characters and arbitrary text rather than silently deleting them.
    3. Normalize an 11-digit number beginning with 8 to the same number beginning with 7.
    4. Preserve an 11-digit number beginning with 7.
    5. Accept a valid 10-digit Russian national number beginning with 3-9 by prepending 7.
    6. Reject all other phone formats.

    Returns:
        11-digit normalized string (e.g. '79991234567') or None if invalid.
    """
    if raw_phone is None:
        return None

    if not isinstance(raw_phone, str):
        return None

    stripped = raw_phone.strip()
    if not stripped:
        return None

    # Reject if any non-allowed characters (e.g. letters, emojis, unsupported punctuation) exist
    if not ALLOWED_CHARS_PATTERN.match(stripped):
        return None

    # Extract digits only
    digits = re.sub(r"\D", "", stripped)

    # 11-digit number beginning with 8 -> normalize to +7
    if len(digits) == 11 and digits.startswith("8"):
        return "+7" + digits[1:]

    # 11-digit number beginning with 7 -> normalize to +7
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits

    # 10-digit Russian national number beginning with 3-9 -> prepend +7
    if len(digits) == 10 and digits[0] in "3456789":
        return "+7" + digits

    # All other formats rejected
    return None
