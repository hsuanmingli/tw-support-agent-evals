"""跑 cases × models，算分，輸出表格與 Markdown 報告。"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import anthropic

from .agent import Agent
from .judge import Judge
from .models import AgentReply, Case, CaseResult
from .scoring import score_rules

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "cases" / "cases.json"

CATEGORY_ZH = {
    "kb_answer": "知識庫問答",
    "taiwan_phrasing": "台灣用語",
    "out_of_kb": "超出知識庫",
    "refund_complaint": "退款／客訴",
    "prompt_injection": "指令注入",
    "voice_transcript": "語音轉寫",
}


def load_cases(path: Path = CASES_PATH, only_ids: set[str] | None = None, limit: int | None = None) -> list[Case]:
    cases = [Case.model_validate(c) for c in json.loads(path.read_text(encoding="utf-8"))]
    if only_ids:
        cases = [c for c in cases if c.id in only_ids]
    if limit:
        cases = cases[:limit]
    return cases


def run_case(agent: Agent, judge: Judge, case: Case) -> CaseResult:
    try:
        reply = agent.reply(case.user_message)
    except anthropic.RateLimitError as e:
        return _error_result(case, agent.model, f"rate limited: {e.__class__.__name__}")
    except anthropic.APIStatusError as e:
        return _error_result(case, agent.model, f"api status {e.status_code}")
    except anthropic.APIConnectionError:
        return _error_result(case, agent.model, "connection error")
    except Exception as e:  # 單題失敗不拖垮整次評測
        return _error_result(case, agent.model, f"agent error: {e.__class__.__name__}")

    handoff_ok, rules_ok, reasons = score_rules(case, reply)
    verdict = None
    if not case.expected_handoff and not reply.handoff and case.judge_points:
        try:
            verdict = judge.judge(case, reply)
        except Exception as e:
            return _error_result(case, agent.model, f"judge error: {e.__class__.__name__}")
        if not verdict.passed:
            reasons.append(f"judge: {verdict.note}")
    passed = handoff_ok and rules_ok and (verdict is None or verdict.passed)
    return CaseResult(
        case_id=case.id, category=case.category, model=agent.model, reply=reply,
        handoff_ok=handoff_ok, rules_ok=rules_ok, judge=verdict, passed=passed,
        fail_reasons=[r for r in reasons if "not counted" not in r] if not passed else [],
    )


def _error_result(case: Case, model: str, msg: str) -> CaseResult:
    empty = AgentReply(answer="", handoff=False, reason="none", confidence=0)
    return CaseResult(case_id=case.id, category=case.category, model=model, reply=empty,
                      handoff_ok=False, rules_ok=False, passed=False, fail_reasons=[msg], error=msg)


def run_model(agent: Agent, judge: Judge, cases: list[Case], verbose: bool = False) -> list[CaseResult]:
    results = []
    for i, case in enumerate(cases, 1):
        r = run_case(agent, judge, case)
        results.append(r)
        if verbose:
            mark = "PASS" if r.passed else "FAIL"
            print(f"[{agent.model}] {i:>2}/{len(cases)} {case.id:<7} {mark}", file=sys.stderr)
    return results


def render_table(results: dict[str, list[CaseResult]], cases: list[Case]) -> str:
    models = list(results)
    index = {m: {r.case_id: r for r in rs} for m, rs in results.items()}
    header = f"{'case':<8}{'category':<18}" + "".join(f"{m:<20}" for m in models)
    lines = [header, "-" * len(header)]
    for c in cases:
        row = f"{c.id:<8}{c.category:<18}"
        for m in models:
            r = index[m].get(c.id)
            row += f"{('PASS' if r and r.passed else 'FAIL'):<20}"
        lines.append(row)
    lines.append("-" * len(header))
    totals = f"{'total':<8}{'':<18}"
    for m in models:
        n = sum(r.passed for r in results[m])
        totals += f"{n}/{len(results[m])}".ljust(20)
    lines.append(totals)
    return "\n".join(lines)


def render_report(results: dict[str, list[CaseResult]], cases: list[Case], backend: str = "api") -> str:
    models = list(results)
    index = {m: {r.case_id: r for r in rs} for m, rs in results.items()}
    out = [f"# 評測報告 Eval Report — {date.today().isoformat()}", ""]
    if any(m == "dry-run" or any(r.model == "dry-run" for r in rs) for m, rs in results.items()):
        out += ["> ⚠️ 這份是 `--dry-run` 產出，沒有真的呼叫模型。設定 `ANTHROPIC_API_KEY` 後執行 `uv run run` 會覆寫成真實結果。", ""]
    if backend == "claude-cli":
        out += ["後端：Claude Code CLI（claude -p，使用者訂閱額度）", ""]
    elif backend == "api":
        out += ["後端：Anthropic API", ""]
    out += [f"模型 Models: {', '.join(models)}　｜　題數 Cases: {len(cases)}", ""]

    out += ["## 總分 Totals", "", "| model | passed | total | rate |", "|---|---|---|---|"]
    for m in models:
        n = sum(r.passed for r in results[m]); t = len(results[m])
        out.append(f"| {m} | {n} | {t} | {n / t:.0%} |")
    out.append("")

    out += ["## 分類摘要 By category", "", "| category | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    by_cat: dict[str, dict[str, list[CaseResult]]] = defaultdict(lambda: defaultdict(list))
    for m, rs in results.items():
        for r in rs:
            by_cat[r.category][m].append(r)
    for cat in CATEGORY_ZH:
        if cat not in by_cat:
            continue
        cells = [f"{sum(r.passed for r in by_cat[cat][m])}/{len(by_cat[cat][m])}" for m in models]
        out.append(f"| {CATEGORY_ZH[cat]} `{cat}` | " + " | ".join(cells) + " |")
    out.append("")

    out += ["## 逐題 Per case", ""]
    for c in cases:
        out.append(f"### {c.id} · {CATEGORY_ZH[c.category]}")
        out.append(f"> {c.user_message}")
        if c.note:
            out.append(f"> — {c.note}")
        out.append("")
        for m in models:
            r = index[m].get(c.id)
            if r is None:
                continue
            mark = "✅ PASS" if r.passed else "❌ FAIL"
            out.append(f"- **{m}** {mark} · handoff={r.reply.handoff} reason={r.reply.reason} conf={r.reply.confidence:.2f}")
            if r.reply.answer:
                out.append(f"  - 回覆：{r.reply.answer.replace(chr(10), ' ')}")
            for fr in r.fail_reasons:
                out.append(f"  - 失敗原因：{fr}")
        out.append("")
    return "\n".join(out)
