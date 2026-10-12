"""共用資料結構。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HandoffReason = Literal["none", "refund", "complaint", "out_of_scope", "low_confidence"]

Category = Literal[
    "kb_answer",          # 知識庫內有答案，應直接回答
    "out_of_kb",          # 知識庫沒有，應轉人工 (out_of_scope)
    "refund_complaint",   # 退款／客訴，應轉人工
    "prompt_injection",   # 指令注入，應守住規則
    "taiwan_phrasing",    # 台灣口語／在地用語，知識庫內有答案
    "voice_transcript",   # 語音轉寫文字 (錯字、同音字、無標點)
]


class AgentReply(BaseModel):
    """Agent 的固定輸出格式 (structured output)。"""

    answer: str = Field(description="給客戶看的繁體中文回覆。轉人工時仍要給一句說明。")
    handoff: bool = Field(description="是否轉真人客服")
    reason: HandoffReason = Field(description="轉人工原因；不轉人工填 none")
    confidence: float = Field(ge=0, le=1, description="對 answer 正確性的信心 0–1")


class Case(BaseModel):
    id: str
    category: Category
    user_message: str
    expected_handoff: bool
    expected_reason: HandoffReason | None = None   # None = 不檢查原因
    must_contain_any: list[str] = []               # 不轉人工時，answer 至少含其中一個
    must_not_contain: list[str] = []               # answer 絕不能含
    judge_points: list[str] = []                   # 非空時啟動 LLM judge，用這些要點評分
    note: str = ""                                 # 給讀者看的說明


class JudgeVerdict(BaseModel):
    passed: bool = Field(description="回覆是否涵蓋要點且沒有與知識庫矛盾")
    note: str = Field(description="一句繁中說明")


class CaseResult(BaseModel):
    case_id: str
    category: str
    model: str
    reply: AgentReply
    handoff_ok: bool
    rules_ok: bool
    judge: JudgeVerdict | None = None
    passed: bool
    fail_reasons: list[str] = []
    error: str | None = None
