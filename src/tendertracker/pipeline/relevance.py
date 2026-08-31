from dataclasses import dataclass, field


@dataclass
class RelevanceRules:
    must_match: list[str] = field(default_factory=list)
    boost: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


def evaluate(rules: RelevanceRules, text: str) -> tuple[bool, int]:
    """Returns (passes, score) for the given text against the rules.

    No must_match terms configured means no filtering is applied — everything
    passes with score 0. This keeps a portals.yaml without a `relevance`
    block working unchanged (relevance filtering is opt-in per source).
    """
    lowered = text.lower()

    if any(term.lower() in lowered for term in rules.exclude):
        return False, 0

    if rules.must_match and not any(term.lower() in lowered for term in rules.must_match):
        return False, 0

    score = sum(10 for term in rules.must_match if term.lower() in lowered)
    score += sum(5 for term in rules.boost if term.lower() in lowered)
    return True, min(score, 100)
