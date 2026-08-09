from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    InvariantCertificate,
    LayerPredicate,
    LinearAtom,
    canonical_bytes,
    compression_record,
    evaluate_predicate,
    parse_certificate,
)
from t27_base19_invariant_lift import (  # noqa: E402
    Atom,
    CegisLayer,
    CertificateCheckResult,
    Equation,
    EquationManifest,
    EvidenceError,
    FrontierCertificate,
    FrontierLayer,
    FrontierTransition,
    GrammarLimits,
    ObligationResult,
    PBRow,
    build_gate_a,
    canonicalize_state,
    check_certificate,
    check_exclusion,
    check_initiation,
    decide_gate_a,
    derive_cut_candidates,
    enumerate_atoms,
    load_promoted_inputs,
    reproduce_structural_baseline,
    separate_counterexample,
    state_table_payload,
    synthesize_cegis,
    synthesize_late_certificate,
    synthesize_terminal_predicate,
)


def _atom_value(atom: LinearAtom, state: dict[str, int]) -> bool:
    predicate = LayerPredicate(
        0,
        tuple(state),
        (Conjunction((atom,)),),
    )
    return evaluate_predicate(predicate, state)


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


def _three_layer_obligation_fixture() -> tuple[
    tuple[EquationManifest, FrontierCertificate],
    InvariantCertificate,
]:
    transfer = Equation(
        provenance="phase=0,n=0,column=1",
        left=Atom(variable="p0:f1:d0"),
        right=Atom(literal=1),
        target=Atom(variable="p0:f1:d1"),
        carry_in=None,
        carry_out=None,
    )
    terminal = Equation(
        provenance="phase=0,n=0,column=2",
        left=Atom(variable="p0:f1:d1"),
        right=Atom(literal=0),
        target=Atom(literal=7),
        carry_in=None,
        carry_out=None,
    )
    manifest = EquationManifest(
        content_sha256="a" * 64,
        file_sha256="b" * 64,
        topology_sha256="c" * 64,
        base=19,
        equations=(transfer, terminal),
        fragment_lengths=((1, 2, 1),),
    )
    layers = (
        FrontierLayer(
            number=0,
            equation_provenances=(),
            input_variables=(),
            output_variables=("digit:p0:f1:d0",),
            input_state_count=1,
            output_state_count=1,
            local_model_count=1,
            output_states_sha256="",
            output_states=((6,),),
            transitions=(FrontierTransition((), ((6,),)),),
        ),
        FrontierLayer(
            number=1,
            equation_provenances=(transfer.provenance,),
            input_variables=("digit:p0:f1:d0",),
            output_variables=("digit:p0:f1:d1",),
            input_state_count=1,
            output_state_count=1,
            local_model_count=1,
            output_states_sha256="",
            output_states=((7,),),
            transitions=(FrontierTransition((6,), ((7,),)),),
        ),
        FrontierLayer(
            number=2,
            equation_provenances=(terminal.provenance,),
            input_variables=("digit:p0:f1:d1",),
            output_variables=(),
            input_state_count=1,
            output_state_count=1,
            local_model_count=1,
            output_states_sha256="",
            output_states=((),),
            transitions=(FrontierTransition((7,), ((),)),),
        ),
    )
    frontier = FrontierCertificate(
        content_sha256="d" * 64,
        equations_sha256=manifest.file_sha256,
        provenances_sha256="e" * 64,
        removed="fixture-removed",
        base=19,
        layers=layers,
    )
    certificate = InvariantCertificate(
        schema="t27-invariant-certificate-v1",
        base=19,
        removed="fixture-removed",
        source_digests=(
            ("equations", manifest.content_sha256),
            ("frontier", frontier.content_sha256),
        ),
        predicates=(
            LayerPredicate(
                0,
                ("D0",),
                (Conjunction((LinearAtom("eq", (("D0", 1),), 6),)),),
            ),
            LayerPredicate(
                1,
                ("D0",),
                (Conjunction((LinearAtom("le", (("D0", 1),), 6),)),),
            ),
        ),
        obligations=(),
    )
    return (manifest, frontier), certificate


def test_checker_reports_the_first_bad_transition() -> None:
    inputs, certificate = _three_layer_obligation_fixture()

    result = check_certificate(inputs, certificate)

    assert result.status == "FAIL"
    assert result.obligations[-1].kind == "consecution"
    assert result.obligations[-1].layer == 1
    assert result.obligations[-1].counterexample == {
        "input": {"D0": 6},
        "output": {"D0": 7},
    }


def test_initiation_reports_the_first_reachable_counterexample() -> None:
    (_, frontier), _ = _three_layer_obligation_fixture()
    predicate = LayerPredicate(
        0,
        ("D0",),
        (Conjunction((LinearAtom("eq", (("D0", 1),), 5),)),),
    )

    result = check_initiation(frontier.layers_by_number[0], predicate)

    assert result.status == "FAIL"
    assert result.counterexample == {"output": {"D0": 6}}
    assert result.checked_count == 1


def test_checker_reports_a_terminal_model_admitted_by_the_last_predicate() -> None:
    inputs, certificate = _three_layer_obligation_fixture()
    admitting = replace(
        certificate,
        predicates=(
            certificate.predicates[0],
            LayerPredicate(
                1,
                ("D0",),
                (Conjunction((LinearAtom("eq", (("D0", 1),), 7),)),),
            ),
        ),
    )

    result = check_certificate(inputs, admitting)

    assert result.status == "FAIL"
    assert result.obligations[-1].kind == "exclusion"
    assert result.obligations[-1].counterexample == {"input": {"D0": 7}}


def test_checker_accepts_a_complete_three_layer_certificate() -> None:
    (manifest, frontier), certificate = _three_layer_obligation_fixture()
    terminal = replace(manifest.equations[-1], target=Atom(literal=8))
    passing_manifest = replace(manifest, equations=(manifest.equations[0], terminal))
    passing = replace(
        certificate,
        predicates=(
            certificate.predicates[0],
            LayerPredicate(
                1,
                ("D0",),
                (Conjunction((LinearAtom("eq", (("D0", 1),), 7),)),),
            ),
        ),
    )

    result = check_certificate((passing_manifest, frontier), passing)

    assert result.status == "PASS"
    assert [obligation.kind for obligation in result.obligations] == [
        "initiation",
        "consecution",
        "exclusion",
    ]
    assert all(obligation.status == "PASS" for obligation in result.obligations)


def test_atom_enumerator_respects_the_closed_grammar() -> None:
    atoms = tuple(
        enumerate_atoms(
            states=({"L0": 0, "R0": 1, "D0": 5},),
            variables=("L0", "R0", "D0"),
            limits=GrammarLimits(),
        )
    )

    assert atoms == tuple(sorted(set(atoms), key=canonical_bytes))
    assert atoms
    assert all(max(abs(coefficient) for _, coefficient in atom.terms) <= 3 for atom in atoms)
    assert all(atom.modulus is None or 2 <= atom.modulus <= 20 for atom in atoms)


def test_pb_elimination_derives_a_shared_frontier_equality() -> None:
    rows = (
        PBRow("eq", (("L0", 1), ("x", 1), ("D0", -1)), 0, source="left"),
        PBRow("eq", (("R0", 1), ("x", -1)), 0, source="right"),
    )

    candidates = derive_cut_candidates(
        rows,
        shared_variables=("L0", "R0", "D0"),
        limits=GrammarLimits(),
    )

    expected = LinearAtom(
        "eq",
        (("L0", 1), ("R0", 1), ("D0", -1)),
        0,
    )
    candidate = next(item for item in candidates if item.atom == expected)
    assert candidate.route == "pb_elimination"
    assert candidate.parent_sources == ("left", "right")
    assert candidate.multipliers == (1, 1)


def test_state_cegis_discovers_a_single_shared_equality() -> None:
    variables = ("L0", "R0", "D0")
    positives = (
        {"L0": 0, "R0": 0, "D0": 0},
        {"L0": 0, "R0": 1, "D0": 1},
        {"L0": 1, "R0": 0, "D0": 1},
        {"L0": 1, "R0": 1, "D0": 2},
    )
    bad_states = tuple(
        {"L0": left, "R0": right, "D0": digit}
        for left in range(2)
        for right in range(2)
        for digit in range(3)
        if left + right != digit
    )

    candidates = synthesize_cegis(
        (CegisLayer(variables, positives, bad_states),),
        GrammarLimits(),
    )

    expected = LinearAtom(
        "eq",
        (("L0", 1), ("R0", 1), ("D0", -1)),
        0,
    )
    candidate = next(item for item in candidates if item.atom == expected)
    assert candidate.route == "state_cegis"
    assert candidate.parent_sources == ("layer:0:complete-positive-and-bad-states",)


def test_solver_guided_separator_does_not_expand_the_closed_grammar() -> None:
    variables = ("L0", "R0", "L1", "R1", "L2", "R2", "D0")
    positives = (
        {"L0": 0, "R0": 0, "L1": 0, "R1": 0, "L2": 0, "R2": 0, "D0": 0},
        {"L0": 0, "R0": 1, "L1": 1, "R1": 0, "L2": 1, "R2": 0, "D0": 1},
        {"L0": 1, "R0": 0, "L1": 0, "R1": 1, "L2": 0, "R2": 1, "D0": 1},
    )
    bad = {"L0": 0, "R0": 0, "L1": 0, "R1": 0, "L2": 0, "R2": 0, "D0": 1}

    candidate = separate_counterexample(positives, bad, variables, GrammarLimits())

    assert candidate is not None
    assert candidate.route == "state_cegis"
    assert all(_atom_value(candidate.atom, state) for state in positives)
    assert not _atom_value(candidate.atom, bad)
    assert max(abs(coefficient) for _, coefficient in candidate.atom.terms) <= 3


def test_terminal_family_predicate_covers_and_excludes_exactly() -> None:
    inputs = load_promoted_inputs(ROOT)
    manifest, frontier = inputs

    predicate = synthesize_terminal_predicate(inputs, GrammarLimits())

    assert predicate.layer == 32
    assert len(predicate.clauses) == 3
    assert sorted(len(clause.atoms) for clause in predicate.clauses) == [10, 11, 11]
    assert check_initiation(frontier.layers_by_number[32], predicate).status == "PASS"
    assert check_exclusion(manifest, frontier, predicate).status == "PASS"
    assert any(
        atom.relation == "congruent" and atom.modulus == 19
        for clause in predicate.clauses
        for atom in clause.atoms
    )


def test_late_synthesis_stops_without_claiming_grammar_impossibility() -> None:
    result = synthesize_late_certificate(load_promoted_inputs(ROOT))

    assert result.status == "STOP"
    assert result.stop_reason == "backward_extension_layer_31_not_found"
    assert result.candidate is not None and result.candidate.layer == 32
    assert [obligation.status for obligation in result.checked_obligations] == [
        "PASS",
        "PASS",
    ]
    assert result.compression["at_least_tenfold"] is False
    assert "no_invariant_impossibility_claim" in result.route_provenance


def test_gate_a_stops_when_late_certificate_is_too_large() -> None:
    passing = CertificateCheckResult(
        "PASS",
        (ObligationResult("initiation", 25, "PASS", 20),),
    )

    result = decide_gate_a(
        milestone_check=passing,
        milestone_compression={"at_least_tenfold": False},
    )

    assert result == {
        "status": "STOP",
        "stop_reason": "late_certificate_below_tenfold_compression",
        "gate_b_authorized": False,
    }


def test_gate_a_never_authorizes_gate_b_after_an_obligation_failure() -> None:
    failing = CertificateCheckResult(
        "FAIL",
        (ObligationResult("consecution", 31, "FAIL", 1),),
    )

    result = decide_gate_a(
        milestone_check=failing,
        milestone_compression={"at_least_tenfold": True},
    )

    assert result["status"] == "STOP"
    assert result["stop_reason"] == "late_certificate_obligation_failure"
    assert result["gate_b_authorized"] is False


def test_real_gate_a_record_stops_before_symbolic_claims() -> None:
    record = build_gate_a(ROOT)

    assert record["status"] == "STOP"
    assert record["stop_reason"] == "backward_extension_layer_31_not_found"
    assert record["gate_b_authorized"] is False
    assert record["milestone"]["reachable_state_counts"] == [
        20,
        12,
        12,
        17,
        16,
        18,
        18,
        22,
    ]
    assert "symbolic_base_claim" not in record
    assert record["tail_lemma"]["obligation_status"] == "PASS"
