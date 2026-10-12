import json
import subprocess

import pytest

from tw_support_evals import claude_cli
from tw_support_evals.agent import ClaudeCliAgent
from tw_support_evals.cli import main

GOOD = json.dumps({"is_error": False, "subtype": "success", "structured_output": {"answer": "x", "handoff": False, "reason": "none", "confidence": 0.9}})


def _cp(stdout, code=0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr="")


def _patch(monkeypatch, outputs):
    calls = []

    def fake(argv, **kw):
        calls.append(argv)
        return outputs[len(calls) - 1]

    monkeypatch.setattr(claude_cli.subprocess, "run", fake)
    return calls


def test_success(monkeypatch):
    calls = _patch(monkeypatch, [_cp(GOOD)])
    r = ClaudeCliAgent().reply("hi")
    assert r.answer == "x"
    assert "--json-schema" in calls[0] and "--max-turns" in calls[0] and "hi" in calls[0]


def test_retry_on_bad_json(monkeypatch):
    calls = _patch(monkeypatch, [_cp("not json"), _cp(GOOD)])
    assert ClaudeCliAgent().reply("hi").answer == "x"
    assert len(calls) == 2


def test_failure_after_two_attempts(monkeypatch):
    bad = _cp(json.dumps({"is_error": True}))
    calls = _patch(monkeypatch, [bad, bad])
    with pytest.raises(RuntimeError):
        ClaudeCliAgent().reply("hi")
    assert len(calls) == 2


def test_nonzero_exit_no_retry(monkeypatch):
    calls = _patch(monkeypatch, [_cp("", 1), _cp(GOOD)])
    with pytest.raises(RuntimeError):
        ClaudeCliAgent().reply("hi")
    assert len(calls) == 1


def test_main_without_cli_returns_2(monkeypatch):
    monkeypatch.setattr("tw_support_evals.cli.cli_available", lambda: False)
    assert main(["--backend", "claude-cli", "--limit", "1"]) == 2
