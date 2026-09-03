"""Render a one-page brief from a Brief record and the room state."""

from __future__ import annotations

import hashlib
import json
import re
import string
from pathlib import Path

from driver.config import DriverConfig
from driver.dispatcher import Brief
from driver.state import State

ALLOWED_WRITES: tuple[str, ...] = (
    ".timeloop/ledger.md", ".timeloop/notebook/", ".timeloop/pool.jsonl", ".timeloop/lib/",
    ".timeloop/runs/", ".timeloop/tests/", ".timeloop/lean/arena/", ".timeloop/driver/results/",
)

# What the brief tells the model it may write. Excludes .timeloop/driver/results/:
# that path is driver-owned (the recorder writes the raw result there itself), and
# `validate` excludes driver-owned paths from the files_changed comparison, so a
# model that honestly declares a write there would get `files_mismatch`. Kept
# separate from ALLOWED_WRITES, which recorder.py's `is_allowed` still enforces
# unchanged, so this display-only trim cannot change what gets reverted or staged.
BRIEF_WRITE_SET: tuple[str, ...] = tuple(
    p for p in ALLOWED_WRITES if p != ".timeloop/driver/results/"
)

FRAME_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["slug", "title", "statement", "shape", "source"],
    "properties": {
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "statement": {"type": "string"},
        "shape": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "source": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind"],
            "properties": {
                "kind": {"enum": ["arxiv", "doi", "oeis", "web", "own"]},
                "id": {"type": "string"},
                "url": {"type": "string"},
            },
        },
    },
}

RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "outcome",
        "refinement",
        "ledger_line",
        "files_changed",
        "frames_filed",
        "next_action",
        "notes",
    ],
    "properties": {
        "outcome": {
            "enum": [
                "negative",
                "structure",
                "correction",
                "verified",
                "counterexample",
                "frames",
                "nothing",
            ]
        },
        "refinement": {"type": "boolean"},
        "ledger_line": {"type": ["string", "null"]},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "frames_filed": {"type": "array", "items": FRAME_SCHEMA},
        "next_action": {"type": ["string", "null"]},
        "notes": {"type": "string"},
    },
}

KIND_RULES: dict[str, str] = {
    "attack": (
        "Attack the target with the single frame below. Bounded compute. Record "
        "what it ruled out or found. Report `nothing` honestly if that is what happened."
    ),
    "combine": (
        "Apply the two frames below together on the target. The question is their "
        "interaction: what does one frame's output let the other frame do that it could "
        "not do alone. Two separate attacks is the wrong answer."
    ),
    "forage-target": (
        "Search the web (arXiv, OEIS, MathOverflow, blogs) for methods that fit the "
        "target's shape and that no existing frame covers. File each as a frame with a "
        "source URL. Do not attack the target this turn."
    ),
    "forage-frontier": (
        "Read the new-listings page $listing and skim abstracts for methods that could "
        "transplant to any target in the pool. File each as a frame with the arXiv URL. "
        "A target is optional. Do not attack anything this turn."
    ),
    "adversarial": (
        "Below is a prior recorded claim. Try to break it with an independent code path "
        "that does not import the code that produced it. Report `correction` if it breaks, "
        "`verified` if it survives with a stated range, `nothing` if you could not test "
        "it in the budget."
    ),
    "patrol": (
        "Re-run the recorded NOVELTY queries for the targets with the oldest novelty "
        "checks and for all parked or superseded targets. Append a correction to the "
        "notebook where the literature has moved. Do not attack anything this turn."
    ),
}


def sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_digest(root: Path) -> str:
    t = root / "driver" / "templates"
    return sha256((t / "brief.md").read_text() + (t / "system.md").read_text())


def honesty_rules(root: Path) -> str:
    text = (root / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## Honesty rules\s*\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    if not m:
        raise ValueError("README.md has no '## Honesty rules' section")
    return m.group(1).strip()


def _index_line(root: Path, slug: str) -> str:
    idx = root / "index.md"
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"- {slug} |"):
                return line
    return f"- {slug} | (no index line; run bin/lint --index)"


def _target_block(brief: Brief, state: State, root: Path) -> str:
    if brief.target is None:
        if brief.kind == "adversarial":
            return f"Claim under test:\n\n    {brief.claim or '(no prior claims recorded)'}"
        if brief.kind == "forage-frontier":
            return f"Category: {brief.category}. No target this turn."
        return "No target this turn."
    t = state.target(brief.target)
    rec = {k: v for k, v in t.raw.items() if not str(k).startswith("_")}
    index_line = _index_line(root, t.slug)
    return (
        f"```json\n{json.dumps(rec, indent=1)}\n```\n\nIndex line:\n\n"
        f"{index_line}"
    )


def _ledger_block(brief: Brief, state: State) -> str:
    if brief.target is None:
        return "(none)"
    lines = [ln for ln in state.ledger_lines if f"| {brief.target} |" in ln][-3:]
    return "\n\n".join(lines) if lines else "(no ledger lines mention this target yet)"


def _frames_block(brief: Brief, state: State) -> str:
    if brief.kind in ("forage-target", "forage-frontier"):
        slugs = ", ".join(f.slug for f in state.frames)
        return (
            "You are filing frames, not using them. Existing frame slugs, to avoid "
            f"duplicates:\n\n{slugs}"
        )
    if not brief.frames:
        return "(none)"
    out = []
    for slug in brief.frames:
        f = state.frame(slug)
        shape = ", ".join(f.shape)
        out.append(
            f"### {f.title}\n\nslug: `{f.slug}`  shape: {shape}\n\n{f.statement}"
        )
    return "\n\n".join(out)


def render_brief(brief: Brief, state: State, config: DriverConfig, root: Path) -> str:
    template_path = root / "driver" / "templates" / "brief.md"
    template = string.Template(template_path.read_text(encoding="utf-8"))
    listing = (
        f"https://arxiv.org/list/{brief.category}/new"
        if brief.category
        else ""
    )
    rules = KIND_RULES[brief.kind].replace("$listing", listing)
    return template.substitute(
        turn_id=brief.turn_id,
        turn_id_lower=brief.turn_id.lower(),
        kind=brief.kind,
        kind_rules=rules,
        target_block=_target_block(brief, state, root),
        ledger_block=_ledger_block(brief, state),
        frames_block=_frames_block(brief, state),
        honesty_rules=honesty_rules(root),
        allowed_writes=", ".join(BRIEF_WRITE_SET),
        notebook_slug=brief.target or "<slug>",
        result_schema=json.dumps(RESULT_SCHEMA, indent=1),
    )
