"""Structured-record creation layer (Step 7).

Turns raw extraction units (pages/sheets/tables/OCR text) into traceable
`extracted_records` rows. Deterministic only: no LLM, no semantic guessing,
no OCR auto-correction — an uncertain "1O5" is stored as "1O5".
"""
