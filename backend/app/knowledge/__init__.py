"""Knowledge base / retrieval layer (Step 8).

Deterministic indexing + search over the authoritative source tables.
This layer is NOT a source of truth, NOT RAG, and contains no LLM — every
result carries provenance pointing back to documents/pages/records.
"""
