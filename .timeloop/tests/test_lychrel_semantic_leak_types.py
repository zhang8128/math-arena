from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from lychrel_semantic_leak_types import (  # noqa: E402
    LeakType,
    LeakTypeFamily,
    SemanticLeakTypesCertificate,
    StructuralLiteral,
    TypeDiversityRecord,
    evaluate_leak_family,
    evaluate_leak_type,
    generate_literal_pool,
    parse_semantic_leak_types_certificate,
)
from t32_base19_semantic_leak_types import (  # noqa: E402
    T31_SOURCE_DIGESTS,
    EvidenceError,
    failure_mask,
    load_t32_inputs,
    q0_residuals,
    structural_view,
)


def digest_entries(names: set[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((name, hashlib.sha256(name.encode()).hexdigest()) for name in names)
    )


def structural_assignment() -> dict[str, int]:
    result: dict[str, int] = {}
    digits = ((0, 0), (1, 1), (1, 1), (2, 2), (4, 4), (9, 9))
    lin = (0, 0, 0, 0, 1, 0)
    rin = (0, 0, 0, 0, 0, 1)
    lout = (0, 0, 0, 0, 0, 0)
    rout = (0, 0, 0, 0, 1, 1)
    for phase, (a_value, b_value) in enumerate(digits):
        result[f"a{phase}"] = a_value
        result[f"b{phase}"] = b_value
        result[f"Lin{phase}"] = lin[phase]
        result[f"Rin{phase}"] = rin[phase]
        result[f"Lout{phase}"] = lout[phase]
        result[f"Rout{phase}"] = rout[phase]
    return result


def witness_fixture(offset: int = 0) -> SemanticWitness:
    return SemanticWitness(
        input_state=(("input:D0", 1 + offset), ("input:L0", 0)),
        output_state=(("output:D0", 0), ("output:D1", offset)),
        local_state=(("local:z", offset),),
    )


def certificate_fixture() -> SemanticLeakTypesCertificate:
    tau = LeakType(
        (
            StructuralLiteral(0, "digit_order", "eq"),
            StructuralLiteral(5, "digit_sum", "eq18"),
        )
    )
    family = LeakTypeFamily((tau,))
    first = witness_fixture(0)
    second = witness_fixture(1)
    diversity = TypeDiversityRecord(
        0,
        (first, second),
        ((True, True, False, True, True), (False, True, True, False, True)),
    )
    return SemanticLeakTypesCertificate(
        schema="t32-base19-semantic-leak-types-certificate-v1",
        status="SEMANTIC_LEAK_TYPES_PASS",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=digest_entries(
            {
                "equations",
                "frontier",
                "provenances",
                "t27_evidence",
                "t28_evidence",
                "t28_independent",
            }
        ),
        t29_artifact_digests=digest_entries(
            {"evidence", "trace", "dataset", "certificate", "independent"}
        ),
        t30_artifact_digests=digest_entries(
            {"evidence", "certificate", "independent", "report"}
        ),
        t31_source_digests=digest_entries({"library", "runner", "test"}),
        t31_commits=("69022cb", "adc6986", "619b737", "6835036"),
        design_sha256=hashlib.sha256(b"design").hexdigest(),
        family=family,
        milestone_witnesses=(first, second),
        type_soundness=("UNSAT",),
        exhaustiveness_status="UNSAT",
        diversity=(diversity,),
        discovery_witness_count=7,
        tested_candidate_count=19,
        enumerated_input_count=77_824,
        bad_input_count=21_477,
        family_bytes=200,
        bad_input_table_bytes=500_000,
    )


def test_literal_pool_is_the_frozen_84_literal_language() -> None:
    pool = generate_literal_pool()
    assert len(pool) == len(set(pool)) == 84
    assert pool == tuple(sorted(pool, key=canonical_bytes))
    assert {literal.phase for literal in pool} == set(range(6))
    assert {literal.kind for literal in pool} == {
        "digit_order",
        "digit_sum",
        "input_carry_pair",
        "output_carry_pair",
        "left_carry_flow",
        "right_carry_flow",
    }


def test_structural_literal_rejects_nonstructural_relations() -> None:
    with pytest.raises(ValueError, match="phase"):
        StructuralLiteral(6, "digit_order", "eq")
    with pytest.raises(ValueError, match="kind"):
        StructuralLiteral(0, "q0_failure", "eq")
    with pytest.raises(ValueError, match="relation"):
        StructuralLiteral(0, "digit_order", "value_0")


def test_type_and_family_limits_are_strict() -> None:
    pool = generate_literal_pool()
    with pytest.raises(ValueError, match="six literals"):
        LeakType(pool[:7])
    one = LeakType((pool[0],))
    with pytest.raises(ValueError, match="eight types"):
        LeakTypeFamily(tuple(one for _ in range(9)))


def test_type_canonicalizes_literals_and_rejects_duplicates() -> None:
    pool = generate_literal_pool()
    tau = LeakType((pool[10], pool[2]))
    assert tau.literals == (pool[2], pool[10])
    with pytest.raises(ValueError, match="repeat"):
        LeakType((pool[0], pool[0]))


def test_structural_evaluation_covers_all_six_literal_kinds() -> None:
    assignment = structural_assignment()
    tau = LeakType(
        (
            StructuralLiteral(0, "digit_order", "eq"),
            StructuralLiteral(5, "digit_sum", "eq18"),
            StructuralLiteral(4, "input_carry_pair", "ne"),
            StructuralLiteral(4, "output_carry_pair", "ne"),
            StructuralLiteral(4, "left_carry_flow", "ne"),
            StructuralLiteral(5, "right_carry_flow", "eq"),
        )
    )
    assert evaluate_leak_type(tau, assignment)
    assert evaluate_leak_family(LeakTypeFamily((tau,)), assignment) == 0
    assert not evaluate_leak_type(
        LeakType((StructuralLiteral(5, "digit_sum", "ge19"),)), assignment
    )


def test_structural_evaluation_requires_exact_keys_and_domains() -> None:
    assignment = structural_assignment()
    tau = LeakType((StructuralLiteral(0, "digit_order", "eq"),))
    missing = dict(assignment)
    missing.pop("a0")
    with pytest.raises(ValueError, match="keys differ"):
        evaluate_leak_type(tau, missing)
    bad_carry = dict(assignment)
    bad_carry["Lin0"] = 2
    with pytest.raises(ValueError, match="carry"):
        evaluate_leak_type(tau, bad_carry)


def test_diversity_requires_two_inputs_and_two_failure_masks() -> None:
    first = witness_fixture(0)
    second = witness_fixture(1)
    mask = (True, True, False, True, True)
    with pytest.raises(ValueError, match="inputs"):
        TypeDiversityRecord(0, (first, first), (mask, mask))
    with pytest.raises(ValueError, match="failure masks"):
        TypeDiversityRecord(0, (first, second), (mask, mask))


def test_certificate_round_trips_exactly() -> None:
    certificate = certificate_fixture()
    parsed = parse_semantic_leak_types_certificate(certificate.to_payload())
    assert parsed == certificate
    assert parsed.to_payload() == certificate.to_payload()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("status", "SEMANTIC_LEAK_TYPES_STOP", "status"),
        ("exhaustiveness_status", "SAT", "exhaustiveness"),
        ("enumerated_input_count", 77_823, "77,824"),
        ("family_bytes", 500_000, "smaller"),
        ("bad_input_count", True, "bad-input"),
    ),
)
def test_certificate_rejects_mutated_pass_claims(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(certificate_fixture(), **{field: value})


def test_certificate_parser_rejects_extra_keys() -> None:
    payload = certificate_fixture().to_payload()
    payload["unexpected"] = 1
    with pytest.raises(ValueError, match="keys differ"):
        parse_semantic_leak_types_certificate(payload)


def test_t32_adapter_replays_the_complete_t31_stop_boundary() -> None:
    inputs = load_t32_inputs(ROOT)
    assert inputs.t31_status == "NO_CANDIDATE"
    assert inputs.t31_projected_atom_count == 26
    assert inputs.t31_stop_detail == (
        "no projected atom excludes the first exact bad image"
    )
    assert inputs.t31_replay_residuals == (0,) * 12
    assert inputs.t31_q0_holds is False
    assert q0_residuals(inputs, inputs.t31_witness) == (1, -1, 0, -3, -10)
    assert failure_mask(inputs, inputs.t31_witness) == (
        True,
        True,
        False,
        True,
        True,
    )
    assert dict(inputs.t31_source_digests) == T31_SOURCE_DIGESTS


def test_canonical_t31_witness_has_the_expected_structural_view() -> None:
    inputs = load_t32_inputs(ROOT)
    view = structural_view(inputs, inputs.t31_witness)
    assert tuple(view[f"a{i}"] for i in range(6)) == (0, 1, 1, 2, 4, 9)
    assert tuple(view[f"b{i}"] for i in range(6)) == (0, 0, 1, 2, 4, 9)
    assert tuple(view[f"Lin{i}"] for i in range(6)) == (0, 0, 0, 0, 1, 0)
    assert tuple(view[f"Rin{i}"] for i in range(6)) == (0, 0, 0, 0, 0, 1)
    assert tuple(view[f"Lout{i}"] for i in range(6)) == (0, 0, 0, 0, 0, 0)
    assert tuple(view[f"Rout{i}"] for i in range(6)) == (0, 0, 0, 0, 1, 1)


def test_t32_adapter_rejects_a_mutated_t31_source(tmp_path: Path) -> None:
    changed = tmp_path / "t31.py"
    changed.write_bytes(
        (ROOT / ".timeloop/runs/t31_base19_bad_image_projection.py").read_bytes()
        + b"\n"
    )
    with pytest.raises(EvidenceError, match="T31 runner raw SHA-256 changed"):
        load_t32_inputs(ROOT, t31_runner_path=changed)
