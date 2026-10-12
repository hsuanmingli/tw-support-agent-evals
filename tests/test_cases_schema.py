# tests/test_cases_schema.py
import json
from collections import Counter
from pathlib import Path

from tw_support_evals.models import Case

CASES = Path(__file__).resolve().parents[1] / "cases" / "cases.json"


def load():
    return [Case.model_validate(c) for c in json.loads(CASES.read_text())]


def test_forty_cases_unique_ids():
    cases = load()
    assert len(cases) == 40
    assert len({c.id for c in cases}) == 40


def test_category_counts():
    counts = Counter(c.category for c in load())
    assert counts == {
        "kb_answer": 10,
        "taiwan_phrasing": 4,
        "out_of_kb": 6,
        "refund_complaint": 8,
        "prompt_injection": 7,
        "voice_transcript": 5,
    }


def test_handoff_cases_have_reason_and_no_judge():
    for c in load():
        if c.expected_handoff:
            assert c.expected_reason in {"refund", "complaint", "out_of_scope", "low_confidence"}, c.id
            assert c.judge_points == [], c.id
        else:
            assert c.must_contain_any or c.judge_points, f"{c.id} needs a check"
