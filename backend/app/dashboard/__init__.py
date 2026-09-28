"""Production dashboard (Step 14) — read-only operational aggregation.

The dashboard composes counts and statuses from EXISTING source-of-truth
tables and services (documents, records, validation, knowledge index,
intelligence, health) into one honest operational view. It duplicates no
business logic, persists nothing, and — when PostgreSQL is unreachable —
reports `data_available=False` with metric sections absent rather than
showing fabricated zeroes.
"""
