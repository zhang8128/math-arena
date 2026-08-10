from __future__ import annotations

import ast
import hashlib
import importlib.util
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEPENDENT = (
    ROOT / ".timeloop/runs/t32_base19_semantic_leak_types_independent.py"
)
EQUATIONS = ROOT / "publication/base19-radial/instance/equations.json"
FRONTIER = ROOT / "publication/base19-radial/certificates/minimal-core-frontier.json"
T27_EVIDENCE = ROOT / ".timeloop/runs/t27_base19_invariant_lift.json"
T28_EVIDENCE = ROOT / ".timeloop/runs/t28_base19_tail_quotient.json"
T28_INDEPENDENT = ROOT / ".timeloop/runs/t28_base19_tail_quotient_independent.json"
T29_TRACE = ROOT / ".timeloop/runs/t29_base19_reachability_separator_trace.json"
T29_DATASET = ROOT / ".timeloop/runs/t29_base19_reachability_separator_dataset.json"
T29_EVIDENCE = ROOT / ".timeloop/runs/t29_base19_reachability_separator.json"
T29_CERTIFICATE = (
    ROOT / ".timeloop/runs/t29_base19_reachability_separator_certificate.json"
)
T29_INDEPENDENT = (
    ROOT / ".timeloop/runs/t29_base19_reachability_separator_independent.json"
)
T30_EVIDENCE = ROOT / ".timeloop/runs/t30_base19_exact_image_refinement.json"
T30_CERTIFICATE = (
    ROOT / ".timeloop/runs/t30_base19_exact_image_refinement_certificate.json"
)
T30_INDEPENDENT = (
    ROOT / ".timeloop/runs/t30_base19_exact_image_refinement_independent.json"
)
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
    find_first_leak_type,
    load_t32_inputs,
    q0_residuals,
    structural_view,
    synthesize_leak_family,
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


def load_independent_module() -> object:
    spec = importlib.util.spec_from_file_location("t32_independent_test", INDEPENDENT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_independent_checker_starts_under_isolated_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "milestone" in completed.stdout
    assert "full" in completed.stdout


def test_independent_checker_has_only_standard_library_imports() -> None:
    tree = ast.parse(INDEPENDENT.read_text(encoding="utf-8"))
    roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert roots <= {
        "__future__",
        "argparse",
        "hashlib",
        "itertools",
        "json",
        "re",
        "sys",
        "dataclasses",
        "pathlib",
    }


def test_independent_constraint_search_handles_literal_target_both_ways() -> None:
    module = load_independent_module()
    equation = {
        "left": {"variable": "p0:f0:d1"},
        "right": {"literal": 18},
        "target": {"variable": "p0:f0:d2"},
        "carry_in": None,
        "carry_out": "c:p0:n0:col1",
    }
    domains = {
        "digit:p0:f0:d1": set(range(19)),
        "digit:p0:f0:d2": set(range(19)),
        "c:p0:n0:col1": {0, 1},
    }
    constraint = module.allowed_equation_tuples(equation, domains, 19)
    assert module.first_solution(domains, (constraint,)) == (
        ("c:p0:n0:col1", 0),
        ("digit:p0:f0:d1", 0),
        ("digit:p0:f0:d2", 18),
    )
    reverse = {name: set(values) for name, values in domains.items()}
    reverse["digit:p0:f0:d2"] = {0}
    assert module.first_solution(reverse, (constraint,)) == (
        ("c:p0:n0:col1", 1),
        ("digit:p0:f0:d1", 1),
        ("digit:p0:f0:d2", 0),
    )


def test_independent_structural_literals_cover_all_six_kinds() -> None:
    module = load_independent_module()
    assignment = structural_assignment()
    literals = (
        {"phase": 0, "kind": "digit_order", "relation": "eq"},
        {"phase": 5, "kind": "digit_sum", "relation": "eq18"},
        {"phase": 4, "kind": "input_carry_pair", "relation": "ne"},
        {"phase": 4, "kind": "output_carry_pair", "relation": "ne"},
        {"phase": 4, "kind": "left_carry_flow", "relation": "ne"},
        {"phase": 5, "kind": "right_carry_flow", "relation": "eq"},
    )
    assert all(
        module.structural_literal_holds(literal, assignment)
        for literal in literals
    )


def run_independent_milestone(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(INDEPENDENT),
            "milestone",
            str(EQUATIONS),
            str(FRONTIER),
            str(T27_EVIDENCE),
            str(T28_EVIDENCE),
            str(T28_INDEPENDENT),
            str(T29_TRACE),
            str(T29_DATASET),
            str(T29_EVIDENCE),
            str(T29_CERTIFICATE),
            str(T29_INDEPENDENT),
            str(T30_EVIDENCE),
            str(T30_CERTIFICATE),
            str(T30_INDEPENDENT),
            str(path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_independent_milestone_rejects_a_q0_countermodel(tmp_path: Path) -> None:
    inputs = load_t32_inputs(ROOT)
    dummy_witness = {"input_state": {}, "output_state": {}, "local_state": {}}
    milestone = {
        "schema": "t32-base19-semantic-leak-type-milestone-v1",
        "leak_type": {
            "literals": [
                {"phase": 0, "kind": "input_carry_pair", "relation": "eq"}
            ]
        },
        "witnesses": [dummy_witness, dummy_witness],
        "failure_masks": [
            [True, False, False, False, False],
            [False, True, False, False, False],
        ],
        "source_digests": dict(inputs.source_digests),
        "t29_artifact_digests": dict(inputs.t29_artifact_digests),
        "t30_artifact_digests": dict(inputs.t30_artifact_digests),
        "t31_source_digests": dict(inputs.t31_source_digests),
        "t31_commits": list(inputs.t31_commits),
        "design_sha256": inputs.design_sha256,
    }
    path = tmp_path / "milestone.json"
    path.write_bytes(canonical_bytes(milestone) + b"\n")
    completed = run_independent_milestone(path)
    assert completed.returncode != 0
    assert "type soundness counterexample" in completed.stderr


def test_repository_first_type_reaches_pass_or_exact_stop() -> None:
    result = find_first_leak_type(load_t32_inputs(ROOT))
    assert result.status in {
        "PASS",
        "NO_SOUND_TYPE",
        "NO_DIVERSE_TYPE",
        "WITNESS_BUDGET_EXHAUSTED",
        "CANDIDATE_BUDGET_EXHAUSTED",
        "INDEPENDENT_DISAGREEMENT",
    }
    assert 1 <= result.inspected_witness_count <= 128
    assert 0 <= result.tested_candidate_count <= 2_000
    if result.status == "PASS":
        assert result.leak_type is not None
        assert len(result.leak_type.literals) <= 6
        assert len(result.witnesses) == 2
        assert result.failure_masks[0] != result.failure_masks[1]
        assert result.soundness_status == "UNSAT"
        assert result.independent_status == "PASS"
    else:
        assert result.leak_type is None
        assert result.stop_detail


def test_first_type_search_is_byte_deterministic() -> None:
    inputs = load_t32_inputs(ROOT)
    assert canonical_bytes(find_first_leak_type(inputs).to_payload()) == (
        canonical_bytes(find_first_leak_type(inputs).to_payload())
    )


def test_first_type_search_enforces_exact_budget_bounds() -> None:
    inputs = load_t32_inputs(ROOT)
    with pytest.raises(ValueError, match="witness limit"):
        find_first_leak_type(inputs, witness_limit=0)
    with pytest.raises(ValueError, match="candidate limit"):
        find_first_leak_type(inputs, candidate_limit=2_001)


def test_repository_family_reaches_pass_or_exact_stop() -> None:
    inputs = load_t32_inputs(ROOT)
    milestone = find_first_leak_type(inputs)
    assert milestone.status == "PASS"
    result = synthesize_leak_family(inputs, milestone)
    assert result.status in {
        "PASS",
        "NO_SOUND_TYPE",
        "NO_DIVERSE_TYPE",
        "TYPE_LIMIT_EXCEEDED",
        "WITNESS_BUDGET_EXHAUSTED",
        "CANDIDATE_BUDGET_EXHAUSTED",
        "UNKNOWN",
    }
    assert result.inspected_witness_count <= 256
    assert result.tested_candidate_count <= 10_000
    if result.status == "PASS":
        assert result.family is not None
        assert 1 <= len(result.family.types) <= 8
        assert result.exhaustiveness_status == "UNSAT"
        assert result.type_soundness == ("UNSAT",) * len(result.family.types)
        assert len(result.diversity) == len(result.family.types)
    else:
        assert result.stop_detail


def test_family_search_is_byte_deterministic() -> None:
    inputs = load_t32_inputs(ROOT)
    milestone = find_first_leak_type(inputs)
    first = synthesize_leak_family(inputs, milestone)
    second = synthesize_leak_family(inputs, milestone)
    assert canonical_bytes(first.to_payload()) == canonical_bytes(second.to_payload())
