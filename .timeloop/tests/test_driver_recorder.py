# .timeloop/tests/test_driver_recorder.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.dispatcher import Brief  # noqa: E402
from driver.recorder import (  # noqa: E402
    CommitFailure,
    ExamFailure,
    Hooks,
    delta,
    is_allowed,
    record,
    snapshot,
    validate,
)
from driver.runner import RunResult  # noqa: E402
from driver.state import read_jsonl  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".timeloop" / "driver" / "results").mkdir(parents=True)
    (repo / ".timeloop" / "notebook").mkdir()
    (repo / ".timeloop" / "driver" / "briefs").mkdir()
    (repo / "publication").mkdir()
    (repo / ".timeloop" / "ledger.md").write_text("# L\n\nT1 | a | nothing | x\n")
    (repo / ".timeloop" / "pool.jsonl").write_text(
        json.dumps({"slug": "a", "status": "open", "tags": ["x"]}) + "\n"
    )
    (repo / ".timeloop" / "frames.jsonl").write_text("")
    (repo / ".timeloop" / "driver" / "templates").mkdir()
    (repo / ".timeloop" / "driver" / "templates" / "brief.md").write_text("t")
    (repo / ".timeloop" / "driver" / "templates" / "system.md").write_text("s")
    (repo / "publication" / "keep.txt").write_text("released\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    # pre-existing dirty work that must survive untouched
    (repo / "publication" / "keep.txt").write_text("human edit in progress\n")
    (repo / "scratch.txt").write_text("untracked human file\n")
    return repo


def stub_hooks(lint: list[str] | None = None, exam_ok: bool = True) -> Hooks:
    calls: list[str] = []
    return Hooks(
        lint=lambda: (calls.append("lint"), lint or [])[1],
        exam=lambda: (calls.append("exam"), exam_ok)[1],
        reap=lambda: calls.append("reap"),
        index=lambda: calls.append("index"),
    )


def result(
    outcome: str,
    ledger_line: str | None,
    files: list[str],
    frames: list[dict[str, object]] | None = None,
    refinement: bool = False,
) -> RunResult:
    payload = {
        "outcome": outcome, "refinement": refinement, "ledger_line": ledger_line,
        "files_changed": files, "frames_filed": frames or [], "next_action": None, "notes": "",
    }
    return RunResult("completed", 0, 12.5, json.dumps(payload), "", payload, None)


def brief(kind: str = "attack") -> Brief:
    return Brief("T2", kind, "a", ("f1",), None, None, False, "")


def test_snapshot_and_delta_use_content_hashes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    assert set(before) == {"publication/keep.txt", "scratch.txt"}
    (repo / ".timeloop" / "runs").mkdir()
    (repo / ".timeloop" / "runs" / "t2_probe.py").write_text("print(1)\n")
    # dirty file changed again
    (repo / "publication" / "keep.txt").write_text("human edit, second pass\n")
    (repo / "scratch.txt").unlink()
    after = snapshot(repo)
    assert delta(before, after) == {
        ".timeloop/runs/t2_probe.py", "publication/keep.txt", "scratch.txt",
    }
    assert delta(after, after) == set()


def test_is_allowed() -> None:
    assert (
        is_allowed(".timeloop/ledger.md")
        and is_allowed(".timeloop/notebook/a.md")
        and is_allowed(".timeloop/lean/arena/X.lean")
    )
    assert (
        not is_allowed(".timeloop/frames.jsonl")
        and not is_allowed("publication/x")
        and not is_allowed("src/y.py")
    )


def test_validate_downgrades() -> None:
    d = {".timeloop/ledger.md"}
    ok = validate(
        brief(), result("negative", "T2 | a | negative | r", [".timeloop/ledger.md"]),
        d, "x\n", "x\nT2 | a | negative | r\n",
    )
    assert ok == ("negative", None, False)
    no_line = validate(brief(), result("negative", None, [".timeloop/ledger.md"]), d, "x\n", "x\n")
    assert no_line[:2] == ("invalid", "no_ledger_line")
    mismatch = validate(brief(), result("nothing", None, []), d, "x\n", "x\n")
    assert mismatch[:2] == ("invalid", "files_mismatch")
    wrong_prefix = validate(
        brief(), result("negative", "T9 | a | negative | r", [".timeloop/ledger.md"]),
        d, "x\n", "x\nT9 | a | negative | r\n",
    )
    assert wrong_prefix[:2] == ("invalid", "no_ledger_line")
    frames_on_attack = validate(brief(), result("frames", None, []), set(), "x\n", "x\n")
    assert frames_on_attack[:2] == ("invalid", "frames_outside_forage")
    timeout = validate(
        brief(), RunResult("timeout", None, 1800.0, "", "", None, None), set(), "x\n", "x\n"
    )
    assert timeout[:2] == ("invalid", "timeout")


def test_record_commits_delta_and_preserves_dirty_files(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    pre = snapshot(repo)
    # the dispatcher's writes, before the model runs
    pool = repo / ".timeloop" / "pool.jsonl"
    pool.write_text(
        pool.read_text().replace('"status": "open"', '"status": "parked", "cooldown_until": 22')
    )
    (repo / ".timeloop" / "driver" / "briefs" / "T2.md").write_text("brief")
    before = snapshot(repo)
    ledger_before = (repo / ".timeloop" / "ledger.md").read_text()
    # the turn's writes
    (repo / ".timeloop" / "ledger.md").write_text(
        ledger_before + "\nT2 | a | negative | ruled out n<10\n"
    )
    (repo / ".timeloop" / "notebook" / "a.md").write_text("## STATUS\nopen\n")
    (repo / "src.py").write_text("forbidden\n")
    (repo / "publication" / "new.pdf").write_text("forbidden\n")
    rec = record(
        repo, brief(), "brief",
        result(
            "negative", "T2 | a | negative | ruled out n<10",
            [".timeloop/ledger.md", ".timeloop/notebook/a.md"],
        ),
        pre, before, ledger_before, "2026-09-02T00:00:00Z", stub_hooks(),
    )
    assert rec.outcome == "negative" and rec.invalid_reason is None
    assert not (repo / "src.py").exists() and not (repo / "publication" / "new.pdf").exists()
    assert (repo / "publication" / "keep.txt").read_text() == "human edit in progress\n"
    assert (repo / "scratch.txt").exists()
    log = git(repo, "log", "--format=%s", "-1").strip()
    assert log == "turn: T2 attack a negative"
    assert git(repo, "status", "--porcelain", "--", "publication/keep.txt").startswith(" M")
    turns = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert (
        turns[-1]["turn_id"] == "T2"
        and turns[-1]["base_commit"] == git(repo, "rev-parse", "HEAD~1").strip()
    )
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert ".timeloop/driver/turns.jsonl" in committed
    assert ".timeloop/driver/briefs/T2.md" in committed
    assert ".timeloop/driver/results/T2.json" in committed
    assert ".timeloop/pool.jsonl" in committed  # the dispatcher's parking write rides along
    # but is not blamed on the model
    assert rec.files_changed == (".timeloop/ledger.md", ".timeloop/notebook/a.md")


def test_record_files_frames_and_rejects_bad_ones(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    ledger_before = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "ledger.md").write_text(ledger_before + "\nT2 | a | frames | filed 2\n")
    good = {
        "slug": "new-frame", "title": "N", "statement": "p", "shape": ["x"],
        "source": {"kind": "arxiv", "id": "1", "url": "https://arxiv.org/abs/1"},
    }
    bad = {
        "slug": "no-url", "title": "N", "statement": "p", "shape": ["x"],
        "source": {"kind": "web"},
    }
    rec = record(
        repo, brief("forage-target"), "brief",
        result("frames", "T2 | a | frames | filed 2", [".timeloop/ledger.md"], [good, bad]),
        before, before, ledger_before, "2026-09-02T00:00:00Z", stub_hooks(),
    )
    frames = read_jsonl(repo / ".timeloop" / "frames.jsonl")
    assert [f["slug"] for f in frames] == ["new-frame"] and frames[0]["filed_by"] == "T2"
    assert (
        rec.frames_filed == ("new-frame",)
        and rec.outcome == "frames"
        and rec.invalid_reason is None
    )
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log[-2]["event"] == "frames_rejected" and "no-url" in log[-2]["reasons"][0]
    assert ".timeloop/frames.jsonl" in git(repo, "show", "--name-only", "--format=", "HEAD").split()


def test_record_adversarial_keeps_claim_and_forbids_verified_elsewhere(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "ledger.md").write_text(
        lb + "\nT2 | a | verified | T1 re-derived independently for n<10^6\n"
    )
    adv = Brief("T2", "adversarial", None, (), None, "T1 | a | nothing | x", False, "")
    rec = record(
        repo, adv, "brief",
        result(
            "verified", "T2 | a | verified | T1 re-derived independently for n<10^6",
            [".timeloop/ledger.md"],
        ),
        before, before, lb, "t", stub_hooks(),
    )
    assert rec.outcome == "verified" and rec.claim == "T1 | a | nothing | x"
    assert validate(
        brief(), result("verified", "T2 | a | verified | r", [".timeloop/ledger.md"]),
        {".timeloop/ledger.md"}, "x\n", "x\nT2 | a | verified | r\n",
    )[:2] == ("invalid", "verified_outside_adversarial")


def test_record_lint_failure_and_exam_failure(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    rec = record(
        repo, brief(), "brief", result("nothing", None, []),
        before, before, lb, "t", stub_hooks(lint=["bad schema"]),
    )
    assert rec.outcome == "invalid" and rec.invalid_reason == "lint: bad schema"
    now = snapshot(repo)
    with pytest.raises(ExamFailure):
        record(
            repo, brief(), "brief", result("nothing", None, []),
            now, now, lb, "t", stub_hooks(exam_ok=False),
        )
    assert git(repo, "log", "--format=%s", "-1").strip().startswith("turn: T2")


def test_model_edit_to_driver_code_is_reverted_not_committed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / ".timeloop" / "driver" / "dispatcher.py").write_text("original\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "driver code")
    pre = snapshot(repo)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "driver" / "dispatcher.py").write_text("model tampered\n")
    rec = record(
        repo, brief(), "brief", result("nothing", None, []),
        pre, before, lb, "t", stub_hooks(),
    )
    assert (repo / ".timeloop" / "driver" / "dispatcher.py").read_text() == "original\n"
    assert (
        ".timeloop/driver/dispatcher.py"
        not in git(repo, "show", "--name-only", "--format=", "HEAD").split()
    )
    assert rec.outcome == "nothing"


def test_commit_failure_raises(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    pre = snapshot(repo)
    before = snapshot(repo)
    lb = (repo / ".timeloop" / "ledger.md").read_text()
    (repo / ".timeloop" / "notebook" / "a.md").write_text("## STATUS\nopen\n")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(CommitFailure):
        record(
            repo, brief(), "brief",
            result("nothing", None, [".timeloop/notebook/a.md"]),
            pre, before, lb, "t", stub_hooks(),
        )
