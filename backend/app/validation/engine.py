"""Validation engine: runs all registered rules over value candidates.

Determinism guarantee: same candidates + same config ⇒ same outcomes, in the
same order. No randomness, no model judgments.
"""

from app.validation.config import ValidationConfig
from app.validation.models import RuleOutcome, ValueCandidate
from app.validation.rules import DEFAULT_RULES


def run_validation(
    candidates: list[ValueCandidate],
    config: ValidationConfig,
    rules=None,
) -> list[RuleOutcome]:
    """Execute every rule over the candidates and collect outcomes.

    `rules` is injectable for tests; production uses DEFAULT_RULES.
    """
    outcomes: list[RuleOutcome] = []
    for rule in rules if rules is not None else DEFAULT_RULES:
        outcomes.extend(rule.validate(candidates, config))
    return outcomes
