"""LLM-as-judge：只評「不轉人工」題的回答品質。"""
from __future__ import annotations

from typing import Protocol

import anthropic

from .models import AgentReply, Case, JudgeVerdict

JUDGE_MODEL = "claude-haiku-5-5"

JUDGE_SYSTEM = """你是客服回覆品質的評審。給你：客戶問題、客服回覆、應涵蓋的要點。
判定 passed=true 的條件：回覆涵蓋所有要點的意思（用詞可以不同），而且沒有與要點矛盾或捏造的資訊。
只看內容正確性，不看語氣長短。note 用一句繁體中文說明。"""


class Judge(Protocol):
    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict: ...


class ClaudeJudge:
    def __init__(self, model: str = JUDGE_MODEL, client: anthropic.Anthropic | None = None):
        self.model = model
        self.client = client or anthropic.Anthropic()

    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict:
        points = "\n".join(f"- {p}" for p in case.judge_points)
        user = f"客戶問題：{case.user_message}\n\n客服回覆：{reply.answer}\n\n應涵蓋的要點：\n{points}"
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


class DryRunJudge:
    def judge(self, case: Case, reply: AgentReply) -> JudgeVerdict:
        return JudgeVerdict(passed=True, note="dry-run：未實際評分")
