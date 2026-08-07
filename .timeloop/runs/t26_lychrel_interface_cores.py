#!/usr/bin/env python3
"""Discover deletion-irreducible column obstructions for T25 variants."""

from __future__ import annotations

import gc
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_arbitrary_topology import (  # noqa: E402
    ColumnConstraint,
    DigitAtom,
    GroupedCNFFormula,
    build_column_constraints,
    compile_grouped_one_hot_cnf,
)
from lychrel_interface_perturbations import (  # noqa: E402
    InterfaceMove,
    move_interface,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from t25_lychrel_interface_perturbations_independent import (  # noqa: E402
    BinaryCNF,
)


GROUP_MUS_SOURCE = Path(__file__).with_name("t26_group_mus.cpp")
CADICAL_INCLUDE = Path("/opt/homebrew/opt/cadical/include")
CADICAL_LIBRARY = Path("/opt/homebrew/opt/cadical/lib/libcadical.a")
_CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n0:col(?P<column>\d+)\Z")
_DIGIT_RE = re.compile(
    r"p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z"
)


def variant_id(move: InterfaceMove) -> str:
    sign = "plus" if move.shift > 0 else "minus"
    return f"phase{move.phase}-interface{move.interface}-{sign}{abs(move.shift)}"


def compile_group_mus_binary(output: Path) -> dict[str, object]:
    """Compile the fixed CaDiCaL client and return deterministic provenance."""
    compiler = subprocess.run(
        ("clang++", "--version"),
        check=True,
        text=True,
        capture_output=True,
    )
    command = (
        "clang++",
        "-std=c++17",
        "-O2",
        str(GROUP_MUS_SOURCE),
        f"-I{CADICAL_INCLUDE}",
        str(CADICAL_LIBRARY),
        "-o",
        str(output),
    )
    subprocess.run(command, check=True, text=True, capture_output=True)
    return {
        "compiler": compiler.stdout.splitlines()[0],
        "source_sha256": hashlib.sha256(GROUP_MUS_SOURCE.read_bytes()).hexdigest(),
        "command_flags": ["-std=c++17", "-O2"],
    }


def _selector_map(grouped: GroupedCNFFormula) -> list[tuple[int, str]]:
    start = len(grouped.semantic_keys) + 1
    return [
        (start + index, group.provenance)
        for index, group in enumerate(grouped.groups)
    ]


def _selector_map_digest(mapping: list[tuple[int, str]]) -> str:
    payload = "".join(
        f"{selector}\t{provenance}\n" for selector, provenance in mapping
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _dimacs_bytes(
    variable_count: int,
    clauses: Iterable[Iterable[int]],
) -> bytes:
    materialized = [tuple(clause) for clause in clauses]
    lines = [f"p cnf {variable_count} {len(materialized)}\n"]
    lines.extend(
        " ".join(str(literal) for literal in clause) + " 0\n"
        if clause
        else "0\n"
        for clause in materialized
    )
    return "".join(lines).encode("ascii")


def _run_guarded_problem(
    *,
    base: int,
    extractor: Path,
    mode: str,
    variable_count: int,
    clauses: Iterable[Iterable[int]],
    mapping: list[tuple[int, str]],
    requested_provenances: Iterable[str],
) -> dict[str, object]:
    formula_bytes = _dimacs_bytes(variable_count, clauses)
    formula_digest = hashlib.sha256(formula_bytes).hexdigest()
    by_provenance = {provenance: selector for selector, provenance in mapping}
    by_selector = {selector: provenance for selector, provenance in mapping}
    if len(by_provenance) != len(mapping) or len(by_selector) != len(mapping):
        raise AssertionError("duplicate selector mapping")
    requested = []
    for provenance in requested_provenances:
        if provenance not in by_provenance:
            raise AssertionError(f"unknown group provenance: {provenance}")
        requested.append(by_provenance[provenance])
    if not requested or len(requested) != len(set(requested)):
        raise AssertionError("requested groups must be nonempty and unique")

    with tempfile.TemporaryDirectory(prefix="t26-core-") as temporary:
        directory = Path(temporary)
        formula_path = directory / "formula.cnf"
        selectors_path = directory / "selectors.txt"
        formula_path.write_bytes(formula_bytes)
        selectors_path.write_text(
            "".join(f"{selector}\n" for selector in requested),
            encoding="utf-8",
        )
        completed = subprocess.run(
            (str(extractor), str(formula_path), str(selectors_path), mode),
            check=False,
            text=True,
            capture_output=True,
        )
    if completed.returncode != 0:
        if mode == "verify" and "requested selector set is not UNSAT" in completed.stderr:
            return {
                "base": base,
                "status": "SAT",
                "deletion_statuses": [],
                "deletions": [],
                "formula_sha256": formula_digest,
                "selector_map_sha256": _selector_map_digest(mapping),
                "input_variables": variable_count,
                "input_clauses": formula_bytes.count(b" 0\n") + formula_bytes.count(b"\n0\n"),
            }
        raise RuntimeError(completed.stderr.strip() or "group-MUS client failed")
    if completed.stderr:
        raise RuntimeError(f"unexpected group-MUS stderr: {completed.stderr}")
    raw = json.loads(completed.stdout)
    if raw.get("requested_selectors") != requested:
        raise AssertionError("group-MUS client changed requested selector order")
    core_selectors = raw.get("core_selectors")
    if not isinstance(core_selectors, list) or not core_selectors:
        raise AssertionError("group-MUS client returned an empty or malformed core")
    try:
        core_provenances = [by_selector[selector] for selector in core_selectors]
    except KeyError as error:
        raise AssertionError("group-MUS client returned an unknown selector") from error
    deletions = raw.get("deletion_statuses")
    expected_deletions = 0 if mode == "seed" else len(core_selectors)
    if not isinstance(deletions, list) or len(deletions) != expected_deletions:
        raise AssertionError("group-MUS deletion evidence is incomplete")
    mapped_deletions = []
    statuses = []
    for selector, deletion in zip(core_selectors, deletions):
        if deletion.get("selector") != selector:
            raise AssertionError("group-MUS deletion order mismatch")
        status = deletion.get("status")
        if status not in ("SAT", "UNSAT"):
            raise AssertionError("group-MUS deletion status is malformed")
        statuses.append(status)
        mapped_deletions.append(
            {"provenance": by_selector[selector], "status": status}
        )
    return {
        "base": base,
        "status": raw["status"],
        "core_provenances": core_provenances,
        "deletion_statuses": statuses,
        "deletions": mapped_deletions,
        "formula_sha256": formula_digest,
        "selector_map_sha256": _selector_map_digest(mapping),
        "input_variables": raw["input_variables"],
        "input_clauses": raw["input_clauses"],
        "cadical_version": raw["cadical_version"],
        "solve_calls": raw["solve_calls"],
    }


def _run_extractor(
    grouped: GroupedCNFFormula,
    extractor: Path,
    mode: str,
    provenances: Iterable[str] | None = None,
) -> dict[str, object]:
    mapping = _selector_map(grouped)
    selected = (
        tuple(group.provenance for group in grouped.groups)
        if provenances is None
        else tuple(provenances)
    )
    selected_set = set(selected)
    selector_by_provenance = {
        provenance: selector for selector, provenance in mapping
    }
    clauses: list[tuple[int, ...]] = list(grouped.hard_clauses)
    for group in grouped.groups:
        if group.provenance in selected_set:
            selector = selector_by_provenance[group.provenance]
            clauses.extend((-selector,) + clause for clause in group.clauses)
    return _run_guarded_problem(
        base=grouped.base,
        extractor=extractor,
        mode=mode,
        variable_count=len(grouped.semantic_keys) + len(grouped.groups),
        clauses=clauses,
        mapping=mapping,
        requested_provenances=selected,
    )


def _flat_digit_map(
    words: tuple[ParametricWord, ...],
) -> dict[str, tuple[str, int, int]]:
    result: dict[str, tuple[str, int, int]] = {}
    for phase, word in enumerate(words):
        flat_offset = 0
        for fragment, digits in enumerate(word.fragments):
            for offset in range(len(digits)):
                result[f"p{phase}:f{fragment}:d{offset}"] = (
                    "digit",
                    phase,
                    flat_offset + offset,
                )
            flat_offset += len(digits)
    return result


def _canonical_atom(
    atom: DigitAtom,
    base: int,
    digit_map: dict[str, tuple[str, int, int]],
) -> object:
    if atom.variable is not None:
        if atom.variable not in digit_map or not _DIGIT_RE.fullmatch(atom.variable):
            raise AssertionError(f"malformed digit variable: {atom.variable}")
        return list(digit_map[atom.variable])
    if atom.value == base - 1:
        return ["constant", "B-1"]
    return ["constant", atom.value]


def _canonical_carry(carry: str | None) -> object:
    if carry is None:
        return None
    match = _CARRY_RE.fullmatch(carry)
    if match is None:
        raise AssertionError(f"malformed n=0 carry: {carry}")
    return ["carry", int(match["phase"]), int(match["column"])]


def canonical_incidence(
    words: tuple[ParametricWord, ...],
    base: int,
    provenances: Iterable[str],
) -> tuple[list[dict[str, object]], str]:
    """Serialize exact core equations independently of fragment boundaries."""
    constraints = build_column_constraints(words, base, parameters=(0,))
    by_provenance: dict[str, ColumnConstraint] = {}
    for constraint in constraints:
        if constraint.provenance in by_provenance:
            raise AssertionError("duplicate constraint provenance")
        by_provenance[constraint.provenance] = constraint
    digit_map = _flat_digit_map(words)
    rows = []
    for provenance in provenances:
        try:
            constraint = by_provenance[provenance]
        except KeyError as error:
            raise AssertionError(f"missing core constraint: {provenance}") from error
        phase_text, n_text, column_text = provenance.split(",")
        if n_text != "n=0":
            raise AssertionError("T26 incidence contains a nonzero parameter")
        rows.append(
            {
                "coordinate": [
                    int(phase_text.removeprefix("phase=")),
                    int(column_text.removeprefix("column=")),
                ],
                "left": _canonical_atom(constraint.left, base, digit_map),
                "right": _canonical_atom(constraint.right, base, digit_map),
                "target": _canonical_atom(constraint.target, base, digit_map),
                "carry_in": _canonical_carry(constraint.carry_in),
                "carry_out": _canonical_carry(constraint.carry_out),
            }
        )
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return rows, hashlib.sha256(payload).hexdigest()


def _binary_guarded_problem(
    formula: BinaryCNF,
    selected_provenances: Iterable[str],
) -> tuple[int, list[list[int]], list[tuple[int, str]]]:
    selected = set(selected_provenances)
    mapping = [
        (len(formula.ids) + 1 + index, provenance)
        for index, (provenance, _, _) in enumerate(formula.column_groups)
    ]
    selectors = {provenance: selector for selector, provenance in mapping}
    if not selected <= set(selectors):
        raise AssertionError("binary formula lacks a selected provenance")
    clauses = [list(clause) for clause in formula.clauses[: formula.hard_clause_count]]
    for provenance, start, stop in formula.column_groups:
        if provenance in selected:
            selector = selectors[provenance]
            clauses.extend(
                [-selector] + list(clause)
                for clause in formula.clauses[start:stop]
            )
    return len(formula.ids) + len(mapping), clauses, mapping


def _serialize_words(words: tuple[ParametricWord, ...]) -> list[dict[str, object]]:
    return [
        {
            "fragments": [list(fragment) for fragment in word.fragments],
            "repeats": list(word.repeats),
        }
        for word in words
    ]


def _column_ranges(provenances: Iterable[str]) -> dict[str, list[list[int]]]:
    by_phase: dict[int, list[int]] = {}
    for provenance in provenances:
        phase_text, n_text, column_text = provenance.split(",")
        if n_text != "n=0":
            raise AssertionError("core contains a nonzero parameter")
        phase = int(phase_text.removeprefix("phase="))
        column = int(column_text.removeprefix("column="))
        by_phase.setdefault(phase, []).append(column)
    result: dict[str, list[list[int]]] = {}
    for phase, columns in sorted(by_phase.items()):
        ordered = sorted(columns)
        ranges: list[list[int]] = []
        start = stop = ordered[0]
        for column in ordered[1:]:
            if column == stop + 1:
                stop = column
            else:
                ranges.append([start, stop])
                start = stop = column
        ranges.append([start, stop])
        result[str(phase)] = ranges
    return result


def extract_hybrid_core(
    words: tuple[ParametricWord, ...],
    move: InterfaceMove,
    base: int,
    extractor: Path,
) -> dict[str, object]:
    """Seed in binary CNF, minimize there, and replay in one-hot CNF."""
    moved = move_interface(words, move)
    binary = BinaryCNF(base, _serialize_words(moved))
    binary.build()
    all_provenances = tuple(
        provenance for provenance, _, _ in binary.column_groups
    )
    variables, clauses, mapping = _binary_guarded_problem(
        binary,
        all_provenances,
    )
    seed = _run_guarded_problem(
        base=base,
        extractor=extractor,
        mode="seed",
        variable_count=variables,
        clauses=clauses,
        mapping=mapping,
        requested_provenances=all_provenances,
    )
    seed_provenances = tuple(seed["core_provenances"])

    variables, clauses, mapping = _binary_guarded_problem(
        binary,
        seed_provenances,
    )
    binary_certificate = _run_guarded_problem(
        base=base,
        extractor=extractor,
        mode="extract",
        variable_count=variables,
        clauses=clauses,
        mapping=mapping,
        requested_provenances=seed_provenances,
    )
    core = tuple(binary_certificate["core_provenances"])
    if set(binary_certificate["deletion_statuses"]) != {"SAT"}:
        raise AssertionError("binary core is not deletion-irreducible")

    grouped = compile_grouped_one_hot_cnf(moved, base, parameters=(0,))
    one_hot_certificate = _run_extractor(
        grouped,
        extractor,
        "verify",
        core,
    )
    if (
        one_hot_certificate["core_provenances"] != list(core)
        or set(one_hot_certificate["deletion_statuses"]) != {"SAT"}
    ):
        raise AssertionError("one-hot certificate disagrees with binary core")
    return {
        "base": base,
        "seed_size": len(seed_provenances),
        "core_size": len(core),
        "core_provenances": list(core),
        "columns_by_phase": _column_ranges(core),
        "binary_seed": seed,
        "binary_certificate": binary_certificate,
        "one_hot_certificate": one_hot_certificate,
    }


def verify_hybrid_core(
    words: tuple[ParametricWord, ...],
    move: InterfaceMove,
    base: int,
    provenances: Iterable[str],
    extractor: Path,
) -> dict[str, object]:
    """Replay one exact column core in binary and one-hot encodings."""
    moved = move_interface(words, move)
    core = tuple(provenances)
    if not core or len(core) != len(set(core)):
        raise ValueError("core provenances must be nonempty and unique")
    binary = BinaryCNF(base, _serialize_words(moved))
    binary.build()
    variables, clauses, mapping = _binary_guarded_problem(binary, core)
    binary_certificate = _run_guarded_problem(
        base=base,
        extractor=extractor,
        mode="verify",
        variable_count=variables,
        clauses=clauses,
        mapping=mapping,
        requested_provenances=core,
    )
    grouped = compile_grouped_one_hot_cnf(moved, base, parameters=(0,))
    one_hot_certificate = _run_extractor(
        grouped,
        extractor,
        "verify",
        core,
    )
    return {
        "base": base,
        "core_size": len(core),
        "core_provenances": list(core),
        "columns_by_phase": _column_ranges(core),
        "binary_certificate": binary_certificate,
        "one_hot_certificate": one_hot_certificate,
    }


def discover_variant_families(
    words: tuple[ParametricWord, ...],
    move: InterfaceMove,
    bases: tuple[int, ...],
    extractor: Path,
    *,
    extract_core: Callable[..., dict[str, object]] = extract_hybrid_core,
    verify_core: Callable[..., dict[str, object]] = verify_hybrid_core,
) -> dict[str, object]:
    """Cover bases by representative deletion-irreducible core families."""
    if not bases or tuple(sorted(set(bases))) != bases:
        raise ValueError("bases must be nonempty, unique, and increasing")
    moved = move_interface(words, move)
    uncovered = list(bases)
    families = []
    while uncovered:
        representative = uncovered[0]
        extracted = extract_core(words, move, representative, extractor)
        core = extracted["core_provenances"]
        rows, incidence_digest = canonical_incidence(moved, representative, core)
        gc.collect()

        covered: list[int] = []
        verifications: list[dict[str, object]] = []
        for base in list(uncovered):
            if base == representative:
                verification = extracted
            else:
                verification = verify_core(
                    words,
                    move,
                    base,
                    core,
                    extractor,
                )
                gc.collect()
            base_rows, base_digest = canonical_incidence(moved, base, core)
            if base_rows != rows or base_digest != incidence_digest:
                raise AssertionError("canonical core incidence changed with base")
            if (
                verification["binary_certificate"]["status"] == "UNSAT"
                and verification["one_hot_certificate"]["status"] == "UNSAT"
                and set(
                    verification["binary_certificate"]["deletion_statuses"]
                )
                == {"SAT"}
                and set(
                    verification["one_hot_certificate"]["deletion_statuses"]
                )
                == {"SAT"}
            ):
                covered.append(base)
                verifications.append(verification)
        if representative not in covered:
            raise AssertionError("representative family made no progress")
        covered_set = set(covered)
        uncovered = [base for base in uncovered if base not in covered_set]
        families.append(
            {
                "family_index": len(families),
                "representative_base": representative,
                "covered_bases": covered,
                "core_size": len(core),
                "core_provenances": core,
                "canonical_incidence": rows,
                "canonical_incidence_sha256": incidence_digest,
                "verifications": verifications,
            }
        )

    assigned = [base for family in families for base in family["covered_bases"]]
    if sorted(assigned) != list(bases) or len(assigned) != len(set(assigned)):
        raise AssertionError("family coverage is incomplete or overlapping")
    return {
        "variant_id": variant_id(move),
        "move": {
            "phase": move.phase,
            "interface": move.interface,
            "shift": move.shift,
        },
        "bases": list(bases),
        "families": families,
        "uncovered_bases": [],
    }


def main() -> None:
    raise SystemExit("use build_primary_evidence from the completed T26 runner")


if __name__ == "__main__":
    main()
