"""Report generation route (Step 11): POST /api/reports/generate.

Deterministic, provenance-grounded DOCX generation over validated structured
records. Response modes:
- default / format=docx → the generated .docx as a downloadable attachment
  (metadata echoed in the X-Report-* headers).
- format=json → JSON metadata only (useful for UIs/tests); the artifact
  itself is not persisted anywhere in this foundation step.

Error contract (honest failures only):
- 422 validation_error / empty_title / invalid_sections / unsupported_report_format …
- 503 database_unavailable — reports over the record store are impossible
  without it; the generator never returns an empty-but-successful report.

Audit: one `report.generate` AuditLog row per successful generation with
safe metadata only (status, report type, format, counts, fingerprint) —
never document contents, never record values.
"""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import AuditLog
from app.reports.service import audit_metadata, generate_report, log_report_generation
from app.reports.spec import build_specification
from app.schemas.reports import ReportGenerateRequest, ReportGenerateResponse

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.post("/generate")
def generate_report_route(
    payload: ReportGenerateRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Generate a deterministic, provenance-grounded report.

    The LLM is NOT involved anywhere in this pipeline; every value in the
    generated document originates from validated structured records stored
    by the platform. Conflicting values are reported with their sources and
    marked REVIEW REQUIRED — never silently resolved.
    """
    try:
        # "json" selects the RESPONSE representation (metadata only); the
        # generated artifact itself is always DOCX in this foundation.
        json_mode = (payload.output_format or "docx").strip().lower() == "json"
        specification = build_specification(
            title=payload.title,
            report_type=payload.report_type,
            reporting_period=payload.reporting_period,
            document_ids=payload.document_ids,
            entities=payload.entities,
            metrics=payload.metrics,
            sections=payload.sections,
            output_format="docx",
            filters=(payload.filters.model_dump() if payload.filters else None),
            requester=payload.requester,
        )

        try:
            result = generate_report(specification, db=db)
        except DatabaseUnavailableError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("Report generation failed at the database level")
            raise DatabaseUnavailableError from exc

        log_report_generation(db, result)

    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 — keep the JSON error contract
        logger.exception("Report generation failed unexpectedly")
        raise AppError(
            status_code=500,
            code="report_generation_failed",
            message="Report generation failed unexpectedly.",
        ) from exc

    metadata = audit_metadata(result)

    if json_mode:
        return ReportGenerateResponse(
            status=result["status"],
            report_id=result["report_id"],
            fingerprint=result["fingerprint"],
            specification=result["specification"],
            reporting_period=result["reporting_period"],
            generated_at=result["generated_at"],
            artifact=result["artifact"],
            summary=result["summary"],
            conflict_count=result["conflict_count"],
            conflicts=result["conflicts"],
            evidence_count=result["evidence_count"],
            validation_warning_error_count=result["validation_warning_error_count"],
            missing_value_count=result["missing_value_count"],
            sections_built=result["sections_built"],
            limitations=result["limitations"],
        )

    headers = {
        "X-Report-Id": result["report_id"],
        "X-Report-Fingerprint": result["fingerprint"],
        "X-Report-Records": str(metadata["record_count"]),
        "X-Report-Conflicts": str(metadata["conflict_count"]),
        "X-Report-Validation-Flags": str(metadata["validation_warning_error_count"]),
        "X-Report-Missing": str(metadata["missing_value_count"]),
        "X-Report-Status": metadata["status"],
    }
    return Response(
        content=result["docx_bytes"],
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            **headers,
            "Content-Disposition": f'attachment; filename="{result["artifact"]["filename"]}"',
        },
    )
