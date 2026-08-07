from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_arbitrary_topology import (  # noqa: E402
    CNFFormula,
    ColumnConstraint,
    DigitAtom,
    assignment_satisfies,
    build_column_constraints,
    compile_one_hot_cnf,
    decode_digit_assignment,
    materialize_cycle,
    reference_assignment,
    render_arbitrary,
)
from lychrel_wordproof import ParametricWord, verify_cycle  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


def test_renderer_maps_repeats_but_not_fixed_occurrences() -> None:
    word = ParametricWord(17, ((3,), (4,), (5,)), (0, 16))

    rendered = render_arbitrary((word,), 0, 1, 20)

    assert rendered == (
        DigitAtom("p0:f0:d0"),
        DigitAtom(None, 0),
        DigitAtom("p0:f1:d0"),
        DigitAtom(None, 19),
        DigitAtom("p0:f2:d0"),
    )


def test_column_constraint_is_hand_derived() -> None:
    words = (
        ParametricWord(17, ((3, 5),), ()),
        ParametricWord(17, ((8, 8),), ()),
    )

    constraints = build_column_constraints(
        words,
        20,
        parameters=(0,),
        phases=(0,),
    )

    assert constraints[0] == ColumnConstraint(
        left=DigitAtom("p0:f0:d0"),
        right=DigitAtom("p0:f0:d1"),
        target=DigitAtom("p1:f0:d1"),
        carry_in=None,
        carry_out="c:p0:n0:col0",
        provenance="phase=0,n=0,column=0",
    )


def test_wrap_transition_targets_the_incremented_parameter() -> None:
    words = (
        ParametricWord(17, ((1,), (2,)), (0,)),
        ParametricWord(17, ((3,), (4,)), (16,)),
    )

    constraints = build_column_constraints(
        words,
        20,
        parameters=(0,),
        phases=(1,),
    )

    assert len(constraints) == 3
    assert constraints[1].target == DigitAtom(None, 0)


def test_compiler_rejects_invalid_base_phase_and_parameter() -> None:
    words = (ParametricWord(17, ((1,),), ()),)

    for kwargs in (
        {"base": 16},
        {"base": 17, "parameters": (-1,)},
        {"base": 17, "phases": (1,)},
    ):
        try:
            build_column_constraints(words, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {kwargs}")


def test_one_hot_cnf_has_literal_domains_and_transition_implication() -> None:
    words = (
        ParametricWord(2, ((1, 1),), ()),
        ParametricWord(2, ((1, 1),), ()),
    )

    formula = compile_one_hot_cnf(words, 2, parameters=(0,))

    p0_zero = formula.variable_ids["digit:p0:f0:d0:value0"]
    p0_one = formula.variable_ids["digit:p0:f0:d0:value1"]
    p0_right_one = formula.variable_ids["digit:p0:f0:d1:value1"]
    p1_zero = formula.variable_ids["digit:p1:f0:d1:value0"]
    carry = formula.variable_ids["c:p0:n0:col0"]
    assert formula.clauses[:2] == (
        (p0_zero, p0_one),
        (-p0_zero, -p0_one),
    )
    assert (-p0_one, -p0_right_one, p1_zero) in formula.clauses
    assert (-p0_one, -p0_right_one, carry) in formula.clauses
    assert formula.dimacs_bytes().startswith(
        f"p cnf {formula.variable_count} {formula.clause_count}\n".encode()
    )
    assert len(formula.digest) == 64
    assert formula.digest == compile_one_hot_cnf(
        words, 2, parameters=(0,)
    ).digest


@lru_cache(maxsize=1)
def reference_cycle() -> tuple[ParametricWord, ...]:
    return base17_reference_cycle()


def test_t21_n_zero_system_has_expected_size_and_reference_model() -> None:
    words = reference_cycle()

    constraints = build_column_constraints(words, 17, parameters=(0,))
    formula = compile_one_hot_cnf(words, 17, parameters=(0,))
    assignment = reference_assignment(words, formula)

    assert sum(len(fragment) for word in words for fragment in word.fragments) == 497
    assert len(constraints) == 499
    assert assignment_satisfies(formula, assignment)


def test_reference_model_decodes_and_materializes_the_control_cycle() -> None:
    words = reference_cycle()
    formula = compile_one_hot_cnf(words, 17, parameters=(0,))
    assignment = reference_assignment(words, formula)
    model = tuple(
        None if index == 0 else assignment[formula.semantic_keys[index - 1]]
        for index in range(formula.variable_count + 1)
    )

    digits = decode_digit_assignment(formula, model)
    cycle = materialize_cycle(words, 17, digits)

    assert cycle == words
    assert verify_cycle(cycle)


def test_assignment_checker_rejects_missing_and_false_models() -> None:
    formula = CNFFormula(
        base=2,
        parameters=(0,),
        clauses=((1,),),
        semantic_keys=("x",),
        digit_keys=(),
    )

    assert not assignment_satisfies(formula, {})
    assert not assignment_satisfies(formula, {"x": False})
    assert assignment_satisfies(formula, {"x": True})


def test_primary_evidence_scans_every_base() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "runs"
        / "t24_lychrel_arbitrary_topology.py"
    )

    completed = subprocess.run(
        ["/usr/local/bin/sage", "-python", str(script)],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    evidence = json.loads(completed.stdout)

    assert evidence["kind"] == "arbitrary_digit_topology_classification"
    assert evidence["status"] == "no_n_zero_realizations"
    assert evidence["reference"] == {
        "base": 17,
        "fixed_occurrences": 497,
        "integer_replays": 54,
        "n_zero_columns": 499,
        "one_hot_assignment_verified": True,
        "polynomial_verified": True,
    }
    assert evidence["scan"]["base_start"] == 18
    assert evidence["scan"]["base_stop"] == 40
    assert evidence["scan"]["tested"] == 23
    assert evidence["scan"]["hits"] == []
    assert [item["base"] for item in evidence["scan"]["results"]] == list(
        range(18, 41)
    )
    assert {item["status"] for item in evidence["scan"]["results"]} == {
        "infeasible_at_n_zero"
    }
    assert {tuple(item["parameters_checked"]) for item in evidence["scan"]["results"]} == {
        (0,)
    }
    base18 = evidence["scan"]["results"][0]
    assert base18["variable_count"] == 9439
    assert base18["clause_count"] == 715404
    assert len(base18["dimacs_digest"]) == 64
    assert evidence["solver"]["engine"] == "PicoSAT via pycosat"
    assert evidence["independent_audit"]["implementation"] == (
        "standalone binary digit encoding"
    )
    assert evidence["independent_audit"]["solver"] == {
        "engine": "CaDiCaL",
        "version": "3.0.1",
    }
    assert evidence["independent_audit"]["all_unsatisfiable"] is True
    assert evidence["independent_audit"]["covered_bases"] == list(range(18, 41))
    assert evidence["independent_audit"]["status_agreement"] is True
    assert evidence["prism"]["model"] == "qwen3.6:27b-mlx"
    assert evidence["prism"]["artifacts"] == [
        "99415b8fc2a52e62f541c03b93712c1bae61f39ac0d3a61fdf898409c92687ce",
        "8a9c0b6e3bb8539cf2aa022edaeba1508a09281bc562c382f57d4b738758e90c",
    ]


def test_standalone_binary_audit() -> None:
    runs = Path(__file__).resolve().parents[1] / "runs"
    script = runs / "t24_lychrel_arbitrary_topology_independent.py"
    source = runs / "t21_lychrel_multi_interface.json"

    with tempfile.TemporaryDirectory() as directory:
        isolated = Path(directory)
        shutil.copy2(script, isolated / script.name)
        shutil.copy2(source, isolated / source.name)
        completed = subprocess.run(
            [sys.executable, "-I", str(isolated / script.name)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    audit = json.loads(completed.stdout)
    primary = json.loads(
        (runs / "t24_lychrel_arbitrary_topology.json").read_text()
    )

    assert audit["kind"] == "independent_binary_topology_audit"
    assert audit["implementation"] == "standalone binary digit encoding"
    assert audit["solver"] == {"engine": "CaDiCaL", "version": "3.0.1"}
    assert audit["bases_tested"] == 23
    assert audit["covered_bases"] == list(range(18, 41))
    assert {item["status"] for item in audit["results"]} == {"unsatisfiable"}
    assert {item["parameters_checked"] for item in audit["results"]} == {0}
    assert audit["all_unsatisfiable"] is True
    assert audit["results"][0]["dimacs_digest"] != primary["scan"]["results"][0][
        "dimacs_digest"
    ]
