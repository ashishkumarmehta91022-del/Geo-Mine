"""Deterministic embedding-input construction.

Embedding input must carry enough context for semantic retrieval: a record is
never embedded as a bare "1200" — it embeds entity + metric + period + unit +
source value. Raw values are preserved verbatim in the index row; this text is
only the retrieval representation.
"""

from app.knowledge.units import IndexUnitDraft

SECTION_SEPARATOR = " | "


def build_embedding_input(draft: IndexUnitDraft) -> str:
    """Contextual, deterministic text for one retrieval unit.

    - record: "record — <entity> — <metric> — value <value> <unit> — period <period>"
    - page:   "page — <title> | <content>"
    - validation: "validation — <rule> (<status>) | <message>"
    Unit-type prefix keeps semantic spaces distinguishable across unit kinds.
    """
    if draft.unit_type == "record":
        parts = ["record"]
        if draft.entity:
            parts.append(draft.entity)
        if draft.metric:
            parts.append(draft.metric)
        value_bits = []
        if draft.content:
            value_bits.append(f"value {draft.content}")
        value_bits.append(f"unit {draft.unit or 'unknown'}")
        parts.append(" ".join(value_bits))
        if draft.reporting_period:
            parts.append(f"period {draft.reporting_period}")
        if draft.validation_status:
            parts.append(f"validation {draft.validation_status}")
        return SECTION_SEPARATOR.join(parts).replace("\n", " ")

    if draft.unit_type == "validation":
        parts = ["validation"]
        if draft.title:
            parts.append(draft.title)
        if draft.content:
            parts.append(draft.content)
        return SECTION_SEPARATOR.join(parts).replace("\n", " ")

    # page (default): title gives document/page context, content the body text.
    parts = ["page"]
    if draft.title:
        parts.append(draft.title)
    if draft.content:
        parts.append(draft.content)
    return SECTION_SEPARATOR.join(parts)
