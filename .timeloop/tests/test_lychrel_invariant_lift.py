from __future__ import annotations

import json
import shutil
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
from t27_base19_invariant_lift import (  # noqa: E402
    EvidenceError,
    canonicalize_state,
    load_promoted_inputs,
    reproduce_structural_baseline,
    state_table_payload,
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


def test_promoted_base19_inputs_have_frozen_identity() -> None:
    equations, frontier = load_promoted_inputs(ROOT)

    assert equations.content_sha256 == (
        "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"
    )
    assert frontier.content_sha256 == (
        "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"
    )
    assert frontier.provenances_sha256 == (
        "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"
    )
    assert frontier.removed == "phase=0,n=0,column=82"
    assert len(equations.equations) == 409
    assert len(frontier.layers) == 35
    assert tuple(layer.number for layer in frontier.layers) == tuple(range(-1, 34))
    assert tuple(
        frontier.layers_by_number[layer].output_state_count
        for layer in range(25, 34)
    ) == (20, 12, 12, 17, 16, 18, 18, 22, 0)


def test_canonical_state_orders_phase_carries_before_digits() -> None:
    layer = load_promoted_inputs(ROOT)[1].layers_by_number[32]
    state = canonicalize_state(layer, "output", layer.output_states[0])

    assert list(state)[:4] == ["L0", "R0", "L1", "R1"]
    assert list(state)[-2:] == ["D0", "D1"]
    assert tuple(state.values()) == layer.output_states[0]


def _copy_promoted_inputs(tmp_path: Path) -> Path:
    destination = tmp_path / "repo" / "publication" / "base19-radial"
    (destination / "instance").mkdir(parents=True)
    (destination / "certificates").mkdir()
    shutil.copy(
        ROOT / "publication/base19-radial/instance/equations.json",
        destination / "instance/equations.json",
    )
    shutil.copy(
        ROOT / "publication/base19-radial/certificates/minimal-core-frontier.json",
        destination / "certificates/minimal-core-frontier.json",
    )
    return tmp_path / "repo"


def test_promoted_loader_rejects_a_changed_source_digest(tmp_path: Path) -> None:
    root = _copy_promoted_inputs(tmp_path)
    path = root / "publication/base19-radial/instance/equations.json"
    payload = json.loads(path.read_text())
    payload["content_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidenceError, match="content digest"):
        load_promoted_inputs(root)


def test_promoted_loader_rejects_a_frontier_state_width_mismatch(
    tmp_path: Path,
) -> None:
    root = _copy_promoted_inputs(tmp_path)
    path = root / "publication/base19-radial/certificates/minimal-core-frontier.json"
    payload = json.loads(path.read_text())
    payload["layers"][0]["output_states"][0].append(0)
    unsigned = dict(payload)
    unsigned.pop("content_sha256")
    payload["content_sha256"] = __import__("hashlib").sha256(
        (json.dumps(unsigned, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidenceError, match="digest"):
        load_promoted_inputs(root)


def test_structural_baseline_reproduces_pair_and_terminal_facts() -> None:
    baseline = reproduce_structural_baseline(load_promoted_inputs(ROOT))

    assert baseline["pair_count"] == 203
    assert baseline["boundary_provenances"] == [
        "phase=5,n=0,column=0",
        "phase=5,n=0,column=83",
    ]
    assert [item["base"] for item in baseline["difference_relaxation"]] == list(
        range(17, 41)
    )
    assert {
        item["status"] for item in baseline["difference_relaxation"]
    } == {"SAT"}
    assert len(baseline["terminal_deletions"]) == 12
    assert min(
        item["surviving_state_count"] for item in baseline["terminal_deletions"]
    ) >= 2


def test_state_table_payload_has_only_canonical_mathematical_content() -> None:
    frontier = load_promoted_inputs(ROOT)[1]
    payload = state_table_payload(
        tuple(frontier.layers_by_number[layer] for layer in range(25, 33))
    )

    assert set(payload) == {"layers"}
    assert [item["layer"] for item in payload["layers"]] == list(range(25, 33))
    assert set(payload["layers"][0]) == {"layer", "variables", "states"}
    assert len(payload["layers"][0]["states"]) == 20
