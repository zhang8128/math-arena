from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

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
