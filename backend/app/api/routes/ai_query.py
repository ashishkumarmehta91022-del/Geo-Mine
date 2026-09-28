"""AI Query route (Step 10): POST /api/ai/query.

Retrieval-grounded answering with honest status mapping:
- 422 empty/too-long question, unsupported mode
- 503 database unavailable (retrieval impossible ⇒ no evidence ⇒ no answer)
- 200 with status=insufficient_evidence | llm_unavailable | llm_error | ok

Observability: one AuditLog row per query with safe metadata only (status,
mode, evidence count, provider/model, latency) — never the question text,
answers, or credentials.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.service import audit_metadata, run_ai_query
from app.exceptions import AppError, DatabaseUnavailableError
from app.models import AuditLog
from app.schemas.ai_query import AIQueryRequest, AIQueryResponse
from app.db import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=AIQueryResponse)
def ai_query_route(
    payload: AIQueryRequest,
    db: Session = Depends(get_db),
) -> AIQueryResponse:
    """Answer a question ONLY from retrieved project evidence.

    The LLM never searches the database and never answers without evidence.
    Unavailability (LLM not configured, provider failure, malformed response)
    is reported honestly — no fabricated answers, ever.
    """
    try:
        result = run_ai_query(db, payload.question, mode=payload.mode, limit=payload.limit)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("AI query failed at the database level")
        raise DatabaseUnavailableError from exc

    # Safe audit trail (metadata only).
    try:
        db.add(AuditLog(action="ai.query", entity_type="ai_query", details=audit_metadata(result)))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("AI query audit write failed (query result unaffected)")

    if result["status"] == "llm_unavailable":
        raise AppError(
            status_code=503,
            code="llm_unavailable",
            message="No LLM provider is configured; answers cannot be generated without one.",
        )

    return AIQueryResponse(**result)
