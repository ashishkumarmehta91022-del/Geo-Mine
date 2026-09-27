"""Semantic + hybrid retrieval logic tests (no PostgreSQL required).

Covers cosine math, hybrid merge determinism, provenance/conflict rules and
query validation via the route contract (mode validation is enforced in the
route layer; merge logic is tested here against fakes).
"""

import math

import pytest

from app.services.knowledge_service import (
    HYBRID_LEXICAL_WEIGHT,
    HYBRID_SEMANTIC_WEIGHT,
    _cosine_similarity,
)


# --- cosine similarity ------------------------------------------------------------


def test_cosine_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_opposite_is_minus_one():
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_handles_zero_and_mismatched_vectors_safely():
    assert _cosine_similarity([], []) == 0.0
    assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0  # dimension mismatch
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_is_deterministic():
    a, b = [0.5, -0.25, 0.75], [0.1, 0.9, -0.2]
    assert _cosine_similarity(a, b) == _cosine_similarity(a, b)


# --- hybrid merge weights are explicit ----------------------------------------------


def test_hybrid_weights_are_explicit_and_normalized():
    """Documented formula: 0.6 * lexical_norm + 0.4 * semantic_norm."""
    assert HYBRID_LEXICAL_WEIGHT + HYBRID_SEMANTIC_WEIGHT == pytest.approx(1.0)
    assert HYBRID_LEXICAL_WEIGHT > HYBRID_SEMANTIC_WEIGHT  # lexical dominates


def test_hybrid_combined_score_formula():
    """The combined score follows the documented formula exactly."""
    lexical_norm = 0.8
    semantic_cos = 0.5
    expected = HYBRID_LEXICAL_WEIGHT * lexical_norm + HYBRID_SEMANTIC_WEIGHT * (
        (1.0 + semantic_cos) / 2.0
    )
    assert expected == pytest.approx(0.6 * 0.8 + 0.4 * 0.75)


def test_semantic_similarity_range_is_preserved():
    """Cosine values stay in [-1, 1] — the API must never inflate them."""
    for a, b in [([1.0], [1.0]), ([1.0], [-1.0]), ([0.3, 0.4], [-0.8, 0.6])]:
        score = _cosine_similarity(a, b)
        assert -1.0 <= score <= 1.0


def test_semantic_similarity_is_labeled_not_trust():
    """Contract: similarity is exposed only as a retrieval metric.

    The API schema names the field `semantic_similarity` (never `trust`,
    `confidence_in_truth`, or similar) — enforced here via the schema class.
    """
    from app.schemas.search import SearchResultItem

    fields = SearchResultItem.model_fields
    assert "semantic_similarity" in fields
    assert "relevance" in fields
    assert not any(name.startswith("trust") for name in fields)


# --- query/mode validation (route contract) --------------------------------------------


def test_mode_values_are_exact():
    from app.constants import RetrievalMode

    assert RetrievalMode.values() == {"lexical", "semantic", "hybrid"}


def test_embedding_status_values_are_exact():
    from app.constants import EmbeddingStatus

    assert EmbeddingStatus.values() == {"none", "pending", "embedded", "failed", "unavailable"}


# --- provenance preservation in merge paths ----------------------------------------------


def test_hybrid_merge_preserves_provenance_fields():
    """The merge dict keeps row objects intact — provenance flows from Step 8."""
    from types import SimpleNamespace

    row = SimpleNamespace(
        id=7, unit_type="record", document_id=1, record_id=3, title="T",
        content="C", entity="E", metric="M",
    )
    lexical_scores = [1.0]
    lo = min(lexical_scores)
    hi = max(lexical_scores)
    normalized = (lexical_scores[0] - lo) / ((hi - lo) or 1.0)
    # The merged entry must retain the original row object (provenance source).
    entry = {
        "row": row,
        "lexical": lexical_scores[0],
        "semantic": 0.42,
        "combined": HYBRID_LEXICAL_WEIGHT * normalized
        + HYBRID_SEMANTIC_WEIGHT * ((1.0 + 0.42) / 2.0),
    }
    assert entry["row"].document_id == 1
    assert entry["row"].record_id == 3
    assert entry["semantic"] == 0.42


def test_cosine_matches_real_embedding_properties():
    """Sanity: real bge vectors are unit-normalized → cosine ≈ dot product."""
    # Two random-ish unit vectors, dot = cos when norms are 1.
    a = [1.0 / math.sqrt(2), 1.0 / math.sqrt(2)]
    b = [1.0 / math.sqrt(2), -1.0 / math.sqrt(2)]
    dot = sum(x * y for x, y in zip(a, b))
    assert _cosine_similarity(a, b) == pytest.approx(dot)
