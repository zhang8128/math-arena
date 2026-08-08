#!/usr/bin/env python3
"""Run a deterministic, resumable exact audit of all single deletions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import cache
from multiprocessing import get_context
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_interface_perturbations import InterfaceMove, move_interface  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402
from t26_radial_frontier import (  # noqa: E402
    base19_candidate_provenances,
    replay_radial_witness,
    solve_radial_frontier,
)

SCHEMA = "base19-radial-deletion-v1"
EXPECTED_REPLAY = {
    "status": "valid",
    "equation_count": 408,
    "digit_count": 409,
    "carry_count": 410,
}
EQUATIONS = ROOT / "publication" / "base19-radial" / "instance" / "equations.json"


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _content_digested(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["content_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def _validate_digest(record: dict[str, Any]) -> None:
    unsigned = dict(record)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError("deletion record content digest mismatch")


def make_record(
    index: int,
    removed: str,
    status: str,
    witness: dict[str, Any] | None,
    witness_replay: dict[str, Any] | None,
) -> dict[str, Any]:
    if status not in {"SAT", "UNSAT"}:
        raise ValueError("deletion result is not exact")
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "candidate_index": index,
        "removed": removed,
        "status": status,
        "equation_count": 408,
    }
    if status == "SAT":
        if not isinstance(witness, dict) or not isinstance(witness_replay, dict):
            raise ValueError("SAT deletion record is missing its witness")
        record["witness"] = witness
        record["witness_replay"] = witness_replay
    elif witness is not None or witness_replay is not None:
        raise ValueError("UNSAT deletion record unexpectedly contains a witness")
    return _content_digested(record)


def _validate_record(
    record: object,
    expected_index: int,
    expected_removed: str,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("deletion record is not an object")
    _validate_digest(record)
    if record.get("schema") != SCHEMA:
        raise ValueError("deletion record schema is invalid")
    if record.get("candidate_index") != expected_index:
        raise ValueError("deletion record index is not contiguous")
    if record.get("removed") != expected_removed:
        raise ValueError("deletion record provenance is out of order")
    if record.get("equation_count") != 408:
        raise ValueError("deletion record equation count is invalid")
    status = record.get("status")
    base_keys = {
        "schema",
        "candidate_index",
        "removed",
        "status",
        "equation_count",
        "content_sha256",
    }
    if status == "SAT":
        if set(record) != base_keys | {"witness", "witness_replay"}:
            raise ValueError("SAT deletion record fields are invalid")
        if not isinstance(record["witness"], dict):
            raise ValueError("SAT deletion witness is malformed")
        replay = record["witness_replay"]
        if not isinstance(replay, dict) or replay.get("status") != "valid":
            raise ValueError("SAT deletion replay metadata is invalid")
    elif status == "UNSAT":
        if set(record) != base_keys:
            raise ValueError("UNSAT deletion record fields are invalid")
    else:
        raise ValueError("deletion record status is not exact")
    return record


def _moved_words():
    return move_interface(base17_reference_cycle(), InterfaceMove(0, 0, -2))


@cache
def _equations() -> tuple[dict[str, Any], ...]:
    payload = json.loads(EQUATIONS.read_text(encoding="utf-8"))
    equations = payload.get("equations")
    if not isinstance(equations, list) or len(equations) != 409:
        raise ValueError("equation manifest must contain 409 equations")
    return tuple(equations)


@cache
def _full_variable_names() -> tuple[frozenset[str], frozenset[str]]:
    digits: set[str] = set()
    carries: set[str] = set()
    for equation in _equations():
        for key in ("left", "right", "target"):
            atom = equation[key]
            if "variable" in atom:
                digits.add(atom["variable"])
        for key in ("carry_in", "carry_out"):
            if equation[key] is not None:
                carries.add(equation[key])
    if len(digits) != 409 or len(carries) != 410:
        raise ValueError("full witness variable counts changed")
    return frozenset(digits), frozenset(carries)


def validate_projected_replay(
    replay: dict[str, Any], witness: dict[str, Any]
) -> None:
    digits = witness.get("digits")
    carries = witness.get("carries")
    if not isinstance(digits, dict) or not isinstance(carries, dict):
        raise ValueError("projected deletion witness is malformed")
    expected = {
        "status": "valid",
        "equation_count": 408,
        "digit_count": len(digits),
        "carry_count": len(carries),
    }
    if replay != expected:
        raise ValueError("projected deletion witness replay metadata changed")


def complete_witness(witness: dict[str, Any]) -> dict[str, dict[str, int]]:
    digits = witness.get("digits")
    carries = witness.get("carries")
    if not isinstance(digits, dict) or not isinstance(carries, dict):
        raise ValueError("projected deletion witness is malformed")
    full_digits, full_carries = _full_variable_names()
    if not set(digits) <= full_digits or not set(carries) <= full_carries:
        raise ValueError("projected deletion witness contains an unknown variable")
    if any(type(value) is not int or not 0 <= value < 19 for value in digits.values()):
        raise ValueError("projected deletion witness digit is out of range")
    if any(value not in (0, 1) for value in carries.values()):
        raise ValueError("projected deletion witness carry is not binary")
    leading = {f"p{phase}:f0:d0" for phase in range(6)}
    return {
        "digits": {
            name: digits.get(name, 1 if name in leading else 0)
            for name in sorted(full_digits)
        },
        "carries": {name: carries.get(name, 0) for name in sorted(full_carries)},
    }


def replay_completed_witness(
    removed: str, witness: dict[str, Any]
) -> dict[str, Any]:
    completed = complete_witness(witness)
    digits = completed["digits"]
    carries = completed["carries"]
    retained = 0

    def atom_value(atom: dict[str, Any]) -> int:
        if "literal" in atom:
            return atom["literal"]
        return digits[atom["variable"]]

    for equation in _equations():
        if equation["provenance"] == removed:
            continue
        retained += 1
        carry_in = 0 if equation["carry_in"] is None else carries[equation["carry_in"]]
        carry_out = (
            0 if equation["carry_out"] is None else carries[equation["carry_out"]]
        )
        if (
            atom_value(equation["left"])
            + atom_value(equation["right"])
            + carry_in
            != atom_value(equation["target"]) + 19 * carry_out
        ):
            raise ValueError(
                "completed deletion witness violates " + equation["provenance"]
            )
    if retained != 408:
        raise ValueError("completed deletion witness removes the wrong equation")
    if any(digits[name] <= 0 for name in {f"p{phase}:f0:d0" for phase in range(6)}):
        raise ValueError("completed deletion witness has a zero leading digit")
    return dict(EXPECTED_REPLAY)


def _retained_provenances(removed: str) -> tuple[str, ...]:
    candidates = base19_candidate_provenances()
    retained = tuple(provenance for provenance in candidates if provenance != removed)
    if len(retained) != 408:
        raise ValueError("deletion provenance is absent or duplicated")
    return retained


def _replay_sat_record(record: dict[str, Any]) -> None:
    actual = replay_completed_witness(record["removed"], record["witness"])
    if actual != record["witness_replay"] or actual != EXPECTED_REPLAY:
        raise ValueError("deletion witness exact replay changed")


def load_prefix(
    output: Path,
    candidates: tuple[str, ...],
    *,
    replay_sat: bool = True,
) -> dict[int, dict[str, Any]]:
    if not output.exists():
        return {}
    raw = output.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("deletion audit has a truncated final line")
    records: dict[int, dict[str, Any]] = {}
    for index, line in enumerate(raw.splitlines(keepends=True)):
        if index >= len(candidates):
            raise ValueError("deletion audit contains extra records")
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError("deletion audit contains invalid JSON") from error
        record = _validate_record(parsed, index, candidates[index])
        if line != canonical_bytes(record):
            raise ValueError("deletion audit record is not canonical JSON")
        if replay_sat and record["status"] == "SAT":
            _replay_sat_record(record)
        records[index] = record
    return records


def append_ready_records(
    output: Path,
    candidates: tuple[str, ...],
    pending: dict[int, dict[str, Any]],
    next_index: int,
) -> int:
    if not 0 <= next_index <= len(candidates):
        raise ValueError("deletion audit next index is invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("ab") as stream:
        while next_index in pending:
            record = _validate_record(
                pending.pop(next_index), next_index, candidates[next_index]
            )
            stream.write(canonical_bytes(record))
            stream.flush()
            os.fsync(stream.fileno())
            next_index += 1
    return next_index


def minimality_promotable(
    records: dict[int, dict[str, Any]], candidates: tuple[str, ...]
) -> bool:
    if set(records) != set(range(len(candidates))):
        return False
    removed = []
    for index, candidate in enumerate(candidates):
        record = records[index]
        if record.get("removed") != candidate or record.get("status") != "SAT":
            return False
        if not isinstance(record.get("witness"), dict):
            return False
        replay = record.get("witness_replay")
        if not isinstance(replay, dict) or replay.get("status") != "valid":
            return False
        removed.append(record["removed"])
    return len(set(removed)) == len(candidates)


def _solve_deletion(task: tuple[int, str]) -> tuple[int, dict[str, Any]]:
    index, removed = task
    retained = _retained_provenances(removed)
    evidence = solve_radial_frontier(
        _moved_words(),
        19,
        retained,
        include_witness=True,
    )
    status = evidence.get("status")
    if status == "SAT":
        projected = evidence.get("witness")
        if not isinstance(projected, dict):
            raise ValueError(f"deletion witness is missing for {removed}")
        replay = replay_radial_witness(_moved_words(), 19, retained, projected)
        validate_projected_replay(replay, projected)
        if evidence.get("witness_replay") != replay:
            raise ValueError(f"deletion witness replay failed for {removed}")
        witness = complete_witness(projected)
        full_replay = replay_completed_witness(removed, witness)
        return index, make_record(index, removed, "SAT", witness, full_replay)
    if status == "UNSAT":
        return index, make_record(index, removed, "UNSAT", None, None)
    raise ValueError(f"deletion solver returned a nonexact status for {removed}")


def run_audit(output: Path, workers: int) -> dict[int, dict[str, Any]]:
    if workers <= 0:
        raise ValueError("worker count must be positive")
    candidates = base19_candidate_provenances()
    if len(candidates) != 409 or len(set(candidates)) != 409:
        raise ValueError("candidate provenance list is not the expected 409-set")
    records = load_prefix(output, candidates)
    next_index = len(records)
    if next_index == len(candidates):
        return records
    tasks = [(index, candidates[index]) for index in range(next_index, len(candidates))]
    pending: dict[int, dict[str, Any]] = {}
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("spawn"),
    ) as executor:
        futures = {executor.submit(_solve_deletion, task): task for task in tasks}
        for future in as_completed(futures):
            index, record = future.result()
            if index in pending or index in records:
                raise ValueError("deletion worker returned a duplicate index")
            pending[index] = record
            previous = next_index
            ready: dict[int, dict[str, Any]] = {}
            cursor = next_index
            while cursor in pending:
                ready[cursor] = pending[cursor]
                cursor += 1
            next_index = append_ready_records(output, candidates, pending, next_index)
            records.update(ready)
            if next_index != previous:
                print(f"committed {next_index}/{len(candidates)}", flush=True)
    if next_index != len(candidates) or pending:
        raise ValueError("deletion audit ended with an incomplete prefix")
    return load_prefix(output, candidates)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    records = run_audit(args.output, args.workers)
    candidates = base19_candidate_provenances()
    outcome = "deletion-minimal" if minimality_promotable(records, candidates) else "not-promoted"
    print(f"audit complete: {len(records)}/{len(candidates)}; {outcome}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"audit_deletions: {error}", file=sys.stderr)
        sys.exit(1)
