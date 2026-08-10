from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEPENDENT = (
    ROOT
    / ".timeloop"
    / "runs"
    / "t30_base19_exact_image_refinement_independent.py"
)
EQUATIONS = ROOT / "publication/base19-radial/instance/equations.json"
FRONTIER = (
    ROOT / "publication/base19-radial/certificates/minimal-core-frontier.json"
)
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
T30_REPORT = ROOT / ".timeloop/runs/t30_base19_exact_image_refinement_report.md"

sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_exact_image_refinement import (  # noqa: E402
    ExactImageRefinementCertificate,
    PredecessorImageObligation,
    parse_exact_image_refinement_certificate,
)
from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    LayerPredicate,
    LinearAtom,
    canonical_bytes,
)
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from t30_base19_exact_image_refinement import (  # noqa: E402
    T29_ARTIFACT_DIGESTS,
    EvidenceError,
    FiniteBoundaryCheck,
    RefinedSemanticCheck,
    build_q0,
    build_t30_primary,
    check_finite_boundary,
    check_predecessor_implication,
    check_refined_semantics,
    decide_t30_gate,
    load_t30_inputs,
    render_t30_report,
)

VARIABLES = (
    "D0",
    "D1",
    "L0",
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "R0",
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
)


def q0_fixture() -> LayerPredicate:
    return LayerPredicate(
        layer=31,
        variables=VARIABLES,
        clauses=(
            Conjunction(
                (
                    LinearAtom(
                        "eq",
                        (("L1", 1), ("L4", -1), ("L5", 1), ("R4", -1)),
                        0,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("L1", 1),
                            ("L2", -2),
                            ("L4", -2),
                            ("L5", -2),
                            ("R1", -3),
                            ("R2", 3),
                            ("R3", 2),
                            ("R4", 1),
                        ),
                        0,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("L0", 3),
                            ("L1", 1),
                            ("L2", 2),
                            ("L5", -2),
                            ("R1", -3),
                            ("R3", 1),
                        ),
                        3,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("D1", 1),
                            ("L0", 3),
                            ("L1", -2),
                            ("L2", -3),
                            ("L3", 1),
                            ("L4", 1),
                            ("R0", -1),
                            ("R1", -3),
                            ("R2", -3),
                            ("R3", 3),
                            ("R4", -1),
                        ),
                        9,
                    ),
                    LinearAtom(
                        "eq",
                        (
                            ("D0", 1),
                            ("D1", -1),
                            ("L0", -1),
                            ("R0", 1),
                            ("R5", 1),
                        ),
                        1,
                    ),
                )
            ),
        ),
    )


def obligation_fixture(index: int) -> PredecessorImageObligation:
    return PredecessorImageObligation(
        predecessor_index=index,
        predecessor_sha256=hashlib.sha256(f"predecessor-{index}".encode()).hexdigest(),
        exact_model_count=1,
        output_count=1,
        output_sha256=hashlib.sha256(f"outputs-{index}".encode()).hexdigest(),
        q0_violation_status="UNSAT",
    )


def certificate_fixture() -> ExactImageRefinementCertificate:
    return ExactImageRefinementCertificate(
        schema="t30-base19-exact-image-refinement-certificate-v1",
        status="EXACT_IMAGE_REFINEMENT_PASS",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=(
            ("equations", "a" * 64),
            ("frontier", "b" * 64),
            ("provenances", "c" * 64),
            ("t27_evidence", "d" * 64),
            ("t28_evidence", "e" * 64),
            ("t28_independent", "f" * 64),
        ),
        t29_artifact_digests=(
            ("certificate", "1" * 64),
            ("dataset", "2" * 64),
            ("evidence", "3" * 64),
            ("independent", "4" * 64),
            ("trace", "5" * 64),
        ),
        q0=q0_fixture(),
        predecessor_obligations=tuple(obligation_fixture(i) for i in range(18)),
        implication_status="UNSAT",
        finite_status="PASS",
        semantic_status="UNSAT",
        implication_witness=None,
        semantic_witness=None,
    )


def test_predecessor_obligation_requires_canonical_identity() -> None:
    obligation = PredecessorImageObligation(
        predecessor_index=0,
        predecessor_sha256="a" * 64,
        exact_model_count=0,
        output_count=0,
        output_sha256=hashlib.sha256(canonical_bytes([])).hexdigest(),
        q0_violation_status="UNSAT",
    )
    assert obligation.to_payload()["predecessor_index"] == 0
    with pytest.raises(ValueError, match="predecessor index"):
        replace(obligation, predecessor_index=-1)
    with pytest.raises(ValueError, match="q0 violation status"):
        replace(obligation, q0_violation_status="UNKNOWN")


def test_exact_image_certificate_round_trips_strictly() -> None:
    certificate = certificate_fixture()
    assert parse_exact_image_refinement_certificate(
        certificate.to_payload()
    ) == certificate
    mutated = certificate.to_payload()
    mutated["unexpected"] = True
    with pytest.raises(ValueError, match="certificate keys differ"):
        parse_exact_image_refinement_certificate(mutated)


@pytest.mark.parametrize("field", ["predecessor_sha256", "output_sha256"])
def test_predecessor_obligation_rejects_malformed_digests(field: str) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        replace(obligation_fixture(0), **{field: "A" * 64})


def test_certificate_rejects_skipped_predecessor_index() -> None:
    certificate = certificate_fixture()
    obligations = list(certificate.predecessor_obligations)
    obligations[-1] = replace(obligations[-1], predecessor_index=19)
    with pytest.raises(ValueError, match="consecutive"):
        replace(certificate, predecessor_obligations=tuple(obligations))


def test_certificate_rejects_noncanonical_digest_maps() -> None:
    certificate = certificate_fixture()
    with pytest.raises(ValueError, match="source digest names differ"):
        replace(certificate, source_digests=tuple(reversed(certificate.source_digests)))


@pytest.mark.parametrize("atom_count", [4, 6])
def test_certificate_requires_exactly_five_q0_atoms(atom_count: int) -> None:
    certificate = certificate_fixture()
    atoms = certificate.q0.clauses[0].atoms
    if atom_count == 4:
        replacement = atoms[:4]
    else:
        replacement = (*atoms, LinearAtom("eq", (("D0", 1),), 0))
    q0 = LayerPredicate(31, VARIABLES, (Conjunction(tuple(replacement)),))
    with pytest.raises(ValueError, match="exactly five"):
        replace(certificate, q0=q0)


def test_certificate_rejects_multiple_q0_clauses() -> None:
    certificate = certificate_fixture()
    q0 = LayerPredicate(
        31,
        VARIABLES,
        (*certificate.q0.clauses, Conjunction((LinearAtom("eq", (("D0", 1),), 0),))),
    )
    with pytest.raises(ValueError, match="one conjunction"):
        replace(certificate, q0=q0)


def test_certificate_rejects_q0_inequality() -> None:
    certificate = certificate_fixture()
    atoms = list(certificate.q0.clauses[0].atoms)
    atom = atoms[0]
    atoms[0] = LinearAtom("le", atom.terms, atom.constant)
    q0 = LayerPredicate(31, VARIABLES, (Conjunction(tuple(atoms)),))
    with pytest.raises(ValueError, match="equalities"):
        replace(certificate, q0=q0)


def test_certificate_requires_witness_exactly_for_semantic_sat() -> None:
    certificate = certificate_fixture()
    with pytest.raises(ValueError, match="semantic SAT requires a witness"):
        replace(
            certificate,
            status="EXACT_IMAGE_REFINEMENT_STOP",
            semantic_status="SAT",
        )
    witness = SemanticWitness(
        input_state=(("x", 1),),
        output_state=(("y", 2),),
        local_state=(),
    )
    with pytest.raises(ValueError, match="only semantic SAT carries a witness"):
        replace(certificate, semantic_witness=witness)


def test_pass_requires_exactly_eighteen_obligations() -> None:
    certificate = certificate_fixture()
    with pytest.raises(ValueError, match="18 predecessor obligations"):
        replace(
            certificate,
            predecessor_obligations=certificate.predecessor_obligations[:-1],
        )


def test_q0_is_the_exact_five_atom_closed_grammar_candidate() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    atoms = q0.clauses[0].atoms
    assert q0.layer == 31
    assert len(q0.clauses) == 1
    assert len(atoms) == 5
    assert {atom.relation for atom in atoms} == {"eq"}
    assert max(abs(c) for atom in atoms for _, c in atom.terms) == 3
    assert max(len(atom.terms) for atom in atoms) == 11
    assert sum(len(atom.terms) for atom in atoms) == 34
    assert q0 == q0_fixture()


def test_t30_adapter_binds_the_complete_t29_boundary() -> None:
    inputs = load_t30_inputs(ROOT)
    assert len(inputs.dataset.positives) == 12
    assert len(inputs.dataset.trace_negatives) == 221
    assert len(inputs.dataset.live_controls) == 6
    assert dict(inputs.t29_artifact_digests) == T29_ARTIFACT_DIGESTS
    assert dict(inputs.t29_leak) == {
        "D0": 5,
        "D1": 6,
        "L0": 0,
        "L1": 1,
        "L2": 1,
        "L3": 0,
        "L4": 1,
        "L5": 1,
        "R0": 0,
        "R1": 0,
        "R2": 1,
        "R3": 0,
        "R4": 0,
        "R5": 1,
    }


@pytest.mark.parametrize(
    ("override", "relative_path"),
    [
        ("evidence_path", ".timeloop/runs/t29_base19_reachability_separator.json"),
        (
            "trace_path",
            ".timeloop/runs/t29_base19_reachability_separator_trace.json",
        ),
        (
            "dataset_path",
            ".timeloop/runs/t29_base19_reachability_separator_dataset.json",
        ),
        (
            "certificate_path",
            ".timeloop/runs/t29_base19_reachability_separator_certificate.json",
        ),
        (
            "independent_path",
            ".timeloop/runs/t29_base19_reachability_separator_independent.json",
        ),
    ],
)
def test_t30_adapter_rejects_each_raw_t29_mutation(
    tmp_path: Path,
    override: str,
    relative_path: str,
) -> None:
    payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    payload["mutation"] = True
    mutated = tmp_path / Path(relative_path).name
    mutated.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvidenceError, match="raw SHA-256"):
        load_t30_inputs(ROOT, **{override: mutated})


def test_real_predecessor_image_implies_q0_exactly() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_predecessor_implication(inputs, build_q0(inputs.variables))
    assert result.status == "UNSAT"
    assert result.witness is None
    assert len(result.obligations) == 18
    assert [item.exact_model_count for item in result.obligations] == [
        0,
        0,
        0,
        0,
        0,
        4,
        0,
        0,
        0,
        0,
        0,
        0,
        4,
        4,
        0,
        4,
        2,
        0,
    ]
    assert sum(item.output_count for item in result.obligations) == 18
    assert sum(item.output_count > 0 for item in result.obligations) == 5
    assert {item.q0_violation_status for item in result.obligations} == {"UNSAT"}


def test_mutated_q0_returns_a_complete_implication_witness() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    atoms = list(q0.clauses[0].atoms)
    atom = next(
        item
        for item in atoms
        if {name for name, _ in item.terms} == {"D0", "D1", "L0", "R0", "R5"}
    )
    atoms[atoms.index(atom)] = LinearAtom(
        atom.relation, atom.terms, atom.constant + 1
    )
    mutated = LayerPredicate(31, q0.variables, (Conjunction(tuple(atoms)),))
    result = check_predecessor_implication(inputs, mutated)
    assert result.status == "SAT"
    assert result.witness is not None
    assert len(result.witness.input_state) == 13
    assert len(result.witness.output_state) == 14
    assert result.obligations[-1].q0_violation_status == "SAT"


def test_predecessor_implication_is_byte_deterministic() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    assert check_predecessor_implication(inputs, q0) == check_predecessor_implication(
        inputs, q0
    )


def test_real_q0_passes_the_frozen_finite_boundary() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_finite_boundary(inputs, build_q0(inputs.variables))
    assert result.status == "PASS"
    assert result.q0_positive_count == 12
    assert result.q0_trace_accepted == 0
    assert result.q0_live_count == 6
    assert result.q0_leak_holds is False
    assert result.combined_failures == ()


def test_real_refined_successor_query_is_unsat() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_refined_semantics(inputs, build_q0(inputs.variables))
    assert result.status == "UNSAT"
    assert result.equation_count == 12
    assert result.witness is None


def test_two_equation_semantic_control_returns_complete_witness() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    control = LayerPredicate(
        31,
        q0.variables,
        (Conjunction(q0.clauses[0].atoms[:2]),),
    )
    result = check_refined_semantics(inputs, control)
    assert result.status == "SAT"
    assert result.witness is not None
    assert len(result.witness.input_state) == 14
    assert len(result.witness.output_state) == 14


def test_gate_pass_keeps_s29_and_q0_separate() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    implication = check_predecessor_implication(inputs, q0)
    finite = check_finite_boundary(inputs, q0)
    semantic = check_refined_semantics(inputs, q0)
    evidence, certificate = decide_t30_gate(
        inputs, implication, finite, semantic
    )
    assert evidence["status"] == "EXACT_IMAGE_REFINEMENT_PASS"
    assert certificate is not None
    assert certificate.q0 == q0
    assert "s29" not in certificate.to_payload()
    assert dict(certificate.t29_artifact_digests)["certificate"] == (
        T29_ARTIFACT_DIGESTS["certificate"]
    )


def test_gate_stops_at_the_first_failed_stage() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    implication = check_predecessor_implication(inputs, q0)
    finite = check_finite_boundary(inputs, q0)
    semantic = check_refined_semantics(inputs, q0)

    failed_finite = FiniteBoundaryCheck(
        "STOP",
        finite.q0_positive_count - 1,
        finite.q0_trace_accepted,
        finite.q0_live_count,
        finite.q0_leak_holds,
        (("positive", inputs.dataset.positives[0]),),
    )
    evidence, certificate = decide_t30_gate(
        inputs, implication, failed_finite, semantic
    )
    assert evidence["stop_reason"] == "finite_boundary_failure"
    assert certificate is not None
    assert certificate.semantic_status == "NOT_RUN"

    failed_semantic = RefinedSemanticCheck(
        "SAT",
        semantic.equation_count,
        check_refined_semantics(
            inputs,
            LayerPredicate(31, q0.variables, (Conjunction(q0.clauses[0].atoms[:2]),)),
        ).witness,
    )
    evidence, certificate = decide_t30_gate(
        inputs, implication, finite, failed_semantic
    )
    assert evidence["stop_reason"] == "semantic_successor_found"
    assert certificate is not None
    assert certificate.semantic_status == "SAT"


def test_primary_builder_and_report_state_the_bounded_claim() -> None:
    evidence, certificate = build_t30_primary(ROOT)
    assert evidence["status"] == "EXACT_IMAGE_REFINEMENT_PASS"
    assert certificate is not None
    report = render_t30_report(evidence)
    assert "promoted layer-30 frontier" in report
    assert "EXACT_IMAGE_REFINEMENT_PASS" in report
    assert all(line == line.rstrip() for line in report.splitlines())


def test_primary_cli_preserves_predecessor_obligation_order(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".timeloop/runs/t30_base19_exact_image_refinement.py"),
            "--evidence",
            str(evidence),
            "--certificate",
            str(tmp_path / "certificate.json"),
            "--report",
            str(tmp_path / "report.md"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert [
        item["predecessor_index"]
        for item in payload["implication"]["predecessor_obligations"]
    ] == list(range(18))


def write_primary_fixture(tmp_path: Path) -> tuple[Path, Path]:
    evidence = tmp_path / "evidence.json"
    certificate = tmp_path / "certificate.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".timeloop/runs/t30_base19_exact_image_refinement.py"),
            "--evidence",
            str(evidence),
            "--certificate",
            str(certificate),
            "--report",
            str(tmp_path / "report.md"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return evidence, certificate


def independent_command(*, evidence: Path, certificate: Path) -> list[str]:
    return [
        sys.executable,
        "-I",
        str(INDEPENDENT),
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
        str(evidence),
        str(certificate),
    ]


def test_independent_checker_starts_under_isolated_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "T30_CERTIFICATE" in completed.stdout


def test_independent_checker_accepts_primary_temporary_artifacts(
    tmp_path: Path,
) -> None:
    evidence, certificate = write_primary_fixture(tmp_path)
    completed = subprocess.run(
        independent_command(evidence=evidence, certificate=certificate),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    audit = json.loads(completed.stdout)
    assert audit["status"] == "EXACT_IMAGE_REFINEMENT_PASS"
    assert audit["repository_imports"] == []
    assert audit["predecessor_obligation_count"] == 18
    assert audit["successor_bearing_predecessor_count"] == 5
    assert audit["exact_model_count"] == 18
    assert audit["semantic_status"] == "UNSAT"


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("evidence", "q0"),
        ("evidence", "obligation"),
        ("certificate", "q0"),
        ("certificate", "obligation"),
        ("certificate", "semantic_status"),
    ],
)
def test_independent_checker_rejects_t30_mutations(
    tmp_path: Path,
    target: str,
    mutation: str,
) -> None:
    evidence, certificate = write_primary_fixture(tmp_path)
    path = evidence if target == "evidence" else certificate
    payload = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "q0":
        payload["q0"]["clauses"][0]["atoms"][0]["constant"] += 1
    elif mutation == "obligation":
        container = payload["implication"] if target == "evidence" else payload
        container["predecessor_obligations"][0]["exact_model_count"] += 1
    else:
        payload["semantic_status"] = "SAT"
    path.write_text(json.dumps(payload), encoding="utf-8")
    completed = subprocess.run(
        independent_command(evidence=evidence, certificate=certificate),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert completed.stderr.startswith("REJECT:")


def run_primary_cli(directory: Path) -> tuple[Path, Path, Path]:
    directory.mkdir(parents=True)
    evidence = directory / "evidence.json"
    certificate = directory / "certificate.json"
    report = directory / "report.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".timeloop/runs/t30_base19_exact_image_refinement.py"),
            "--evidence",
            str(evidence),
            "--certificate",
            str(certificate),
            "--report",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return evidence, certificate, report


def run_independent_cli(
    primary: tuple[Path, Path, Path], output: Path
) -> Path:
    completed = subprocess.run(
        independent_command(evidence=primary[0], certificate=primary[1]),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    output.write_text(completed.stdout, encoding="utf-8")
    return output


def test_primary_and_independent_cli_are_byte_deterministic(
    tmp_path: Path,
) -> None:
    first = run_primary_cli(tmp_path / "first")
    second = run_primary_cli(tmp_path / "second")
    assert first[0].read_bytes() == second[0].read_bytes()
    assert first[1].read_bytes() == second[1].read_bytes()
    assert first[2].read_bytes() == second[2].read_bytes()
    audit_one = run_independent_cli(first, tmp_path / "audit-one.json")
    audit_two = run_independent_cli(second, tmp_path / "audit-two.json")
    assert audit_one.read_bytes() == audit_two.read_bytes()


def test_durable_t30_artifacts_are_bound_and_parseable() -> None:
    for path in (T30_EVIDENCE, T30_CERTIFICATE, T30_INDEPENDENT, T30_REPORT):
        assert path.is_file()
    evidence = json.loads(T30_EVIDENCE.read_text(encoding="utf-8"))
    certificate = parse_exact_image_refinement_certificate(
        json.loads(T30_CERTIFICATE.read_text(encoding="utf-8"))
    )
    audit = json.loads(T30_INDEPENDENT.read_text(encoding="utf-8"))
    assert evidence["status"] == "EXACT_IMAGE_REFINEMENT_PASS"
    assert certificate.status == "EXACT_IMAGE_REFINEMENT_PASS"
    assert audit["primary_evidence_sha256"] == hashlib.sha256(
        T30_EVIDENCE.read_bytes()
    ).hexdigest()
    assert audit["certificate_file_sha256"] == hashlib.sha256(
        T30_CERTIFICATE.read_bytes()
    ).hexdigest()
