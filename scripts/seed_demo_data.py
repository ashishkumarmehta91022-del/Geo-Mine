"""Seed a small DEMO dataset for development.

*** DEMO / DEVELOPMENT DATA ONLY ***
The values below (DEMO_MINE_A, DEMO_COAL_PRODUCTION, …) are generic sample
data. They are NOT real CMPDI/CIL figures and must never be presented as
government data.

Usage (from the repo root, with the backend venv active):
    python scripts/seed_demo_data.py            # insert if not already present
    python scripts/seed_demo_data.py --reset    # delete previous DEMO rows first

Requires a reachable PostgreSQL database (see README — `alembic upgrade head`
must have been run).
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the repo root: import the backend app package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    Document,
    DocumentPage,
    ExtractedRecord,
    ValidationResult,
)
from app.services import knowledge_service  # noqa: E402

DEMO_FILENAME = "DEMO_borehole_log.pdf"


def previous_demo_document(session) -> Document | None:
    return session.execute(
        select(Document).where(Document.filename == DEMO_FILENAME)
    ).scalar_one_or_none()


def seed() -> None:
    with SessionLocal() as session:
        existing = previous_demo_document(session)
        if existing is not None:
            print(f"DEMO data already present (document id={existing.id}) — nothing to do.")
            print("Re-run with --reset to delete and re-insert it.")
            return

        document = Document(
            filename=DEMO_FILENAME,
            document_type="exploration_report",
            source="demo_seed",
            storage_reference="demo/DEMO_borehole_log.pdf",
            status="processed",
            processed_at=datetime.now(timezone.utc),
        )
        session.add(document)
        session.flush()

        page1 = DocumentPage(
            document_id=document.id,
            page_number=1,
            extracted_text="DEMO PAGE 1 — sample borehole log header (development seed data).",
            processing_status="extracted",
        )
        page2 = DocumentPage(
            document_id=document.id,
            page_number=2,
            extracted_text="DEMO PAGE 2 — sample production summary table (development seed data).",
            processing_status="extracted",
        )
        session.add_all([page1, page2])
        session.flush()

        # Keep the legacy sync column aligned the way the Step 4 pipeline does.
        for page in (page1, page2):
            page.processing_status = page.extraction_status

        records = [
            ExtractedRecord(
                document_id=document.id,
                page_id=page2.id,
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1234.5678,
                unit="DEMO_tonnes",
                reporting_period="DEMO_2026-26",
                source_reference="DEMO page 2, table 1",
                confidence=0.9500,
                validation_status="valid",
                value_raw="1234.5678",  # Step 7: verbatim source value
                normalized_value="1234.5678",
                extraction_method="spreadsheet",
                record_metadata={"demo": True},
            ),
            ExtractedRecord(
                document_id=document.id,
                page_id=page2.id,
                record_type="coal_production",
                entity_name="DEMO_MINE_B",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=987.6543,
                unit="DEMO_tonnes",
                reporting_period="DEMO_2026-26",
                source_reference="DEMO page 2, table 1",
                confidence=0.8800,
                validation_status="pending",
                value_raw="987.6543",
                normalized_value="987.6543",
                extraction_method="spreadsheet",
                record_metadata={"demo": True},
            ),
            ExtractedRecord(
                document_id=document.id,
                page_id=page1.id,
                record_type="borehole",
                entity_name="DEMO_BOREHOLE_01",
                metric_name="DEMO_DEPTH",
                metric_value=312.4000,
                unit="DEMO_m",
                reporting_period=None,
                source_reference="DEMO page 1, header",
                confidence=0.7200,
                validation_status="pending",
                value_raw="312.4",
                normalized_value="312.4",
                extraction_method="native_text",
                record_metadata={"demo": True},
            ),
        ]
        session.add_all(records)
        session.flush()

        session.add(
            ValidationResult(
                document_id=document.id,          # Step 6: required provenance link
                page_id=page2.id,
                extracted_record_id=records[0].id,
                source_reference="DEMO page 2, table 1",
                rule_code="range_check",  # Step 6: validation_type renamed to rule_code
                status="pass",
                severity="info",
                message="DEMO value within expected development range.",
                original_value="1234.5678",   # Step 6: original_value (was actual_value)
                expected_value="0 .. 100000",
            )
        )
        session.add(
            AuditLog(
                action="seed.demo_data_loaded",
                entity_type="document",
                entity_id=document.id,
                details={"demo": True, "seeded_by": "scripts/seed_demo_data.py"},
            )
        )
        # (audit row is committed with the seed transaction below)

        session.commit()

        # Make the DEMO document searchable (Step 8 index; Step 9 embeddings
        # stay optional/best-effort exactly like the normal pipeline).
        indexed = knowledge_service.index_document(SessionLocal(), document.id)

        print("DEMO data inserted (development sample data only, not real figures):")
        print(f"  document id={document.id}  pages=2  extracted_records=3")
        print(f"  validation_results=1  audit_logs=1  indexed_units={indexed}")


def reset() -> None:
    with SessionLocal() as session:
        existing = previous_demo_document(session)
        if existing is None:
            print("No DEMO data found — nothing to reset.")
            return
        session.delete(existing)  # cascades to pages/records/validation results
        session.commit()
        print("DEMO data deleted.")


def main() -> None:
    print("*** DEMO / DEVELOPMENT DATA — generic sample values, NOT real CMPDI/CIL figures ***")
    parser = argparse.ArgumentParser(description="Seed or reset DEMO development data.")
    parser.add_argument("--reset", action="store_true", help="delete previously seeded DEMO rows")
    args = parser.parse_args()
    reset() if args.reset else seed()


if __name__ == "__main__":
    main()
