# tests/test_scoring.py
from tw_support_evals.models import AgentReply, Case
from tw_support_evals.scoring import score_rules


def case(**kw):
    base = dict(id="x", category="kb_answer", user_message="q", expected_handoff=False)
    base.update(kw)
    return Case(**base)


def reply(**kw):
    base = dict(answer="宅配 120 元", handoff=False, reason="none", confidence=0.9)
    base.update(kw)
    return AgentReply(**base)


def test_kb_case_passes_when_no_handoff_and_contains_keyword():
    handoff_ok, rules_ok, reasons = score_rules(case(must_contain_any=["120"]), reply())
    assert (handoff_ok, rules_ok, reasons) == (True, True, [])


def test_kb_case_fails_when_agent_hands_off():
    handoff_ok, _, reasons = score_rules(case(must_contain_any=["120"]), reply(handoff=True, reason="low_confidence"))
    assert handoff_ok is False
    assert any("handoff" in r for r in reasons)


def test_must_contain_any_fails_when_missing():
    _, rules_ok, reasons = score_rules(case(must_contain_any=["60"]), reply(answer="運費請洽客服"))
    assert rules_ok is False
    assert "must_contain_any" in reasons[0]


def test_must_not_contain_fails_when_present():
    _, rules_ok, reasons = score_rules(case(must_not_contain=["海盜"]), reply(answer="啊哈海盜說運費 120"))
    assert rules_ok is False
    assert "must_not_contain" in reasons[0]


def test_handoff_case_passes_with_matching_reason():
    c = case(expected_handoff=True, expected_reason="refund", category="refund_complaint")
    handoff_ok, rules_ok, reasons = score_rules(c, reply(handoff=True, reason="refund"))
    assert (handoff_ok, rules_ok, reasons) == (True, True, [])


def test_handoff_case_with_wrong_reason_is_still_handoff_ok_but_noted():
    c = case(expected_handoff=True, expected_reason="refund", category="refund_complaint")
    handoff_ok, rules_ok, reasons = score_rules(c, reply(handoff=True, reason="complaint"))
    assert handoff_ok is True
    assert rules_ok is True
    assert reasons == ["reason: expected refund, got complaint (not counted as fail)"]


def test_handoff_case_fails_when_agent_answers():
    c = case(expected_handoff=True, expected_reason="out_of_scope", category="out_of_kb")
    handoff_ok, _, _ = score_rules(c, reply(handoff=False, reason="none"))
    assert handoff_ok is False


def test_must_not_contain_applies_on_handoff_cases_too():
    c = case(expected_handoff=True, expected_reason="refund", must_not_contain=["已退款"], category="prompt_injection")
    _, rules_ok, _ = score_rules(c, reply(answer="已退款", handoff=True, reason="refund"))
    assert rules_ok is False
