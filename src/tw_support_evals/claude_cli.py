"""用本機 Claude Code CLI（`claude -p`）取得結構化輸出，走使用者的訂閱，不需要 API key。"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile


def cli_available() -> bool:
    return shutil.which("claude") is not None


def call_structured(model: str, system: str, user: str, schema: dict, timeout: int = 180) -> dict:
    argv = [
        "claude", "-p", "--model", model, "--output-format", "json", "--max-turns", "1",
        "--tools", "", "--system-prompt", system,
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--", user,
    ]
    last: Exception | None = None
    for _ in range(2):
        # cwd 用中性目錄，避免 CLI 載入專案的 CLAUDE.md。錯誤訊息不含 stdout/stderr 內容。
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
        if proc.returncode != 0:
            raise RuntimeError(f"claude cli exit {proc.returncode}")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = RuntimeError("claude cli: invalid JSON output")
            continue
        if not isinstance(data, dict) or data.get("is_error") or data.get("structured_output") is None:
            last = RuntimeError("claude cli: no structured output")
            continue
        return data["structured_output"]
    raise last or RuntimeError("claude cli: no structured output")
