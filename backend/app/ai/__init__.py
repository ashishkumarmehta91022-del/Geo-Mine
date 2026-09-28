"""AI Query layer (Step 10): evidence construction, conflict detection and
retrieval-grounded orchestration on top of the Step 8/9 retrieval index."""

from app.ai.evidence import ConflictGroup, Evidence, build_evidence, detect_conflicts
from app.ai.service import audit_metadata, parse_llm_response, run_ai_query

__all__ = [
    "ConflictGroup",
    "Evidence",
    "audit_metadata",
    "build_evidence",
    "detect_conflicts",
    "parse_llm_response",
    "run_ai_query",
]
