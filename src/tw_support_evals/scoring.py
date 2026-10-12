"""純規則評分，不打 API。"""
from __future__ import annotations

from .models import AgentReply, Case


def score_rules(case: Case, reply: AgentReply) -> tuple[bool, bool, list[str]]:
    """回傳 (handoff_ok, rules_ok, reasons)。

    handoff_ok：轉人工與否是否符合預期（唯一的硬指標）。
    rules_ok：must_contain_any / must_not_contain 字串規則。
    reasons：人類可讀的說明；reason 不符只記錄、不算失敗。
    """
    reasons: list[str] = []

    handoff_ok = reply.handoff == case.expected_handoff
    if not handoff_ok:
        reasons.append(f"handoff: expected {case.expected_handoff}, got {reply.handoff} ({reply.reason})")
    elif case.expected_handoff and case.expected_reason and reply.reason != case.expected_reason:
        reasons.append(f"reason: expected {case.expected_reason}, got {reply.reason} (not counted as fail)")

    rules_ok = True
    answer = reply.answer
    if not reply.handoff and case.must_contain_any and not any(k in answer for k in case.must_contain_any):
        rules_ok = False
        reasons.append(f"must_contain_any: none of {case.must_contain_any} in answer")
    hits = [k for k in case.must_not_contain if k in answer]
    if hits:
        rules_ok = False
        reasons.append(f"must_not_contain: found {hits}")

    return handoff_ok, rules_ok, reasons
