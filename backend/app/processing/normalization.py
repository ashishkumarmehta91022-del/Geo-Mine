"""Lightweight text normalization.

Rules (deliberately conservative — the original content must stay traceable):
- normalize line endings (CRLF/CR -> LF)
- remove null characters
- collapse runs of SPACES only (tabs are meaningful in sheet TSV text)
- trim trailing whitespace per line
- collapse excessive blank lines (3+ -> 2)

Never done here: rewriting sentences, summarizing, inferring values,
correcting numbers, changing units, inventing headings.
"""

import re

_SPACE_RUN = re.compile(r" {2,}")
_NULL_CHARS = re.compile(r"\x00")


def normalize_text(raw: str | None) -> str:
    """Return normalized text; empty string for None/empty input."""
    if not raw:
        return ""

    text = _NULL_CHARS.sub("", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [_SPACE_RUN.sub(" ", line).rstrip() for line in text.split("\n")]

    # Collapse 3+ consecutive blank lines to exactly one blank line.
    normalized: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        normalized.append(line)

    return "\n".join(normalized).strip("\n")
