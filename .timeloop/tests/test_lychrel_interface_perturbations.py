from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_arbitrary_topology import (  # noqa: E402
    DigitAtom,
    build_column_constraints,
)
from lychrel_interface_perturbations import (  # noqa: E402
    InterfaceMove,
    all_moves,
    move_interface,
    n_zero_relevant_moves,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


def test_positive_shift_moves_boundary_right_by_literal_columns() -> None:
    words = (
        ParametricWord(
            17,
            ((1, 2, 3), (4, 5, 6), (7, 8)),
            (0, 16),
        ),
    )

    moved = move_interface(words, InterfaceMove(0, 0, 2))

    assert moved == (
        ParametricWord(
            17,
            ((1, 2, 3, 4, 5), (6,), (7, 8)),
            (0, 16),
        ),
    )


def test_negative_shift_moves_boundary_left_and_preserves_order() -> None:
    words = (
        ParametricWord(
            17,
            ((1, 2, 3), (4, 5, 6), (7, 8)),
            (0, 16),
        ),
    )

    moved = move_interface(words, InterfaceMove(0, 1, -1))

    assert moved[0].fragments == ((1, 2, 3), (4, 5), (6, 7, 8))
    assert moved[0].repeats == (0, 16)
    assert tuple(digit for fragment in moved[0].fragments for digit in fragment) == (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    )


@pytest.mark.parametrize(
    "move",
    (
        InterfaceMove(0, 0, 0),
        InterfaceMove(-1, 0, 1),
        InterfaceMove(1, 0, 1),
        InterfaceMove(0, -1, 1),
        InterfaceMove(0, 2, 1),
        InterfaceMove(0, 0, 3),
        InterfaceMove(0, 0, -2),
    ),
)
def test_invalid_or_empty_fragment_moves_are_rejected(move: InterfaceMove) -> None:
    words = (ParametricWord(17, ((1,), (2, 3), (4,)), (0, 16)),)

    with pytest.raises(ValueError):
        move_interface(words, move)


def test_t21_enumeration_has_48_moves_and_eight_relevant_moves() -> None:
    words = base17_reference_cycle()

    moves = all_moves(words, max_shift=2)
    relevant = n_zero_relevant_moves(words, max_shift=2)

    assert len(moves) == 48
    assert len(set(moves)) == 48
    assert {move.phase for move in relevant} == {0}
    assert {(move.interface, move.shift) for move in relevant} == {
        (interface, shift)
        for interface in (0, 1)
        for shift in (-2, -1, 1, 2)
    }


def _digit_renaming(words: tuple[ParametricWord, ...]) -> dict[str, str]:
    names = {}
    for phase, word in enumerate(words):
        flat = 0
        for fragment_index, fragment in enumerate(word.fragments):
            for offset in range(len(fragment)):
                names[f"p{phase}:f{fragment_index}:d{offset}"] = (
                    f"p{phase}:flat{flat}"
                )
                flat += 1
    return names


def _canonical_atom(atom: DigitAtom, names: dict[str, str]) -> tuple[str, object]:
    if atom.variable is not None:
        return ("variable", names[atom.variable])
    return ("constant", atom.value)


def _canonical_n_zero_columns(
    words: tuple[ParametricWord, ...],
) -> tuple[tuple[object, ...], ...]:
    names = _digit_renaming(words)
    return tuple(
        (
            _canonical_atom(column.left, names),
            _canonical_atom(column.right, names),
            _canonical_atom(column.target, names),
            column.carry_in,
            column.carry_out,
            column.provenance,
        )
        for column in build_column_constraints(words, 17, parameters=(0,))
    )


def test_only_phase_zero_moves_change_the_canonical_n_zero_system() -> None:
    words = base17_reference_cycle()
    baseline = _canonical_n_zero_columns(words)

    for move in all_moves(words, max_shift=2):
        changed = _canonical_n_zero_columns(move_interface(words, move)) != baseline
        assert changed is (move.phase == 0), move


def test_primary_evidence_classifies_every_relevant_instance() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "runs"
        / "t25_lychrel_interface_perturbations.py"
    )

    completed = subprocess.run(
        ["/usr/local/bin/sage", "-python", str(script)],
        check=True,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    evidence = json.loads(completed.stdout)

    assert evidence["kind"] == "single_interface_topology_classification"
    assert evidence["status"] in {
        "no_n_zero_realizations",
        "no_verified_realizations",
        "verified_realizations",
    }
    assert evidence["scope"]["total_moves"] == 48
    assert evidence["structural_reduction"] == {
        "inherited_moves": 40,
        "relevant_phase": 0,
        "scanned_moves": 8,
        "reason": (
            "at n=0 only the wrap output contains repeats, and it targets phase 0"
        ),
        "t24_bases": list(range(18, 41)),
    }
    assert len(evidence["inherited_variants"]) == 40
    assert {item["phase"] for item in evidence["inherited_variants"]} == {
        1,
        2,
        3,
        4,
        5,
    }
    variants = evidence["scan"]["variants"]
    assert len(variants) == 8
    assert evidence["scan"]["instances"] == 184
    assert evidence["scan"]["base_start"] == 18
    assert evidence["scan"]["base_stop"] == 40
    assert len({item["variant_id"] for item in variants}) == 8
    assert {(item["interface"], item["shift"]) for item in variants} == {
        (interface, shift)
        for interface in (0, 1)
        for shift in (-2, -1, 1, 2)
    }
    for variant in variants:
        assert [item["base"] for item in variant["results"]] == list(
            range(18, 41)
        )
        assert all(
            item["status"]
            in {
                "infeasible_at_n_zero",
                "infeasible_at_interpolation",
                "verified_realization",
            }
            for item in variant["results"]
        )
        assert all(len(item["dimacs_digest"]) == 64 for item in variant["results"])
    n_zero_survivors = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] != "infeasible_at_n_zero"
    ]
    verified = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] == "verified_realization"
    ]
    assert evidence["scan"]["n_zero_survivors"] == n_zero_survivors
    assert evidence["scan"]["verified_realizations"] == verified
    assert evidence["independent_audit"]["kind"] == (
        "independent_binary_interface_audit"
    )
    assert evidence["independent_audit"]["instances_tested"] == 184
    assert evidence["independent_audit"]["status_agreement"] is True
    assert evidence["independent_audit"]["encodings_distinct"] is True
    assert evidence["independent_audit"]["satisfiable_instances"] == (
        n_zero_survivors
    )
    assert evidence["prism"] == {
        "model": "qwen3.6:27b-mlx",
        "applications": [
            {
                "id": "application:0fe7f4314d3eb2e146848f308b389f631b506529af1e23cefa3f12d6f8e6934d",
                "status": "invalid",
            },
            {
                "id": "application:a18fe26dad217803b98d9302f2ee61ea287f099c4b65ab1716cf92c00396bc21",
                "status": "invalid",
            },
            {
                "id": "application:ea5b80592f8dea1b92191ee186cdab0be1a7eced1b3081fac976ab1e2bdbc9d4",
                "status": "invalid",
            },
        ],
        "artifacts": [],
    }


def test_standalone_binary_audit_classifies_every_relevant_instance() -> None:
    runs = Path(__file__).resolve().parents[1] / "runs"
    audit_script = runs / "t25_lychrel_interface_perturbations_independent.py"
    binary_encoder = runs / "t24_lychrel_arbitrary_topology_independent.py"
    source = runs / "t21_lychrel_multi_interface.json"

    with tempfile.TemporaryDirectory() as directory:
        isolated = Path(directory)
        for path in (audit_script, binary_encoder, source):
            shutil.copy2(path, isolated / path.name)
        completed = subprocess.run(
            [sys.executable, "-I", str(isolated / audit_script.name)],
            check=True,
            capture_output=True,
            text=True,
            timeout=3600,
        )
    audit = json.loads(completed.stdout)

    assert audit["kind"] == "independent_binary_interface_audit"
    assert audit["implementation"] == (
        "JSON-only interface movement plus standalone binary full adders"
    )
    assert audit["solver"] == {"engine": "CaDiCaL", "version": "3.0.1"}
    assert audit["variants_tested"] == 8
    assert audit["instances_tested"] == 184
    assert len(audit["variants"]) == 8
    assert {(item["interface"], item["shift"]) for item in audit["variants"]} == {
        (interface, shift)
        for interface in (0, 1)
        for shift in (-2, -1, 1, 2)
    }
    for variant in audit["variants"]:
        assert [item["base"] for item in variant["results"]] == list(
            range(18, 41)
        )
        assert {item["status"] for item in variant["results"]} <= {
            "satisfiable",
            "unsatisfiable",
        }
        assert all(len(item["dimacs_digest"]) == 64 for item in variant["results"])
    assert len(audit["unsatisfiable_instances"]) + len(
        audit["satisfiable_instances"]
    ) == 184
