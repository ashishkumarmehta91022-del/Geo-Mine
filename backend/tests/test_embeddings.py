"""Embedding layer tests (no PostgreSQL required)."""

import pytest

from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderUnavailableError,
    EmbeddingResult,
)
from app.embeddings.config import EmbeddingConfig
from app.embeddings.inputs import build_embedding_input
from app.embeddings.service import (
    embed_texts,
    embedding_available,
    set_embedding_provider,
)
from app.knowledge.units import IndexUnitDraft


class FakeProvider(EmbeddingProvider):
    """Deterministic fake — verifies the same input yields the same vector."""

    name = "fake"
    model = "fake-model"
    dimensions = 4

    def is_available(self) -> bool:
        return True

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        vectors = [
            [float(len(t) % 7), 1.0, 0.5, 0.25] for t in texts
        ]
        return EmbeddingResult(
            vectors=vectors, provider=self.name, model=self.model, dimensions=self.dimensions
        )


class ExplodingProvider(EmbeddingProvider):
    name = "exploding"
    model = "none"
    dimensions = 0

    def is_available(self) -> bool:
        return True

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingProviderError("model exploded")


class MissingProvider(EmbeddingProvider):
    name = "missing"
    model = "none"
    dimensions = 0

    def is_available(self) -> bool:
        return False

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingProviderUnavailableError("not installed")


@pytest.fixture()
def fake_provider():
    set_embedding_provider(FakeProvider())
    yield
    set_embedding_provider(None)


@pytest.fixture()
def no_provider():
    set_embedding_provider(MissingProvider())
    yield
    set_embedding_provider(None)


# --- availability states -----------------------------------------------------


def test_real_provider_available_in_this_environment():
    """fastembed + model are installed here; availability probe must say so
    (no download triggered by the probe)."""
    set_embedding_provider(None)  # real provider
    assert embedding_available() is True


def test_unavailable_provider_reports_honestly(no_provider):
    result, error = embed_texts(["hello"], EmbeddingConfig())
    assert result is None
    assert error is not None and error.startswith("unavailable:")


# --- interface contract ---------------------------------------------------------


def test_provider_returns_real_vectors_with_metadata(fake_provider):
    result, error = embed_texts(["alpha", "beta"], EmbeddingConfig())
    assert error is None
    assert result is not None
    assert len(result.vectors) == 2
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.dimensions == 4


def test_deterministic_same_input_same_vector(fake_provider):
    first, _ = embed_texts(["identical input"], EmbeddingConfig())
    second, _ = embed_texts(["identical input"], EmbeddingConfig())
    assert first.vectors[0] == second.vectors[0]


def test_provider_error_surfaces_as_failed(fake_provider):
    set_embedding_provider(ExplodingProvider())
    result, error = embed_texts(["boom"], EmbeddingConfig())
    assert result is None
    assert error is not None and error.startswith("failed:")


def test_input_length_capped(fake_provider):
    long_text = "x" * 10000
    result, error = embed_texts([long_text], EmbeddingConfig(max_input_chars=100))
    assert error is None
    # The fake keys on length % 7 — truncation must be observable.
    assert result.vectors[0][0] == 100 % 7


def test_batch_size_bounds_provider_calls(fake_provider):
    calls: list[list[str]] = []

    class CountingProvider(FakeProvider):
        def embed_batch(self, texts: list[str]) -> EmbeddingResult:
            calls.append(list(texts))
            return super().embed_batch(texts)

    set_embedding_provider(CountingProvider())
    result, error = embed_texts([f"t{i}" for i in range(10)], EmbeddingConfig(max_batch_size=4))
    assert error is None
    assert [len(batch) for batch in calls] == [4, 4, 2]  # bounded batches


def test_empty_input_is_reported_not_embedded(fake_provider):
    result, error = embed_texts([], EmbeddingConfig())
    assert result is None
    assert error == "no texts to embed"


# --- deterministic input construction -----------------------------------------------


def _record_draft(**overrides) -> IndexUnitDraft:
    values = dict(
        unit_type="record",
        document_id=1,
        record_id=10,
        title="DEMO_MINE_A — demo_coal_production",
        content="1200",
        entity="DEMO_MINE_A",
        metric="demo_coal_production",
        reporting_period="2025-06-30",
        unit="tonnes",
        validation_status="pass",
    )
    values.update(overrides)
    return IndexUnitDraft(**values)


def test_record_embedding_input_has_context_not_bare_value():
    text = build_embedding_input(_record_draft())
    assert "record" in text
    assert "DEMO_MINE_A" in text  # entity context
    assert "demo_coal_production" in text  # metric context
    assert "value 1200" in text
    assert "tonnes" in text
    assert "period 2025-06-30" in text
    # A bare "1200" would defeat semantic retrieval — assert context exists:
    assert text.count("|") >= 3


def test_embedding_input_deterministic():
    assert build_embedding_input(_record_draft()) == build_embedding_input(_record_draft())


def test_page_embedding_input_includes_title_and_content():
    draft = IndexUnitDraft(
        unit_type="page",
        document_id=1,
        page_id=5,
        title="report.pdf — page 2",
        content="The mine produced coal.",
    )
    text = build_embedding_input(draft)
    assert text.startswith("page")
    assert "report.pdf — page 2" in text
    assert "The mine produced coal." in text


def test_validation_embedding_input_includes_rule_and_status():
    draft = IndexUnitDraft(
        unit_type="validation",
        document_id=1,
        validation_id=9,
        title="RANGE_OUT_OF_BOUNDS — error",
        content="Value 99999999 outside configured range.",
    )
    text = build_embedding_input(draft)
    assert text.startswith("validation")
    assert "RANGE_OUT_OF_BOUNDS" in text
    assert "error" in text
