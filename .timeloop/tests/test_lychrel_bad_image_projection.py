from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))

from lychrel_bad_image_projection import (  # noqa: E402
    BadImageProjectionCertificate,
    Layer30Predicate,
    ProjectionAtom,
    ProjectionClause,
    ProjectionOrigin,
    compactness_bytes,
    evaluate_p30,
    parse_bad_image_projection_certificate,
)
from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402

P30_VARIABLES = (
    "L0",
    "R0",
    "L1",
    "R1",
    "L2",
    "R2",
    "L3",
    "R3",
    "L4",
    "R4",
    "L5",
    "R5",
    "D0",
)
SOURCE_NAMES = {
    "equations",
    "frontier",
    "provenances",
    "t27_evidence",
    "t28_evidence",
    "t28_independent",
}
T29_NAMES = {"evidence", "trace", "dataset", "certificate", "independent"}
T30_NAMES = {"evidence", "certificate", "independent", "report"}


def digest_entries(names: set[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((name, hashlib.sha256(name.encode()).hexdigest()) for name in names)
    )


def p30_fixture() -> Layer30Predicate:
    return Layer30Predicate(
        30,
        P30_VARIABLES,
        (ProjectionClause((ProjectionAtom("eq", (("L0", 1),), 0),)),),
    )


def certificate_fixture() -> BadImageProjectionCertificate:
    p30 = p30_fixture()
    atom = p30.clauses[0].atoms[0]
    return BadImageProjectionCertificate(
        schema="t31-base19-bad-image-projection-certificate-v1",
        status="BAD_IMAGE_PROJECTION_PASS",
        stop_reason=None,
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=digest_entries(SOURCE_NAMES),
        t29_artifact_digests=digest_entries(T29_NAMES),
        t30_artifact_digests=digest_entries(T30_NAMES),
        p30=p30,
        projection_origins=(
            ProjectionOrigin(
                atom_sha256=hashlib.sha256(canonical_bytes(atom.to_payload())).hexdigest(),
                failed_q0_equation=0,
                qe_formula_sha256="a" * 64,
                expression_path=(0,),
                polarity="direct",
            ),
        ),
        promoted_count=18,
        promoted_sha256="b" * 64,
        predicate_bytes=100,
        state_table_bytes=200,
        counterexample_count=1,
        implication_status="UNSAT",
        implication_equation_count=12,
        composed_status="UNSAT",
        composed_equation_count=24,
        failure_witness=None,
    )


def complete_witness() -> SemanticWitness:
    return SemanticWitness(
        input_state=tuple(
            sorted((f"input:{name}", 0) for name in P30_VARIABLES)
        ),
        output_state=tuple(
            sorted(
                (f"output:{name}", 0)
                for name in (
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
            )
        ),
        local_state=(),
    )


def test_projection_atom_normalizes_equalities_canonically() -> None:
    atom = ProjectionAtom("eq", (("R0", 2), ("L0", -2)), -4)
    assert atom.terms == (("L0", 1), ("R0", -1))
    assert atom.constant == 2


def test_projection_atom_enforces_t31_coefficient_and_modulus_bounds() -> None:
    atom = ProjectionAtom("le", (("D0", 9), ("L0", -9)), 18)
    assert atom.terms == (("D0", 1), ("L0", -1))
    assert atom.constant == 2
    with pytest.raises(ValueError, match="coefficient"):
        ProjectionAtom("le", (("D0", 10),), 18)
    with pytest.raises(ValueError, match="modulus"):
        ProjectionAtom("congruent", (("D0", 1),), 0, 20)


def test_projection_atom_rejects_zero_duplicate_and_oversized_support() -> None:
    with pytest.raises(ValueError, match="zero coefficient"):
        ProjectionAtom("eq", (("L0", 0),), 0)
    with pytest.raises(ValueError, match="duplicate variable"):
        ProjectionAtom("eq", (("L0", 1), ("L0", -1)), 0)
    with pytest.raises(ValueError, match="support"):
        ProjectionAtom(
            "eq",
            tuple((f"X{index}", 1) for index in range(14)),
            0,
        )


def test_projection_clause_rejects_more_than_six_atoms_and_duplicates() -> None:
    with pytest.raises(ValueError, match="six atoms"):
        ProjectionClause(
            tuple(
                ProjectionAtom("eq", (("D0", 1),), constant)
                for constant in range(7)
            )
        )
    atom = ProjectionAtom("eq", (("L0", 1),), 0)
    with pytest.raises(ValueError, match="repeat"):
        ProjectionClause((atom, atom))


def test_layer30_predicate_enforces_scope_and_clause_budget() -> None:
    clauses = tuple(
        ProjectionClause((ProjectionAtom("eq", (("D0", 1),), constant),))
        for constant in range(3)
    )
    with pytest.raises(ValueError, match="two clauses"):
        Layer30Predicate(30, P30_VARIABLES, clauses)
    with pytest.raises(ValueError, match="outside predicate scope"):
        Layer30Predicate(
            30,
            P30_VARIABLES,
            (ProjectionClause((ProjectionAtom("eq", (("X", 1),), 0),)),),
        )


def test_evaluate_p30_handles_disjunction_and_congruence() -> None:
    predicate = Layer30Predicate(
        30,
        P30_VARIABLES,
        (
            ProjectionClause((ProjectionAtom("eq", (("L0", 1),), 1),)),
            ProjectionClause(
                (ProjectionAtom("congruent", (("D0", 1),), 2, 3),)
            ),
        ),
    )
    zero = {name: 0 for name in P30_VARIABLES}
    assert evaluate_p30(predicate, zero) is False
    assert evaluate_p30(predicate, zero | {"L0": 1}) is True
    assert evaluate_p30(predicate, zero | {"D0": 5}) is True


def test_compactness_bytes_uses_the_exact_state_table_payload() -> None:
    predicate = p30_fixture()
    rows = (tuple(0 for _ in P30_VARIABLES), tuple(1 for _ in P30_VARIABLES))
    predicate_size, table_size = compactness_bytes(predicate, rows)
    expected_table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(row) for row in rows],
    }
    assert predicate_size == len(canonical_bytes(predicate.to_payload()))
    assert table_size == len(canonical_bytes(expected_table))


def test_t31_certificate_round_trips_strictly() -> None:
    certificate = certificate_fixture()
    assert parse_bad_image_projection_certificate(certificate.to_payload()) == certificate
    payload = certificate.to_payload()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="certificate keys differ"):
        parse_bad_image_projection_certificate(payload)


def test_certificate_rejects_wrong_digest_names_and_duplicate_origins() -> None:
    certificate = certificate_fixture()
    with pytest.raises(ValueError, match="source digest names"):
        replace(certificate, source_digests=digest_entries({"equations"}))
    with pytest.raises(ValueError, match="projection origins"):
        replace(
            certificate,
            projection_origins=certificate.projection_origins * 2,
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"promoted_count": 17}, "18 promoted"),
        ({"predicate_bytes": 200}, "strict compression"),
        ({"counterexample_count": 65}, "counterexample"),
        ({"implication_equation_count": 11}, "12 implication"),
        ({"composed_equation_count": 23}, "24 composed"),
        ({"implication_status": "SAT"}, "PASS statuses"),
        ({"composed_status": "NOT_RUN"}, "PASS statuses"),
    ],
)
def test_pass_certificate_requires_every_exact_gate(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(certificate_fixture(), **changes)


def test_stop_certificate_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="stop reason"):
        replace(
            certificate_fixture(),
            status="BAD_IMAGE_PROJECTION_STOP",
        )


def test_sat_status_requires_witness_and_unsat_forbids_it() -> None:
    certificate = certificate_fixture()
    stopped = replace(
        certificate,
        status="BAD_IMAGE_PROJECTION_STOP",
        stop_reason="image_counterexample",
        implication_status="SAT",
        composed_status="NOT_RUN",
        failure_witness=complete_witness(),
    )
    assert stopped.failure_witness is not None
    with pytest.raises(ValueError, match="SAT requires a witness"):
        replace(stopped, failure_witness=None)
    with pytest.raises(ValueError, match="only SAT carries a witness"):
        replace(
            stopped,
            implication_status="UNSAT",
            failure_witness=complete_witness(),
        )
