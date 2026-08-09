from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    LayerPredicate,
    LinearAtom,
    canonical_bytes,
    compression_record,
    evaluate_predicate,
    parse_certificate,
)


def test_linear_congruence_and_carry_literal_evaluation() -> None:
    assignment = {"c0": 1, "c1": 0, "d": 7}
    predicate = LayerPredicate(
        layer=25,
        variables=("c0", "c1", "d"),
        clauses=(
            Conjunction(
                (
                    LinearAtom("eq", (("c0", 1), ("c1", -1)), 1),
                    LinearAtom("le", (("d", 1),), 8),
                    LinearAtom(
                        "congruent",
                        (("d", 1), ("c0", 1)),
                        0,
                        modulus=4,
                    ),
                )
            ),
        ),
    )

    assert evaluate_predicate(predicate, assignment)
    assert not evaluate_predicate(predicate, {"c0": 0, "c1": 0, "d": 7})


def test_canonical_bytes_fix_key_and_semantic_sequence_order() -> None:
    left = {"b": 2, "a": [{"terms": [["y", -1], ["x", 1]]}]}
    right = {"a": [{"terms": [["x", 1], ["y", -1]]}], "b": 2}

    assert canonical_bytes(left) == canonical_bytes(right)
    assert canonical_bytes(left) == b'{"a":[{"terms":[["x",1],["y",-1]]}],"b":2}'


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"relation": "eq", "terms": (("x", 0),), "constant": 0}, "zero"),
        (
            {"relation": "eq", "terms": (("x", 4),), "constant": 0},
            "coefficient",
        ),
        (
            {
                "relation": "congruent",
                "terms": (("x", 1),),
                "constant": 0,
                "modulus": 1,
            },
            "modulus",
        ),
        (
            {
                "relation": "congruent",
                "terms": (("x", 1),),
                "constant": 0,
                "modulus": 21,
            },
            "modulus",
        ),
    ),
)
def test_linear_atom_rejects_values_outside_the_closed_grammar(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LinearAtom(**kwargs)


def test_predicate_rejects_oversized_boolean_structure() -> None:
    atoms = tuple(LinearAtom("eq", ((f"x{i}", 1),), 0) for i in range(13))
    with pytest.raises(ValueError, match="12 atoms"):
        Conjunction(atoms)

    clause = Conjunction((LinearAtom("eq", (("x", 1),), 0),))
    with pytest.raises(ValueError, match="three clauses"):
        LayerPredicate(0, ("x",), (clause, clause, clause, clause))


def test_evaluator_rejects_missing_assignments() -> None:
    predicate = LayerPredicate(
        0,
        ("x",),
        (Conjunction((LinearAtom("eq", (("x", 1),), 0),)),),
    )

    with pytest.raises(ValueError, match="missing assignment"):
        evaluate_predicate(predicate, {})


@pytest.mark.parametrize(
    ("atom", "message"),
    (
        (
            {
                "relation": "eq",
                "terms": [["x", 1], ["x", -1]],
                "constant": 0,
            },
            "duplicate variable",
        ),
        (
            {
                "relation": "congruent",
                "terms": [["x", 1]],
                "constant": 5,
                "modulus": 4,
            },
            "canonical residue",
        ),
    ),
)
def test_certificate_parser_rejects_noncanonical_atoms(
    atom: dict[str, object],
    message: str,
) -> None:
    payload = {
        "schema": "t27-invariant-certificate-v1",
        "base": 19,
        "removed": "phase=0,n=0,column=82",
        "source_digests": {"equations": "a" * 64, "frontier": "b" * 64},
        "predicates": [
            {
                "layer": 0,
                "variables": ["x"],
                "clauses": [{"atoms": [atom]}],
            }
        ],
        "obligations": [],
    }

    with pytest.raises(ValueError, match=message):
        parse_certificate(payload)


def test_compression_record_uses_exact_integer_byte_comparison() -> None:
    certificate = {"certificate": "x"}
    state_payload = {"states": [list(range(300)) for _ in range(10)]}

    result = compression_record(certificate, state_payload)

    assert result["certificate_bytes"] == len(canonical_bytes(certificate))
    assert result["state_table_bytes"] == len(canonical_bytes(state_payload))
    assert result["compression_numerator"] == result["state_table_bytes"]
    assert result["compression_denominator"] == result["certificate_bytes"]
    assert result["at_least_tenfold"] is True
    json.dumps(result, allow_nan=False)
