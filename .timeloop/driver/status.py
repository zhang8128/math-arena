"""Yield numbers from the turn log. The same numbers gate the soak."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from driver.state import PRODUCTIVE, read_jsonl


def _triple(turns: list[dict[str, object]]) -> dict[str, object]:
    n = len(turns)
    p = sum(1 for t in turns if str(t.get("outcome")) in PRODUCTIVE)
    return {"turns": n, "productive": p, "share": (round(p / n, 3) if n else None)}


def yield_report(turns: list[dict[str, object]]) -> dict[str, object]:
    real = [t for t in turns if "turn_id" in t]
    kinds = Counter(str(t.get("kind")) for t in real)
    return {
        "last_10": _triple(real[-10:]),
        "last_50": _triple(real[-50:]),
        "all": _triple(real),
        "by_kind": {k: _triple([t for t in real if t.get("kind") == k]) for k in sorted(kinds)},
    }


def format_status(root: Path) -> str:
    lines: list[str] = []
    lease = root / "driver" / "lease.json"
    if lease.exists():
        L = json.loads(lease.read_text(encoding="utf-8"))
        hb = datetime.fromisoformat(str(L["heartbeat"]).replace("Z", "+00:00"))
        age = int((datetime.now(UTC) - hb).total_seconds())
        lines.append(
            f"lease: pid {L['pid']} since {L['started']} (heartbeat {age}s ago)"
        )
        frames_str = " ".join(L.get("frames", []))
        current_line = (
            f"current: {L.get('turn_id')} {L.get('kind')} {L.get('target')} "
            f"{frames_str}"
        ).rstrip()
        lines.append(current_line)
    else:
        lines.append("lease: no lease (not running)")
    r = yield_report(read_jsonl(root / "driver" / "turns.jsonl"))
    for key in ("last_10", "last_50", "all"):
        t = r[key]
        assert isinstance(t, dict)
        label = key.replace("_", " ")
        share_str = f" ({t['share']})" if t["share"] is not None else ""
        lines.append(f"yield {label}: {t['productive']}/{t['turns']} productive{share_str}")
    by = r["by_kind"]
    assert isinstance(by, dict)
    for k, t in by.items():
        lines.append(f"  {k}: {t['productive']}/{t['turns']}")
    return "\n".join(lines)
