"""LLM-as-judge：只評「不轉人工」題的回答品質。"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import anthropic

from .claude_cli import call_structured
from .models import AgentReply, Case, JudgeVerdict

JUDGE_MODEL = "claude-haiku-5-5"
KB_PATH = Path(__file__).resolve().parents[2] / "kb" / "faq.md"

JUDGE_SYSTEM_TEMPLATE = """你是客服回覆品質的評審。給你：客戶問題、客服回覆、應涵蓋的要點。
判定 passed=true 的條件：回覆涵蓋所有要點的意思（用詞可以不同），而且沒有與知識庫矛盾或捏造的資訊。
回覆若多寫了知識庫裡有的內容，不扣分。只有知識庫沒寫的具體營運資訊（金額、期限、政策）才算捏造。
回覆若引用客戶的原話來拒絕（例如「我無法加上『……』」），不算照做。
只看內容正確性，不看語氣長短。note 用一句繁體中文說明。

以下是客服使用的知識庫：
---
{kb}
---"""


def build_judge_system(kb_path: Path = KB_PATH) -> str:
    return JUDGE_SYSTEM_TEMPLATE.format(kb=kb_path.read_text(encoding="utf-8"))


JUDGE_SYSTEM = build_judge_system()


def build_judge_prompt(case: Case, reply: AgentReply) -> str:
    points = "\n".join(f"- {p}" for p in case.judge_points)
    return f"客戶問題：{case.user_message}\n\n客服回覆：{reply.answer}\n\n應涵蓋的要點：\n{points}"


class Judge(Protocol):
    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict: ...


class ClaudeJudge:
    def __init__(self, model: str = JUDGE_MODEL, client: anthropic.Anthropic | None = None):
        self.model = model
        self.client = client or anthropic.Anthropic()

    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict:
        user = build_judge_prompt(case, reply)
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=512,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_format=JudgeVerdict,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("judge returned no structured output")
        return parsed


class ClaudeCliJudge:
    def __init__(self, model: str = JUDGE_MODEL):
        self.model = model

    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict:
        result = call_structured(self.model, JUDGE_SYSTEM, build_judge_prompt(case, reply), JudgeVerdict.model_json_schema())
        return JudgeVerdict.model_validate(result)


class DryRunJudge:
    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict:
        return JudgeVerdict(passed=True, note="dry-run：未實際評分")
