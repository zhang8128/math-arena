# .timeloop/tests/test_driver_loop.py
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.config import DriverConfig  # noqa: E402
from driver.loop import LeaseHeld, acquire, release, run_loop  # noqa: E402
from driver.recorder import Hooks  # noqa: E402
from driver.state import read_jsonl  # noqa: E402

FAKE = str(TIMELOOP / "tests" / "fixtures" / "fake_claude")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    tl = repo / ".timeloop"
    for d in ("driver/templates", "driver/results", "notebook", "bin"):
        (tl / d).mkdir(parents=True)
    src = TIMELOOP
    (tl / "driver" / "templates" / "brief.md").write_text(
        (src / "driver" / "templates" / "brief.md").read_text()
    )
    (tl / "driver" / "templates" / "system.md").write_text(
        (src / "driver" / "templates" / "system.md").read_text()
    )
    (tl / "README.md").write_text((src / "README.md").read_text())
    (tl / "pool.jsonl").write_text(
        json.dumps(
            {
                "slug": "a", "track": "open", "tags": ["x"], "priority": 1,
                "title": "A", "statement": "s", "status": "open",
            }
        ) + "\n"
        + json.dumps(
            {
                "slug": "b", "track": "open", "tags": ["x"], "priority": 2,
                "title": "B", "statement": "s", "status": "open",
            }
        ) + "\n"
    )
    (tl / "frames.jsonl").write_text(
        json.dumps(
            {
                "slug": "f1", "title": "F1", "statement": "p", "shape": ["x"],
                "source": {"kind": "pool"}, "filed_by": "seed",
                "applied_to": [], "superseded_by": None,
            }
        ) + "\n"
        + json.dumps(
            {
                "slug": "f2", "title": "F2", "statement": "p", "shape": ["x"],
                "source": {"kind": "pool"}, "filed_by": "seed",
                "applied_to": [], "superseded_by": None,
            }
        ) + "\n"
        + json.dumps(
            {
                "slug": "f3", "title": "F3", "statement": "p", "shape": ["*"],
                "source": {"kind": "pool"}, "filed_by": "seed",
                "applied_to": [], "superseded_by": None,
            }
        ) + "\n"
    )
    (tl / "ledger.md").write_text("# L\n\nT0 | a | nothing | start\n")
    (tl / "index.md").write_text(
        "- a | open | ruled out: (none recorded) | next: (none recorded)\n"
        "- b | open | ruled out: (none recorded) | next: (none recorded)\n"
    )
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def hooks() -> Hooks:
    return Hooks(lint=lambda: [], exam=lambda: True, reap=lambda: None, index=lambda: None)


def cfg(**kw: object) -> DriverConfig:
    base = {
        "claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0,
        "forage_frontier_share": 0.0, "turn_timeout_seconds": 5,
    }
    base.update(kw)
    return DriverConfig(**base)  # type: ignore[arg-type]


def test_max_turns_runs_exactly_n_and_commits_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    code = run_loop(repo, cfg(), max_turns=3, max_hours=None, hooks=hooks())
    assert code == 0
    turns = [
        t for t in read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl") if "turn_id" in t
    ]
    assert [t["turn_id"] for t in turns] == ["T1", "T2", "T3"]
    assert all(t["outcome"] == "nothing" for t in turns)
    subjects = git(repo, "log", "--format=%s").splitlines()
    expected = [f"turn: T{i} attack {turns[i-1]['target']} nothing" for i in (3, 2, 1)]
    assert [s for s in subjects if s.startswith("turn: T")] == expected
    for t in turns:   # every record's base_commit is the parent of the commit carrying its id
        child = git(repo, "log", "--format=%H %s", f"{t['base_commit']}..HEAD").splitlines()[-1]
        assert child.endswith(f"turn: {t['turn_id']} attack {t['target']} nothing")
    assert not (repo / ".timeloop" / "driver" / "lease.json").exists()


def test_max_hours_zero_halts_before_any_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    assert run_loop(repo, cfg(), max_turns=None, max_hours=0.0, hooks=hooks()) == 0
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log == [{**log[0], "event": "halt", "reason": "max_hours"}]


def test_breaker_halts_at_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "nonzero")
    code = run_loop(repo, cfg(breaker_threshold=3), max_turns=10, max_hours=None, hooks=hooks())
    assert code == 5
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert sum(1 for t in log if "turn_id" in t) == 3
    assert log[-1]["event"] == "halt" and log[-1]["reason"] == "breaker"


def test_usage_limit_halts_immediately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "usage")
    code = run_loop(repo, cfg(), max_turns=10, max_hours=None, hooks=hooks())
    assert code != 0
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert sum(1 for t in log if "turn_id" in t) == 1 and log[-1]["reason"] == "usage_limit"


def test_lease_contention_and_stale_expiry(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    root = repo / ".timeloop"
    acquire(root, seed=1, stale_seconds=2700)
    with pytest.raises(LeaseHeld):
        acquire(root, seed=1, stale_seconds=2700)
    release(root)
    stale_lease = {
        "pid": 999999, "started": "2026-01-01T00:00:00Z", "seed": 1,
        "heartbeat": "2026-01-01T00:00:00Z", "turn_id": None,
    }
    (root / "driver" / "lease.json").write_text(json.dumps(stale_lease))
    acquire(root, seed=1, stale_seconds=2700)
    log = read_jsonl(root / "driver" / "turns.jsonl")
    assert log[-1]["event"] == "lease_expired"
    release(root)


def test_two_signals_kill_the_turn_and_release(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    env = {**os.environ, "FAKE_CLAUDE_MODE": "sleep", "PYTHONPATH": str(TIMELOOP)}
    cfg_path = repo / ".timeloop" / "driver" / "config.json"
    cfg_path.write_text(json.dumps({
        "claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0,
        "forage_frontier_share": 0.0, "turn_timeout_seconds": 60,
    }))
    proc = subprocess.Popen(
        [sys.executable, "-m", "driver.loop", "run", "--max-turns", "2", "--no-hooks"],
        cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    time.sleep(3)
    proc.send_signal(signal.SIGTERM)   # first: let the turn finish
    time.sleep(2)
    assert proc.poll() is None          # still running: the fake sleeps 30 s
    proc.send_signal(signal.SIGTERM)   # second: kill the child
    _out, err = proc.communicate(timeout=30)
    assert proc.returncode == 130, err
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert [t for t in log if "turn_id" in t][-1]["exit_reason"] == "interrupted"
    assert log[-1]["event"] == "interrupted" and log[-1]["hard"] is True
    assert not (repo / ".timeloop" / "driver" / "lease.json").exists()


def test_one_signal_stops_at_the_boundary(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    env = {**os.environ, "FAKE_CLAUDE_MODE": "ok", "PYTHONPATH": str(TIMELOOP)}
    (repo / ".timeloop" / "driver" / "config.json").write_text(json.dumps({
        "claude_executable": FAKE, "combine_share": 0.0, "forage_target_share": 0.0,
        "forage_frontier_share": 0.0,
    }))
    proc = subprocess.Popen(
        [sys.executable, "-m", "driver.loop", "run", "--max-turns", "50", "--no-hooks"],
        cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    time.sleep(2)
    proc.send_signal(signal.SIGINT)
    _out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    log = read_jsonl(repo / ".timeloop" / "driver" / "turns.jsonl")
    assert log[-1]["event"] == "interrupted" and "hard" not in log[-1]
    assert all(t["exit_reason"] == "completed" for t in log if "turn_id" in t)
    assert 1 <= sum(1 for t in log if "turn_id" in t) < 50


def test_bin_research_allow_list_matches_the_protected_write_set() -> None:
    """The refusal filter must allow exactly what recorder.py protects from revert.

    The write set lives in three places: ALLOWED_WRITES, is_driver_owned, and
    this bash regex. This test is the only thing tying the third to the first two.
    """
    from driver.brief import ALLOWED_WRITES
    from driver.recorder import DRIVER_OWNED_FILES, DRIVER_OWNED_PREFIXES

    script = (TIMELOOP.parent / "bin" / "research").read_text()
    pattern = next(ln for ln in script.splitlines() if "grep -Ev" in ln)
    for path in (*ALLOWED_WRITES, *DRIVER_OWNED_PREFIXES, *DRIVER_OWNED_FILES,
                 ".timeloop/driver/lease.json"):
        assert path.replace(".", r"\.") in pattern, path
    assert r"\.timeloop/driver/|" not in pattern and not pattern.endswith(r"\.timeloop/driver/)")
    assert r"\.superpowers/" not in pattern
    assert "--no-renames" in script
