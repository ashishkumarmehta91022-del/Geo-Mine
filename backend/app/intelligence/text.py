"""Deterministic text processing for document intelligence (Step 13).

Tokenization, stopword filtering and n-gram extraction — pure functions,
no randomness, no NLP framework. Document text is UNTRUSTED input: it is
tokenized defensively (bounded lengths, flattened whitespace) and never
interpreted as instructions anywhere downstream.
"""

import re
from collections import Counter
from typing import Iterable

# Standard English function words (configurable via parameters).
DEFAULT_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "if", "in", "into",
    "is", "it", "its", "of", "on", "or", "our", "per", "she", "so", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "to", "was", "we", "were", "what", "which", "who", "will", "with",
    "would", "you", "your", "also", "each", "any", "all", "not", "no",
    "other", "more", "most", "some", "such", "only", "same", "than", "very",
    "can", "may", "shall", "should", "do", "does", "did", "done", "being",
    "about", "above", "after", "again", "against", "before", "below",
    "between", "both", "down", "during", "few", "further", "here", "how",
    "just", "nor", "now", "off", "once", "out", "over", "own", "under",
    "until", "up", "when", "where", "why",
})

# Token: letters/digits with internal apostrophes/hyphens; lowercased input.
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")

MIN_TOKEN_LEN = 2       # "ignore extremely short/noisy tokens"
MAX_TOKEN_LEN = 40      # bounded (guards against OCR garbage runs)
MAX_PHRASE_TOKENS = 3   # bigrams + trigrams


def tokenize(text: str | None) -> list[str]:
    """Lowercased content tokens, flattened and bounded.

    Deterministic: identical input always yields identical tokens.
    """
    if not text:
        return []
    flattened = " ".join(str(text).split()).lower()
    return [
        token
        for token in TOKEN_PATTERN.findall(flattened)
        if MIN_TOKEN_LEN <= len(token) <= MAX_TOKEN_LEN
    ]


def is_content_token(token: str, stopwords: frozenset[str] = DEFAULT_STOPWORDS) -> bool:
    """A token eligible for keyword/topic analytics.

    Stopwords and pure numbers are excluded — bare numbers out of context
    would fabricate meaningless "keywords" (documented behavior, not a
    domain rule).
    """
    if token in stopwords:
        return False
    if token.isdigit():
        return False
    return True


def content_tokens(tokens: Iterable[str], stopwords: frozenset[str] = DEFAULT_STOPWORDS) -> list[str]:
    return [token for token in tokens if is_content_token(token, stopwords)]


def extract_ngrams(
    tokens: list[str],
    *,
    n_max: int = MAX_PHRASE_TOKENS,
    stopwords: frozenset[str] = DEFAULT_STOPWORDS,
) -> list[tuple[str, ...]]:
    """Deterministic content-only n-grams (2..n_max).

    Every token in a phrase must be a content token (no stopwords, no pure
    numbers, length bounds) — this prevents nonsensical combinations like
    "of the" without any hardcoded domain list.
    """
    phrases: list[tuple[str, ...]] = []
    for n in range(2, n_max + 1):
        for start in range(0, len(tokens) - n + 1):
            window = tokens[start : start + n]
            if all(is_content_token(token, stopwords) for token in window):
                phrases.append(tuple(window))
    return phrases


def phrase_key(phrase: tuple[str, ...] | list[str]) -> str:
    """Normalized join key for a phrase."""
    return " ".join(phrase)


def count_terms(tokens: list[str]) -> Counter:
    return Counter(tokens)
