"""Word-cloud DATA generation (Step 13, Phase 7).

Deterministic, frontend-renderable term weights — no backend image
generation. Weights are normalized TF-IDF scores (0..1) with frequency,
document frequency and bounded source references, so the UI can emphasize
terms without implying unverifiable importance.
"""

from app.intelligence.corpus import CorpusData, display_form
from app.intelligence.keywords import MAX_KEYWORDS, extract_keywords
from app.intelligence.models import WordCloudTerm
from app.intelligence.text import phrase_key

# Bounds.
MAX_CLOUD_TERMS = 40


def generate_word_cloud(corpus: CorpusData) -> list[WordCloudTerm]:
    """Deterministic word-cloud data over terms + phrases.

    Ordering: weight desc, frequency desc, term asc — identical input always
    yields identical output. Weights are normalized to 0..1 by the top score.
    """
    keyword_data = extract_keywords(corpus)
    keywords = keyword_data["keywords"]
    if not keywords:
        return []
    top_score = max(keyword.score for keyword in keywords) or 1.0
    cloud = [
        WordCloudTerm(
            term=keyword.term,
            display_term=keyword.display_term,
            weight=keyword.score / top_score,
            frequency=keyword.frequency,
            document_frequency=keyword.document_frequency,
            kind=keyword.kind,
            sources=keyword.sources,
        )
        for keyword in keywords
    ]
    cloud.sort(key=lambda item: (-item.weight, -item.frequency, item.term))
    return cloud[:MAX_CLOUD_TERMS]


def cloud_terms(corpus: CorpusData) -> dict[str, list[WordCloudTerm]]:
    """Convenience: {term -> cloud entries} keyed for topic attachment."""
    cloud = generate_word_cloud(corpus)
    return {"cloud": cloud}
