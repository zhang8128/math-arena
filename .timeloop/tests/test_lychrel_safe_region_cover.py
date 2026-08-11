from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEPENDENT = ROOT / ".timeloop/runs/t33_base19_safe_region_cover_independent.py"
EQUATIONS = ROOT / "publication/base19-radial/instance/equations.json"
FRONTIER = ROOT / "publication/base19-radial/certificates/minimal-core-frontier.json"
T27_EVIDENCE = ROOT / ".timeloop/runs/t27_base19_invariant_lift.json"
T28_EVIDENCE = ROOT / ".timeloop/runs/t28_base19_tail_quotient.json"
T28_INDEPENDENT = ROOT / ".timeloop/runs/t28_base19_tail_quotient_independent.json"
T29_TRACE = ROOT / ".timeloop/runs/t29_base19_reachability_separator_trace.json"
T29_DATASET = ROOT / ".timeloop/runs/t29_base19_reachability_separator_dataset.json"
T29_EVIDENCE = ROOT / ".timeloop/runs/t29_base19_reachability_separator.json"
T29_CERTIFICATE = ROOT / ".timeloop/runs/t29_base19_reachability_separator_certificate.json"
T29_INDEPENDENT = ROOT / ".timeloop/runs/t29_base19_reachability_separator_independent.json"
T30_EVIDENCE = ROOT / ".timeloop/runs/t30_base19_exact_image_refinement.json"
T30_CERTIFICATE = ROOT / ".timeloop/runs/t30_base19_exact_image_refinement_certificate.json"
T30_INDEPENDENT = ROOT / ".timeloop/runs/t30_base19_exact_image_refinement_independent.json"
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_bad_image_projection import P30_VARIABLES, ProjectionAtom  # noqa: E402
from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from lychrel_safe_region_cover import (  # noqa: E402
    CoreReductionStep,
    IncrementalSearchTranscript,
    RegionQueryRecord,
    SafeRegionClause,
    SafeRegionCoverCertificate,
    SafeRegionPredicate,
    SafeRegionProvenance,
    SearchVisit,
    SeedPair,
    SeedPairSearchTrace,
    bounded_layer30_rows,
    clause_extent,
    compactness_bytes,
    evaluate_safe_atom,
    evaluate_safe_clause,
    evaluate_safe_predicate,
    first_match_ownership,
    generate_seed_pair_pool,
    parse_incremental_search_transcript,
    parse_region_query_record,
    parse_safe_region_cover_certificate,
)
from t33_base19_safe_region_cover import (  # noqa: E402
    T32_SOURCE_DIGESTS,
    CandidateDecision,
    EvidenceError,
    FirstSafeRegionResult,
    PairBudgetExhausted,
    RegionBudgetExhausted,
    RegionSearchBudget,
    _load_t33_inputs_uncached,
    _milestone_payload,
    branch_atoms,
    countermodel_guided_search,
    deletion_minimize_core,
    exact_bad_input_status,
    find_first_safe_region,
    input_assignment_from_witness,
    load_t33_inputs,
    milestone_result_payload,
    query_bad_input,
    query_safe_conjunction,
    verify_region_candidate,
)


def digest_entries(names: set[str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((name, hashlib.sha256(name.encode()).hexdigest()) for name in names)
    )


def row_assignment(row: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(P30_VARIABLES, row, strict=True))


def semantic_witness_for_row(row: tuple[int, ...]) -> SemanticWitness:
    return SemanticWitness(
        input_state=tuple(
            sorted(
                (f"input:{name}", value)
                for name, value in zip(P30_VARIABLES, row, strict=True)
            )
        ),
        output_state=(("output:D0", 0),),
        local_state=(),
    )


def finite_oracle(models: tuple[dict[str, int], ...]):
    def decide(atoms: tuple[ProjectionAtom, ...]) -> RegionQueryRecord:
        for model in models:
            if all(evaluate_safe_atom(atom, model) for atom in atoms):
                row = tuple(model[name] for name in P30_VARIABLES)
                return RegionQueryRecord.from_query(
                    atoms,
                    status="SAT",
                    witness=semantic_witness_for_row(row),
                    equation_residuals=(0,) * 12,
                    q0_holds=False,
                )
        return RegionQueryRecord.from_query(atoms, status="UNSAT")

    return decide


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


def test_incremental_query_records_are_strict_and_round_trip() -> None:
    atoms = tuple(
        ProjectionAtom("eq", ((f"L{index}", 1),), 0) for index in range(6)
    )
    witness = semantic_witness_for_row((0,) * len(P30_VARIABLES))
    record = RegionQueryRecord.from_query(
        atoms,
        status="SAT",
        witness=witness,
        equation_residuals=(0,) * 12,
        q0_holds=False,
    )
    atom_by_sha256 = {
        hashlib.sha256(canonical_bytes(atom)).hexdigest(): atom for atom in atoms
    }
    assert parse_region_query_record(record.to_payload(), atom_by_sha256) == record

    changed = copy.deepcopy(record.to_payload())
    changed["conjunction_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="conjunction digest"):
        parse_region_query_record(changed, atom_by_sha256)
    with pytest.raises(ValueError, match="at most six"):
        RegionQueryRecord.from_query(
            (*atoms, ProjectionAtom("eq", (("R5", 1),), 0)),
            status="UNSAT",
        )
    with pytest.raises(ValueError, match="canonical and distinct"):
        RegionQueryRecord.from_query(tuple(reversed(atoms)), status="UNSAT")


def test_incremental_query_status_union_is_strict() -> None:
    empty = RegionQueryRecord.from_query((), status="UNSAT")
    assert empty.conjunction == ()
    with pytest.raises(ValueError, match="SAT query requires"):
        RegionQueryRecord.from_query((), status="SAT")
    with pytest.raises(ValueError, match="SAT query requires"):
        RegionQueryRecord.from_query(
            (),
            status="SAT",
            witness=semantic_witness_for_row((0,) * len(P30_VARIABLES)),
            equation_residuals=(0,) * 11,
            q0_holds=False,
        )
    with pytest.raises(ValueError, match="UNSAT query forbids"):
        RegionQueryRecord.from_query(
            (),
            status="UNSAT",
            witness=semantic_witness_for_row((0,) * len(P30_VARIABLES)),
        )


def test_incremental_transcript_cross_links_queries_and_seed_pools() -> None:
    first_row = (0,) * len(P30_VARIABLES)
    second_row = (0,) * (len(P30_VARIABLES) - 1) + (1,)
    seed_pair = SeedPair((0, 1), (first_row, second_row))
    pool = generate_seed_pair_pool(*seed_pair.rows)
    pool_sha256 = hashlib.sha256(
        canonical_bytes([atom.to_payload() for atom in pool])
    ).hexdigest()
    query = RegionQueryRecord.from_query((), status="UNSAT")
    visit = SearchVisit(
        purpose="ROOT",
        parent_sha256=None,
        query_sha256=query.conjunction_sha256,
        fresh_query=True,
        violated_atom_sha256s=(),
        branch_atom_sha256s=(),
    )
    pair_trace = SeedPairSearchTrace(
        seed_pair=seed_pair,
        pool_size=len(pool),
        pool_sha256=pool_sha256,
        visits=(visit,),
    )
    transcript = IncrementalSearchTranscript((query,), (pair_trace,))
    assert parse_incremental_search_transcript(transcript.to_payload()) == transcript

    duplicate_fresh = copy.deepcopy(transcript.to_payload())
    duplicate_fresh["pairs"][0]["visits"].append(
        copy.deepcopy(duplicate_fresh["pairs"][0]["visits"][0])
    )
    with pytest.raises(ValueError, match="exactly one fresh"):
        parse_incremental_search_transcript(duplicate_fresh)

    outside_pool = copy.deepcopy(transcript.to_payload())
    outside_pool["pairs"][0]["visits"][0]["violated_atom_sha256s"] = ["0" * 64]
    outside_pool["pairs"][0]["visits"][0]["branch_atom_sha256s"] = ["0" * 64]
    with pytest.raises(ValueError, match="seed pool"):
        parse_incremental_search_transcript(outside_pool)


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
        core_candidate=clause.atoms,
        core_candidate_sha256=hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in clause.atoms])
        ).hexdigest(),
        acquisition_query_sha256=hashlib.sha256(
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


def test_t33_adapter_replays_the_committed_t32_stop() -> None:
    inputs = load_t33_inputs(ROOT)
    assert inputs.t32_first_type_status == "PASS"
    assert inputs.t32_first_type.to_payload() == {
        "literals": [
            {"phase": 0, "kind": "digit_order", "relation": "eq"},
            {"phase": 0, "kind": "digit_sum", "relation": "lt19"},
        ]
    }
    assert inputs.t32_first_type_tested_candidate_count == 31
    assert inputs.t32_first_type_inspected_witness_count == 3
    assert inputs.t32_family_status == "CANDIDATE_BUDGET_EXHAUSTED"
    assert inputs.t32_family_tested_candidate_count == 10_000
    assert inputs.t32_family_inspected_witness_count == 8
    assert inputs.promoted_rows == inputs.t32_inputs.t31_inputs.promoted_rows
    assert len(inputs.promoted_rows) == len(set(inputs.promoted_rows)) == 18
    assert dict(inputs.t32_source_digests) == T32_SOURCE_DIGESTS


def test_bad_input_solver_accepts_no_promoted_row() -> None:
    inputs = load_t33_inputs(ROOT)
    assert tuple(
        exact_bad_input_status(inputs, row) for row in inputs.promoted_rows
    ) == ("UNSAT",) * 18


def test_bad_input_query_replays_a_sat_countermodel() -> None:
    inputs = load_t33_inputs(ROOT)
    witness_input = dict(inputs.t32_inputs.t31_witness.input_state)
    row = tuple(witness_input[f"input:{name}"] for name in P30_VARIABLES)
    result = query_bad_input(inputs, row)
    assert result.status == "SAT"
    assert result.witness is not None
    assert result.equation_residuals == (0,) * 12
    assert result.q0_holds is False


def test_exact_empty_conjunction_returns_replayed_sat_record() -> None:
    record = query_safe_conjunction(load_t33_inputs(ROOT), ())
    assert record.status == "SAT"
    assert record.witness is not None
    assert record.equation_residuals == (0,) * 12
    assert record.q0_holds is False


def test_exact_oracle_rejects_more_than_six_atoms() -> None:
    atoms = tuple(
        sorted(
            (
                ProjectionAtom("le", ((name, 1),), 0)
                for name in P30_VARIABLES[:7]
            ),
            key=canonical_bytes,
        )
    )
    with pytest.raises(ValueError, match="at most six"):
        query_safe_conjunction(load_t33_inputs(ROOT), atoms)


def test_candidate_gate_requires_a_fresh_unsat_replay() -> None:
    inputs = load_t33_inputs(ROOT)
    seed_pair = SeedPair((0, 1), inputs.promoted_rows[:2])
    pool = generate_seed_pair_pool(*seed_pair.rows)
    promoted = tuple(row_assignment(row) for row in inputs.promoted_rows)
    atom = next(
        candidate
        for candidate in pool
        if len(
            tuple(
                row
                for row in promoted
                if evaluate_safe_atom(candidate, row)
            )
        )
        >= 2
    )
    core = (atom,)
    acquisition = RegionQueryRecord.from_query(core, status="UNSAT")
    atom_digest = hashlib.sha256(canonical_bytes(atom)).hexdigest()
    reduction = (
        CoreReductionStep(
            atom_digest,
            hashlib.sha256(canonical_bytes([])).hexdigest(),
            "SAT",
            True,
        ),
    )

    def sat_replay(atoms: tuple[ProjectionAtom, ...]) -> RegionQueryRecord:
        return RegionQueryRecord.from_query(
            atoms,
            status="SAT",
            witness=semantic_witness_for_row((0,) * len(P30_VARIABLES)),
            equation_residuals=(0,) * 12,
            q0_holds=False,
        )

    rejected = verify_region_candidate(
        inputs,
        seed_pair,
        pool,
        promoted,
        core,
        core,
        reduction,
        acquisition,
        sat_replay,
    )
    assert rejected.status == "REJECT"
    assert rejected.detail == "fresh primary query is not UNSAT"

    accepted = verify_region_candidate(
        inputs,
        seed_pair,
        pool,
        promoted,
        core,
        core,
        reduction,
        acquisition,
        lambda atoms: RegionQueryRecord.from_query(atoms, status="UNSAT"),
    )
    assert accepted.status == "PASS"
    assert accepted.provenance is not None
    assert accepted.provenance.acquisition_query_sha256 == acquisition.conjunction_sha256


def test_t33_adapter_rejects_a_mutated_t32_source(tmp_path: Path) -> None:
    changed = tmp_path / "t32.py"
    changed.write_bytes(
        (ROOT / ".timeloop/runs/t32_base19_semantic_leak_types.py").read_bytes()
        + b"\n"
    )
    with pytest.raises(EvidenceError, match="T32 runner raw SHA-256 changed"):
        _load_t33_inputs_uncached(ROOT, t32_runner_path=changed)


def test_t33_adapter_rejects_a_mutated_restart_design(tmp_path: Path) -> None:
    changed = tmp_path / "restart-design.md"
    restart_design = ROOT / (
        "docs/superpowers/specs/"
        "2026-08-10-base19-safe-region-incremental-core-restart-design.md"
    )
    changed.write_bytes(
        restart_design.read_bytes() + b"\n"
    )
    with pytest.raises(EvidenceError, match="restart design raw SHA-256 changed"):
        _load_t33_inputs_uncached(ROOT, restart_design_path=changed)


def test_milestone_stop_payload_binds_boundary_and_omits_candidate() -> None:
    inputs = load_t33_inputs(ROOT)
    seed_pair = SeedPair((0, 1), inputs.promoted_rows[:2])
    pool = generate_seed_pair_pool(*seed_pair.rows)
    query = RegionQueryRecord.from_query((), status="UNSAT")
    visit = SearchVisit(
        "ROOT", None, query.conjunction_sha256, True, (), ()
    )
    trace = SeedPairSearchTrace(
        seed_pair,
        len(pool),
        hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in pool])
        ).hexdigest(),
        (visit,),
    )
    transcript = IncrementalSearchTranscript((query,), (trace,))
    result = FirstSafeRegionResult(
        status="UNKNOWN",
        clause=None,
        provenance=None,
        seed_pair_count=1,
        region_test_count=1,
        primary_safety_status=None,
        independent_status=None,
        stop_detail="synthetic stop",
        search_transcript=transcript,
    )
    payload = milestone_result_payload(inputs, result)
    assert payload["t33_restart_design_sha256"] == inputs.t33_restart_design_sha256
    assert payload["stop_detail"] == "synthetic stop"
    assert "clause" not in payload
    assert "provenance" not in payload


def load_independent_module() -> object:
    spec = importlib.util.spec_from_file_location("t33_independent_test", INDEPENDENT)
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
        "dataclasses",
        "hashlib",
        "itertools",
        "json",
        "math",
        "re",
        "sys",
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


def test_independent_affine_atoms_cover_all_relations() -> None:
    module = load_independent_module()
    assignment = {name: 0 for name in P30_VARIABLES}
    assignment["D0"] = 7
    assert module.affine_atom_holds(
        {"relation": "eq", "terms": [["L0", 1], ["R0", -1]], "constant": 0},
        assignment,
    )
    assert module.affine_atom_holds(
        {"relation": "le", "terms": [["D0", 1]], "constant": 7}, assignment
    )
    assert module.affine_atom_holds(
        {
            "relation": "congruent",
            "terms": [["D0", 1]],
            "constant": 1,
            "modulus": 3,
        },
        assignment,
    )


def test_independent_seed_pool_matches_primary_canonical_bytes() -> None:
    module = load_independent_module()
    first = (0,) * 13
    second = (0,) * 12 + (1,)
    primary = [atom.to_payload() for atom in generate_seed_pair_pool(first, second)]
    assert module.generate_seed_pair_pool(first, second) == primary


@cache
def weak_milestone_payload() -> dict[str, object]:
    inputs = load_t33_inputs(ROOT)
    seed_pair = SeedPair((0, 1), inputs.promoted_rows[:2])
    pool = generate_seed_pair_pool(*seed_pair.rows)
    promoted = tuple(row_assignment(row) for row in inputs.promoted_rows)
    root = query_safe_conjunction(inputs, ())
    assert root.witness is not None
    root_assignment = input_assignment_from_witness(root.witness)
    prior = (tuple((name, root_assignment[name]) for name in P30_VARIABLES),)
    violated, branches = branch_atoms(root, pool, prior, promoted)
    assert len(branches) >= 2
    atom = branches[0]
    acquisition = RegionQueryRecord.from_query((atom,), status="UNSAT")
    atom_digest = hashlib.sha256(canonical_bytes(atom)).hexdigest()
    violated_digests = tuple(
        hashlib.sha256(canonical_bytes(item)).hexdigest() for item in violated
    )
    branch_digests = tuple(
        hashlib.sha256(canonical_bytes(item)).hexdigest() for item in branches
    )
    visits = (
        SearchVisit(
            "ROOT",
            None,
            root.conjunction_sha256,
            True,
            violated_digests,
            branch_digests,
        ),
        SearchVisit(
            "SEARCH",
            root.conjunction_sha256,
            acquisition.conjunction_sha256,
            True,
            (),
            (),
        ),
        SearchVisit(
            "REDUCTION",
            acquisition.conjunction_sha256,
            root.conjunction_sha256,
            False,
            violated_digests,
            branch_digests,
        ),
        SearchVisit(
            "ACCEPTANCE_REPLAY",
            acquisition.conjunction_sha256,
            acquisition.conjunction_sha256,
            False,
            (),
            (),
        ),
    )
    pool_digest = hashlib.sha256(
        canonical_bytes([item.to_payload() for item in pool])
    ).hexdigest()
    trace = SeedPairSearchTrace(
        seed_pair,
        len(pool),
        pool_digest,
        visits,
    )
    transcript = IncrementalSearchTranscript((root, acquisition), (trace,))
    clause = SafeRegionClause((atom,))
    promoted_indices = tuple(
        index
        for index, assignment in enumerate(promoted)
        if evaluate_safe_clause(clause, assignment)
    )
    reduction = (
        CoreReductionStep(
            atom_digest,
            root.conjunction_sha256,
            "SAT",
            True,
        ),
    )
    provenance = SafeRegionProvenance(
        clause=clause,
        seed_pair=seed_pair,
        pool_size=len(pool),
        pool_sha256=pool_digest,
        solver_version="fixture",
        solver_parameters=(("phase_selection", 0), ("random_seed", 0)),
        core_candidate=(atom,),
        core_candidate_sha256=acquisition.conjunction_sha256,
        acquisition_query_sha256=acquisition.conjunction_sha256,
        minimization_trace=reduction,
        promoted_indices=promoted_indices,
        bounded_extent=clause_extent(clause),
    )
    return _milestone_payload(inputs, clause, provenance, transcript)


def run_independent_milestone(
    candidate: Path, *, equations: Path = EQUATIONS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(INDEPENDENT),
            "milestone",
            str(equations),
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
            str(candidate),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def run_independent_payload(
    payload: dict[str, object], tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(canonical_bytes(payload) + b"\n")
    return run_independent_milestone(candidate)


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda payload: payload["search_transcript"]["queries"][0].__setitem__(
                "conjunction_sha256", "0" * 64
            ),
            "query digest",
        ),
        (
            lambda payload: payload["search_transcript"]["pairs"][0]["visits"][
                0
            ].__setitem__("fresh_query", False),
            "fresh-query",
        ),
        (
            lambda payload: payload["search_transcript"]["pairs"][0]["visits"][
                0
            ]["branch_atom_sha256s"].reverse(),
            "branch order",
        ),
        (
            lambda payload: payload.__setitem__(
                "region_test_count", payload["region_test_count"] + 1
            ),
            "counter",
        ),
    ),
)
def test_independent_rejects_corrupted_incremental_transcript(
    mutate, message: str, tmp_path: Path
) -> None:
    payload = copy.deepcopy(weak_milestone_payload())
    mutate(payload)
    completed = run_independent_payload(payload, tmp_path)
    assert completed.returncode != 0
    assert message in completed.stderr


def test_independent_milestone_rejects_a_bad_successor(tmp_path: Path) -> None:
    completed = run_independent_payload(weak_milestone_payload(), tmp_path)
    assert completed.returncode != 0
    assert "claimed UNSAT query is SAT" in completed.stderr


def test_independent_milestone_rejects_a_mutated_equation_source(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(canonical_bytes(weak_milestone_payload()) + b"\n")
    equations = tmp_path / "equations.json"
    changed_equations = json.loads(EQUATIONS.read_text(encoding="utf-8"))
    changed_equations["base"] = 18
    equations.write_bytes(canonical_bytes(changed_equations) + b"\n")
    completed = run_independent_milestone(candidate, equations=equations)
    assert completed.returncode != 0
    assert "equation content digest changed" in completed.stderr


def test_region_budget_counts_only_distinct_conjunctions_and_stops_exactly() -> None:
    budget = RegionSearchBudget(pair_limit=2, region_limit=2)
    budget.enter_pair()
    budget.enter_pair()
    with pytest.raises(PairBudgetExhausted):
        budget.enter_pair()
    assert budget.register_query(hashlib.sha256(b"first").hexdigest())
    assert not budget.register_query(hashlib.sha256(b"first").hexdigest())
    assert budget.register_query(hashlib.sha256(b"second").hexdigest())
    with pytest.raises(RegionBudgetExhausted):
        budget.register_query(hashlib.sha256(b"third").hexdigest())
    assert budget.seed_pair_count == 2
    assert budget.region_test_count == 2


def synthetic_search_fixture():
    first_row = (0,) * len(P30_VARIABLES)
    second_row = (0,) * (len(P30_VARIABLES) - 1) + (1,)
    pair = SeedPair((0, 1), (first_row, second_row))
    pool = tuple(
        sorted(
            (
                ProjectionAtom("eq", (("L0", 1),), 0),
                ProjectionAtom("eq", (("R0", 1),), 0),
                ProjectionAtom("eq", (("L1", 1),), 0),
            ),
            key=canonical_bytes,
        )
    )
    assert set(pool) <= set(generate_seed_pair_pool(*pair.rows))

    def model(**changes: int) -> dict[str, int]:
        assignment = {name: 0 for name in P30_VARIABLES}
        assignment.update({"L0": 1, "R0": 1, "L1": 1})
        assignment.update(changes)
        return assignment

    models = (
        model(L0=0),
        model(R0=0),
        model(L1=0),
    )
    promoted = tuple(row_assignment(row) for row in pair.rows)
    return pair, pool, models, promoted


def test_branch_atoms_are_exactly_the_replayed_model_violations() -> None:
    _, pool, models, promoted = synthetic_search_fixture()
    record = finite_oracle(models)(())
    violated, branches = branch_atoms(record, pool, (), promoted)
    assignment = models[0]
    assert set(violated) == {
        atom for atom in pool if not evaluate_safe_atom(atom, assignment)
    }
    assert set(branches) == set(violated)


def test_countermodel_guided_search_finds_a_minimal_two_atom_core() -> None:
    pair, pool, models, promoted = synthetic_search_fixture()
    budget = RegionSearchBudget(pair_limit=1, region_limit=20)
    budget.enter_pair()
    query_cache: dict[str, RegionQueryRecord] = {}
    queried_lengths: list[int] = []

    def query_exact(atoms: tuple[ProjectionAtom, ...]) -> RegionQueryRecord:
        queried_lengths.append(len(atoms))
        assert len(atoms) <= 2
        return finite_oracle(models)(atoms)

    def verify_candidate(
        minimized: tuple[ProjectionAtom, ...],
        core_candidate: tuple[ProjectionAtom, ...],
        reduction: tuple[CoreReductionStep, ...],
        acquisition: RegionQueryRecord,
        fresh_acceptance,
    ) -> CandidateDecision:
        assert len(minimized) == 2
        assert fresh_acceptance(minimized).status == "UNSAT"
        clause = SafeRegionClause(minimized)
        full_pool = generate_seed_pair_pool(*pair.rows)
        digest = hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in core_candidate])
        ).hexdigest()
        provenance = SafeRegionProvenance(
            clause=clause,
            seed_pair=pair,
            pool_size=len(full_pool),
            pool_sha256=hashlib.sha256(
                canonical_bytes([atom.to_payload() for atom in full_pool])
            ).hexdigest(),
            solver_version="synthetic",
            solver_parameters=(('phase_selection', 0), ('random_seed', 0)),
            core_candidate=core_candidate,
            core_candidate_sha256=digest,
            acquisition_query_sha256=acquisition.conjunction_sha256,
            minimization_trace=reduction,
            promoted_indices=(0, 1),
            bounded_extent=clause_extent(clause),
        )
        return CandidateDecision("PASS", provenance, None)

    result = countermodel_guided_search(
        pair,
        pool,
        promoted,
        budget,
        query_cache,
        query_exact,
        verify_candidate,
        max_atoms=2,
    )
    assert result.status == "PASS"
    assert result.provenance is not None
    assert len(result.provenance.clause.atoms) == 2
    assert max(queried_lengths) <= 2
    assert budget.region_test_count == len(query_cache)
    assert any(visit.purpose == "ACCEPTANCE_REPLAY" for visit in result.trace.visits)


def test_countermodel_search_closes_when_model_violates_no_pool_atom() -> None:
    pair, pool, _, promoted = synthetic_search_fixture()
    all_true = ({name: 0 for name in P30_VARIABLES},)
    budget = RegionSearchBudget(pair_limit=1, region_limit=5)
    budget.enter_pair()
    result = countermodel_guided_search(
        pair,
        pool,
        promoted,
        budget,
        {},
        finite_oracle(all_true),
        lambda *_: pytest.fail("SAT-only search must not verify a candidate"),
        max_atoms=2,
    )
    assert result.status == "EXHAUSTED"
    assert result.trace.visits[0].violated_atom_sha256s == ()


def test_countermodel_search_reuses_global_queries_without_recounting() -> None:
    pair, pool, _, promoted = synthetic_search_fixture()
    all_true = ({name: 0 for name in P30_VARIABLES},)
    budget = RegionSearchBudget(pair_limit=2, region_limit=5)
    cache: dict[str, RegionQueryRecord] = {}
    traces = []
    for _ in range(2):
        budget.enter_pair()
        result = countermodel_guided_search(
            pair,
            pool,
            promoted,
            budget,
            cache,
            finite_oracle(all_true),
            lambda *_: pytest.fail("SAT-only search must not verify a candidate"),
            max_atoms=2,
        )
        traces.append(result.trace)
    assert budget.region_test_count == 1
    assert traces[0].visits[0].fresh_query is True
    assert traces[1].visits[0].fresh_query is False


def test_countermodel_search_propagates_unknown_without_more_queries() -> None:
    pair, pool, models, promoted = synthetic_search_fixture()
    budget = RegionSearchBudget(pair_limit=1, region_limit=20)
    budget.enter_pair()

    result = countermodel_guided_search(
        pair,
        pool,
        promoted,
        budget,
        {},
        finite_oracle(models),
        lambda *_: CandidateDecision("UNKNOWN", None, "synthetic gate stopped"),
        max_atoms=2,
    )
    assert result.status == "UNKNOWN"
    assert result.stop_detail == "synthetic gate stopped"
    assert budget.region_test_count == len(
        {visit.query_sha256 for visit in result.trace.visits if visit.fresh_query}
    )


def test_deletion_minimization_is_canonical_and_irreducible() -> None:
    atoms = (
        ProjectionAtom("eq", (("L0", 1),), 0),
        ProjectionAtom("eq", (("R0", 1),), 0),
        ProjectionAtom("eq", (("L1", 1),), 0),
    )
    ordered = tuple(sorted(atoms, key=canonical_bytes))

    def status(candidate: tuple[ProjectionAtom, ...]) -> str:
        names = {name for atom in candidate for name, _ in atom.terms}
        return "UNSAT" if {"L0", "R0"} <= names else "SAT"

    minimized, trace = deletion_minimize_core(tuple(reversed(atoms)), status)
    assert minimized == tuple(atom for atom in ordered if atom.terms[0][0] != "L1")
    assert tuple(step.status for step in trace) == ("SAT", "UNSAT", "SAT")
    assert tuple(step.retained for step in trace) == (True, False, True)


def test_repository_first_safe_region_reaches_pass_or_exact_stop() -> None:
    result = find_first_safe_region(load_t33_inputs(ROOT))
    assert result.status in {
        "PASS",
        "NO_SAFE_REGION",
        "PAIR_BUDGET_EXHAUSTED",
        "REGION_BUDGET_EXHAUSTED",
        "UNKNOWN",
        "INDEPENDENT_DISAGREEMENT",
    }
    assert 1 <= result.seed_pair_count <= 153
    assert 0 <= result.region_test_count <= 2_000
    if result.status == "PASS":
        assert result.clause is not None
        assert result.provenance is not None
        assert len(result.clause.atoms) <= 6
        assert result.provenance.bounded_extent >= 4
        assert len(result.provenance.promoted_indices) >= 2
        assert result.primary_safety_status == "UNSAT"
        assert result.independent_status == "PASS"
        assert result.stop_detail is None
    else:
        assert result.clause is None
        assert result.provenance is None
        assert result.stop_detail
