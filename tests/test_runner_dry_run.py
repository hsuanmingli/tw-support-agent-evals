# tests/test_runner_dry_run.py
from tw_support_evals.agent import DryRunAgent
from tw_support_evals.judge import DryRunJudge
from tw_support_evals.runner import load_cases, run_model, render_table, render_report


def test_dry_run_scores_all_cases():
    cases = load_cases()
    results = run_model(DryRunAgent(), DryRunJudge(), cases)
    assert len(results) == 40
    # dry-run 固定回「不轉人工＋運費 120/60」：kb-01 pass，所有 handoff 題 fail
    by_id = {r.case_id: r for r in results}
    assert by_id["kb-01"].passed is True
    assert by_id["rc-01"].passed is False
    assert "handoff" in by_id["rc-01"].fail_reasons[0]


def test_table_and_report_mention_every_case():
    cases = load_cases()
    results = {"dry-run": run_model(DryRunAgent(), DryRunJudge(), cases)}
    table = render_table(results, cases)
    report = render_report(results, cases)
    for c in cases:
        assert c.id in table
        assert c.id in report
    assert "PASS" in table and "FAIL" in table
    assert "## 分類摘要" in report
