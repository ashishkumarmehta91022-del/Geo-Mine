"""Deterministic validation & data-quality engine (Step 6).

Rules are pure functions over value candidates — no LLM, no randomness.
Validation NEVER modifies extracted data; it only describes and flags.
"""
