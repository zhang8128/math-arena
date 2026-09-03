from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.index import build_index, index_line, last_section  # noqa: E402

NOTEBOOK = """# x

## STATUS
open

## RULED OUT
- nothing below 10^6

## T9 STATUS — later round
### STATUS
parked, wall reached

### RULED OUT
all residues mod 9

### NEXT
try cubics
"""


def test_last_section_takes_the_last_header() -> None:
    assert last_section(NOTEBOOK, "STATUS") == "parked, wall reached"
    assert last_section(NOTEBOOK, "RULED OUT") == "all residues mod 9"
    assert last_section(NOTEBOOK, "NEXT") == "try cubics"
    assert last_section(NOTEBOOK, "COST") is None


def test_index_line_falls_back_to_pool() -> None:
    line = index_line("slug", None, "open", "a long statement " * 20)
    assert line.startswith("- slug | open | ")
    assert len(line) < 400


def test_build_index_covers_every_pool_target(tmp_path: Path) -> None:
    root = tmp_path / ".timeloop"
    (root / "notebook").mkdir(parents=True)
    (root / "pool.jsonl").write_text(
        json.dumps({"slug": "a", "status": "open", "statement": "s", "tags": ["x"]}) + "\n"
        + json.dumps({"slug": "b", "status": "open", "statement": "t", "tags": ["y"]}) + "\n"
    )
    (root / "notebook" / "a.md").write_text(NOTEBOOK)
    text = build_index(root)
    assert "- a | parked, wall reached | ruled out: all residues mod 9 | next: try cubics" in text
    assert "- b | open | ruled out: (no notebook) | next: t" in text


def test_lint_index_mode_writes_file_and_flags_untagged(tmp_path: Path) -> None:
    root = TIMELOOP
    out = subprocess.run(
        [sys.executable, str(root / "bin" / "lint"), "--index"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "wrote" in out
    assert (root / "index.md").exists()
    assert "lychrel-bases" in (root / "index.md").read_text()
