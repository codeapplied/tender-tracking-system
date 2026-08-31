from tendertracker.pipeline.relevance import RelevanceRules, evaluate


def test_no_rules_means_everything_passes():
    rules = RelevanceRules()
    passes, score = evaluate(rules, "anything at all")
    assert passes is True
    assert score == 0


def test_must_match_gates_non_matching_records():
    rules = RelevanceRules(must_match=["EV", "charging"])
    passes, _ = evaluate(rules, "road resurfacing project")
    assert passes is False


def test_must_match_passes_when_any_term_matches():
    rules = RelevanceRules(must_match=["EV", "charging"])
    passes, score = evaluate(rules, "EV charging infrastructure project")
    assert passes is True
    assert score == 20  # both must_match terms hit, 10 each


def test_exclude_rejects_regardless_of_must_match():
    rules = RelevanceRules(must_match=["charger"], exclude=["phone charger"])
    passes, _ = evaluate(rules, "bulk order of phone charger accessories")
    assert passes is False


def test_boost_raises_score_without_gating():
    rules = RelevanceRules(must_match=["charging"], boost=["fleet"])
    passes, score = evaluate(rules, "EV charging for the municipal fleet")
    assert passes is True
    assert score == 15  # 10 for must_match + 5 for boost


def test_matching_is_case_insensitive():
    rules = RelevanceRules(must_match=["EV"])
    passes, _ = evaluate(rules, "ev charging station")
    assert passes is True


def test_score_is_capped_at_100():
    rules = RelevanceRules(must_match=[f"term{i}" for i in range(20)])
    text = " ".join(f"term{i}" for i in range(20))
    _, score = evaluate(rules, text)
    assert score == 100
