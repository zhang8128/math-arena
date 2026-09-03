from __future__ import annotations

import sys
from pathlib import Path

TIMELOOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TIMELOOP))

from driver.brief import (  # noqa: E402
    ALLOWED_WRITES,
    BRIEF_WRITE_SET,
    RESULT_SCHEMA,
    _ledger_block,
    honesty_rules,
    render_brief,
    template_digest,
)
from driver.config import DriverConfig  # noqa: E402
from driver.dispatcher import Brief  # noqa: E402
from driver.state import load_state  # noqa: E402


def test_schema_is_strict_and_excludes_invalid() -> None:
    assert RESULT_SCHEMA["additionalProperties"] is False
    assert (
        "invalid"
        not in RESULT_SCHEMA["properties"]["outcome"]["enum"]  # type: ignore[index]
    )
    assert set(RESULT_SCHEMA["required"]) == {
        "outcome",
        "refinement",
        "ledger_line",
        "files_changed",
        "frames_filed",
        "next_action",
        "notes",
    }  # type: ignore[arg-type]


def test_honesty_rules_are_verbatim() -> None:
    text = honesty_rules(TIMELOOP)
    assert text.startswith("These exist because")
    assert "Never delete a prior turn's finding" in text


def test_render_attack_brief_has_every_section() -> None:
    s = load_state(TIMELOOP)
    b = Brief(
        "T99",
        "attack",
        "lychrel-bases",
        ("carry-transducer-radial-frontier",),
        None,
        None,
        False,
        "attack",
    )
    text = render_brief(b, s, DriverConfig(), TIMELOOP)
    for needle in (
        "T99",
        "attack",
        "lychrel-bases",
        "Treat reverse-and-add as a finite carry transducer",
        "ruled out:",
        "begin with `T99 | `",
        "30 minutes",
        '"additionalProperties": false',
        "Never delete a prior turn's finding",
        ".timeloop/notebook/lychrel-bases.md",
    ):
        assert needle in text, needle
    assert len(text) < 12_000
    # The template keeps only the last three ledger lines for a target, so
    # pinning a literal turn id (e.g. "T25 |") goes red the moment a fourth
    # productive lychrel-bases turn lands. Assert the shape instead: some
    # ledger history was found, and every line found is actually about this
    # target.
    ledger_block = _ledger_block(b, s)
    assert ledger_block and ledger_block != "(no ledger lines mention this target yet)"
    for line in ledger_block.split("\n\n"):
        assert "lychrel-bases" in line, line


def test_brief_write_set_hides_driver_results_but_enforcement_keeps_it() -> None:
    """Cheap fix: a model that honestly declares a write under
    .timeloop/driver/results/ would fail `validate`'s files_mismatch check,
    since that path is driver-owned and excluded from the comparison. The
    brief must not invite the write; recorder.py's enforcement (ALLOWED_WRITES)
    is untouched."""
    assert ".timeloop/driver/results/" not in BRIEF_WRITE_SET
    assert ".timeloop/driver/results/" in ALLOWED_WRITES
    s = load_state(TIMELOOP)
    b = Brief("T99", "attack", "lychrel-bases", (), None, None, False, "")
    text = render_brief(b, s, DriverConfig(), TIMELOOP)
    assert ".timeloop/driver/results/" not in text


def test_render_forage_and_adversarial_briefs() -> None:
    s = load_state(TIMELOOP)
    f = render_brief(
        Brief("T99", "forage-frontier", None, (), "math.NT", None, False, ""),
        s,
        DriverConfig(),
        TIMELOOP,
    )
    assert "https://arxiv.org/list/math.NT/new" in f and "source URL" in f
    a = render_brief(
        Brief(
            "T99",
            "adversarial",
            None,
            (),
            None,
            "T8 | giuga | REDUCED the conjecture | ...",
            False,
            "",
        ),
        s,
        DriverConfig(),
        TIMELOOP,
    )
    assert "independent code path" in a and "T8 | giuga" in a
    assert template_digest(TIMELOOP).startswith("sha256:")
