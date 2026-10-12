"""`uv run run` 入口。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import DryRunAgent, SupportAgent
from .judge import ClaudeJudge, DryRunJudge
from .runner import ROOT, load_cases, render_report, render_table, run_model

DEFAULT_MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run", description="跑 40 題客服 agent eval，印出 pass/fail 表，寫 Markdown 報告。")
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="要測的 agent 模型 (預設：Sonnet 5.5 與 Haiku 5.5)")
    p.add_argument("--judge-model", default="claude-haiku-5-5")
    p.add_argument("--dry-run", action="store_true", help="不打 API，用固定回覆驗證流程")
    p.add_argument("--limit", type=int, help="只跑前 N 題")
    p.add_argument("--case", nargs="+", dest="case_ids", help="只跑指定 case id")
    p.add_argument("--out", type=Path, default=ROOT / "reports" / "sample-report.md", help="報告輸出路徑")
    args = p.parse_args(argv)

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("找不到 ANTHROPIC_API_KEY。請 `export ANTHROPIC_API_KEY=...`，或先用 --dry-run 驗證流程。", file=sys.stderr)
        return 2

    cases = load_cases(only_ids=set(args.case_ids) if args.case_ids else None, limit=args.limit)
    results = {}
    if args.dry_run:
        results["dry-run"] = run_model(DryRunAgent(), DryRunJudge(), cases, verbose=True)
    else:
        judge = ClaudeJudge(model=args.judge_model)
        for m in args.models:
            results[m] = run_model(SupportAgent(model=m), judge, cases, verbose=True)

    print(render_table(results, cases))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(results, cases), encoding="utf-8")
    print(f"\n報告已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
