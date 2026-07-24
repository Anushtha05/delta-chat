"""Text normalization utilities for canonical element content.

The normalize() function produces a stable, comparable form of text:
- Lowercase
- Collapse all whitespace to single spaces
- Strip leading/trailing whitespace
- Remove punctuation EXCEPT characters that are part of numeric/unit expressions
  (periods in decimals, slashes in units like m/s, hyphens in ranges like 10-20)
"""

import re

# Punctuation to strip: everything that's not alphanumeric, whitespace, period, slash,
# hyphen, or common unit symbols (°, %, µ, ±)
_STRIP_PUNCT = re.compile(r"[^\w\s.\-/°%µ±]", re.UNICODE)

# Collapse multiple whitespace into one
_COLLAPSE_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalize text content for comparison purposes.

    Preserves numbers, units, and their relationships while stripping
    irrelevant formatting differences.

    Examples:
        >>> normalize("  VALVE  TAG:  XV-100  ")
        'valve tag xv-100'
        >>> normalize("3.5 m/s ± 0.1")
        '3.5 m/s ± 0.1'
        >>> normalize("P&ID Drawing #42")
        'pid drawing 42'
        >>> normalize("this.")
        'this.'
        >>> normalize("this .")
        'this.'
    """
    if not text:
        return ""
    result = text.lower()
    result = _STRIP_PUNCT.sub("", result)
    result = _COLLAPSE_WS.sub(" ", result)
    result = result.strip()
    # Collapse space before trailing period/punctuation (e.g., "word ." → "word.")
    result = re.sub(r'\s+([.\-/])\s*$', r'\1', result)
    # Collapse space before period mid-text too (e.g., "this . next" → "this. next")
    result = re.sub(r'\s+\.', '.', result)
    return result
