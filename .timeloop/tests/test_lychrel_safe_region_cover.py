from __future__ import annotations

import copy
import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_bad_image_projection import P30_VARIABLES, ProjectionAtom  # noqa: E402
from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_safe_region_cover import (  # noqa: E402
    CoreReductionStep,
    SafeRegionClause,
    SafeRegionCoverCertificate,
    SafeRegionPredicate,
    SafeRegionProvenance,
    SeedPair,
    bounded_layer30_rows,
    clause_extent,
    compactness_bytes,
    evaluate_safe_clause,
    evaluate_safe_predicate,
    first_match_ownership,
    generate_seed_pair_pool,
    parse_safe_region_cover_certificate,
)


def digest_entries(names: set[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((name, hashlib.sha256(name.encode()).hexdigest()) for name in names)
    )


def row_assignment(row: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(P30_VARIABLES, row, strict=True))


def test_t33_clause_rejects_t31_atoms_outside_the_small_grammar() -> None:
    with pytest.raises(ValueError, match="support"):
        SafeRegionClause(
            (
                ProjectionAtom(
                    "eq", (("L0", 1), ("R0", 1), ("L1", 1)), 0
                ),
            )
        )
    with pytest.raises(ValueError, match="coefficient"):
        SafeRegionClause((ProjectionAtom("le", (("D0", 4),), 17),))
    with pytest.raises(ValueError, match="scope"):
        SafeRegionClause((ProjectionAtom("eq", (("D1", 1),), 0),))


def test_safe_region_limits_and_canonical_order_are_strict() -> None:
    atoms = tuple(
        ProjectionAtom("le", (("D0", 1),), value) for value in range(6)
    )
    clause = SafeRegionClause(tuple(reversed(atoms)))
    assert clause.atoms == tuple(sorted(atoms, key=canonical_bytes))
    with pytest.raises(ValueError, match="six atoms"):
        SafeRegionClause(
            (*atoms, ProjectionAtom("eq", (("L0", 1),), 0))
        )
    clauses = tuple(
        SafeRegionClause((ProjectionAtom("eq", ((name, 1),), 0),))
        for name in P30_VARIABLES[:7]
    )
    with pytest.raises(ValueError, match="six clauses"):
        SafeRegionPredicate(30, P30_VARIABLES, clauses)


def test_safe_predicate_requires_layer_scope_and_distinct_clauses() -> None:
    clause = SafeRegionClause((ProjectionAtom("eq", (("L0", 1),), 0),))
    with pytest.raises(ValueError, match="layer 30"):
        SafeRegionPredicate(29, P30_VARIABLES, (clause,))
    with pytest.raises(ValueError, match="scope"):
        SafeRegionPredicate(30, tuple(reversed(P30_VARIABLES)), (clause,))
    with pytest.raises(ValueError, match="repeat"):
        SafeRegionPredicate(30, P30_VARIABLES, (clause, clause))


def test_safe_region_evaluation_covers_all_relations() -> None:
    assignment = {name: 0 for name in P30_VARIABLES}
    assignment["D0"] = 7
    clause = SafeRegionClause(
        (
            ProjectionAtom("eq", (("L0", 1), ("R0", -1)), 0),
            ProjectionAtom("le", (("D0", 1),), 7),
            ProjectionAtom("congruent", (("D0", 1),), 1, 3),
        )
    )
    predicate = SafeRegionPredicate(30, P30_VARIABLES, (clause,))
    assert evaluate_safe_clause(clause, assignment)
    assert evaluate_safe_predicate(predicate, assignment) == 0
    changed = dict(assignment)
    changed["D0"] = 8
    assert not evaluate_safe_clause(clause, changed)
    assert evaluate_safe_predicate(predicate, changed) is None


def test_safe_region_evaluation_requires_exact_keys_and_domains() -> None:
    clause = SafeRegionClause((ProjectionAtom("eq", (("L0", 1),), 0),))
    assignment = {name: 0 for name in P30_VARIABLES}
    missing = dict(assignment)
    missing.pop("L0")
    with pytest.raises(ValueError, match="keys differ"):
        evaluate_safe_clause(clause, missing)
    bad_carry = dict(assignment)
    bad_carry["R5"] = 2
    with pytest.raises(ValueError, match="carry"):
        evaluate_safe_clause(clause, bad_carry)
    bad_digit = dict(assignment)
    bad_digit["D0"] = 19
    with pytest.raises(ValueError, match="D0"):
        evaluate_safe_clause(clause, bad_digit)
    bool_digit = dict(assignment)
    bool_digit["D0"] = False
    with pytest.raises(ValueError, match="integer"):
        evaluate_safe_clause(clause, bool_digit)


def test_bounded_domain_has_exact_size_order_and_domains() -> None:
    rows = bounded_layer30_rows()
    assert len(rows) == len(set(rows)) == 77_824
    assert rows[0] == (0,) * 13
    assert rows[18] == (0,) * 12 + (18,)
    assert rows[19] == (0,) * 11 + (1, 0)
    assert rows[-1] == (1,) * 12 + (18,)


def test_extent_ownership_and_compactness_use_canonical_predicate_order() -> None:
    first = SafeRegionClause((ProjectionAtom("eq", (("L0", 1),), 0),))
    second = SafeRegionClause((ProjectionAtom("eq", (("R0", 1),), 0),))
    predicate = SafeRegionPredicate(30, P30_VARIABLES, (second, first))
    promoted = (
        (0,) * 13,
        (0, 1) + (0,) * 11,
        (1, 0) + (0,) * 11,
    )
    assert clause_extent(first) == 38_912
    assert first_match_ownership(predicate, promoted) == ((0, 1), (2,))
    predicate_bytes, table_bytes = compactness_bytes(predicate, promoted)
    assert predicate_bytes == len(canonical_bytes(predicate.to_payload()))
    assert table_bytes == len(
        canonical_bytes(
            {
                "layer": 30,
                "variables": list(P30_VARIABLES),
                "states": [list(row) for row in promoted],
            }
        )
    )


def test_seed_pair_pool_is_finite_canonical_and_seed_true() -> None:
    first = (0,) * 13
    second = (0,) * 12 + (1,)
    pool = generate_seed_pair_pool(first, second)
    assert pool
    assert pool == tuple(sorted(set(pool), key=canonical_bytes))
    for atom in pool:
        assert 1 <= len(atom.terms) <= 2
        assert all(abs(coefficient) <= 3 for _, coefficient in atom.terms)
        assert atom.modulus is None or 2 <= atom.modulus <= 19
        clause = SafeRegionClause((atom,))
        assert evaluate_safe_clause(clause, row_assignment(first))
        assert evaluate_safe_clause(clause, row_assignment(second))
        assert clause_extent(clause) < 77_824


def certificate_fixture() -> SafeRegionCoverCertificate:
    first_row = (0,) * 13
    second_row = (0,) * 12 + (1,)
    clause = SafeRegionClause((ProjectionAtom("eq", (("L0", 1),), 0),))
    predicate = SafeRegionPredicate(30, P30_VARIABLES, (clause,))
    pair = SeedPair((0, 1), (first_row, second_row))
    pool = generate_seed_pair_pool(first_row, second_row)
    atom_digest = hashlib.sha256(canonical_bytes(clause.atoms[0])).hexdigest()
    trace = (
        CoreReductionStep(atom_digest, atom_digest, "SAT", True),
    )
    provenance = SafeRegionProvenance(
        clause=clause,
        seed_pair=pair,
        pool_size=len(pool),
        pool_sha256=hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in pool])
        ).hexdigest(),
        solver_version="4.15.3",
        solver_parameters=(("phase_selection", 0), ("random_seed", 0)),
        named_core=clause.atoms,
        named_core_sha256=hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in clause.atoms])
        ).hexdigest(),
        minimization_trace=trace,
        promoted_indices=tuple(range(18)),
        bounded_extent=38_912,
    )
    return SafeRegionCoverCertificate(
        schema="t33-base19-safe-region-cover-certificate-v1",
        status="SAFE_REGION_COVER_PASS",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=digest_entries({"equations", "frontier", "provenances"}),
        t29_artifact_digests=digest_entries(
            {"evidence", "trace", "dataset", "certificate", "independent"}
        ),
        t30_artifact_digests=digest_entries(
            {"evidence", "certificate", "independent", "report"}
        ),
        t32_source_digests=digest_entries(
            {"library", "runner", "independent", "test"}
        ),
        t32_commits=("df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77"),
        t32_design_sha256=hashlib.sha256(b"t32-design").hexdigest(),
        t33_design_sha256=hashlib.sha256(b"t33-design").hexdigest(),
        t32_first_type_status="PASS",
        t32_first_type_sha256=hashlib.sha256(b"first-type").hexdigest(),
        t32_first_type_inspected_witness_count=3,
        t32_first_type_tested_candidate_count=31,
        t32_family_status="CANDIDATE_BUDGET_EXHAUSTED",
        t32_family_inspected_witness_count=8,
        t32_family_tested_candidate_count=10_000,
        predicate=predicate,
        provenances=(provenance,),
        seed_pair_count=1,
        region_test_count=1,
        cover_candidate_count=1,
        promoted_count=18,
        promoted_sha256=hashlib.sha256(b"promoted").hexdigest(),
        promoted_coverage=tuple(range(18)),
        first_match_ownership=(tuple(range(18)),),
        clause_extents=(38_912,),
        predicate_extent=38_912,
        predicate_bytes=len(canonical_bytes(predicate.to_payload())),
        promoted_table_bytes=616,
        clause_safety_statuses=("UNSAT",),
        primary_safety_status="UNSAT",
        independent_status="PASS",
        enumerated_input_count=77_824,
    )


def test_certificate_round_trips_exactly() -> None:
    certificate = certificate_fixture()
    parsed = parse_safe_region_cover_certificate(certificate.to_payload())
    assert parsed == certificate
    assert canonical_bytes(parsed.to_payload()) == canonical_bytes(
        certificate.to_payload()
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("status", "SAFE_REGION_COVER_STOP", "status"),
        ("promoted_count", 17, "18 promoted"),
        ("promoted_coverage", tuple(range(17)), "coverage"),
        ("first_match_ownership", ((0,),), "own"),
        ("clause_extents", (3,), "extent"),
        ("predicate_bytes", 616, "smaller"),
        ("primary_safety_status", "SAT", "safety"),
        ("independent_status", "REJECT", "independent"),
        ("enumerated_input_count", 77_823, "77,824"),
    ),
)
def test_certificate_rejects_mutated_pass_claims(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(certificate_fixture(), **{field: value})


def test_certificate_parser_rejects_extra_keys() -> None:
    payload = certificate_fixture().to_payload()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="keys differ"):
        parse_safe_region_cover_certificate(payload)


def test_certificate_parser_rejects_mutated_seed_pool_provenance() -> None:
    payload = certificate_fixture().to_payload()
    changed_digest = copy.deepcopy(payload)
    changed_digest["provenances"][0]["pool_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pool digest"):
        parse_safe_region_cover_certificate(changed_digest)

    changed_seed = copy.deepcopy(payload)
    changed_seed["provenances"][0]["seed_pair"]["rows"][1][-1] = 2
    with pytest.raises(ValueError, match="pool"):
        parse_safe_region_cover_certificate(changed_seed)
