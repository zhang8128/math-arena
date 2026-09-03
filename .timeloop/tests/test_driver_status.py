from __future__ import annotations

import json
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.status import format_status, yield_report  # noqa: E402


def rec(i: int, kind: str, outcome: str) -> dict[str, object]:
    return {"turn_id": f"T{i}", "kind": kind, "target": "a", "frames": [], "outcome": outcome,
            "refinement": False, "ledger_line": None, "files_changed": [], "frames_filed": [],
            "started": "", "seconds": 1.0, "base_commit": "", "exit_reason": "completed",
            "invalid_reason": None, "brief_digest": "", "template_digest": ""}


def test_yield_report_windows_and_kinds() -> None:
    turns = [rec(i, "attack", "negative" if i % 3 == 0 else "nothing") for i in range(60)]
    turns.insert(5, {"event": "halt", "reason": "x"})
    turns.append(rec(60, "patrol", "nothing"))
    r = yield_report(turns)
    assert r["all"]["turns"] == 61 and r["all"]["productive"] == 20
    assert r["last_10"]["turns"] == 10 and r["last_50"]["turns"] == 50
    assert r["by_kind"]["patrol"] == {"turns": 1, "productive": 0, "share": 0.0}
    assert yield_report([])["all"]["share"] is None


def test_yield_report_excludes_frames_rejected_event() -> None:
    """C1 regression: a frames_rejected event carries `turn` (not `turn_id`) and
    `event`; it must never be counted as a turn in the yield report."""
    turns = [rec(1, "attack", "negative")]
    turns.append({"event": "frames_rejected", "turn": "T2", "reasons": ["bad"]})
    r = yield_report(turns)
    assert r["all"]["turns"] == 1 and r["all"]["productive"] == 1


def test_format_status_reports_lease_and_yield(tmp_path: Path) -> None:
    root = tmp_path / ".timeloop"
    (root / "driver").mkdir(parents=True)
    (root / "driver" / "turns.jsonl").write_text(
        json.dumps(rec(1, "attack", "negative")) + "\n"
    )
    assert "no lease" in format_status(root)
    lease_data = {
        "pid": 1,
        "started": "2026-09-02T00:00:00Z",
        "seed": 1,
        "heartbeat": "2026-09-02T00:10:00Z",
        "turn_id": "T2",
        "kind": "attack",
        "target": "a",
        "frames": ["f"],
    }
    (root / "driver" / "lease.json").write_text(json.dumps(lease_data))
    text = format_status(root)
    assert "pid 1" in text and "T2 attack a" in text and "last 10: 1/1" in text
