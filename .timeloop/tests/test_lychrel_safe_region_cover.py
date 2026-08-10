from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
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
from t33_base19_safe_region_cover import (  # noqa: E402
    T32_SOURCE_DIGESTS,
    EvidenceError,
    _load_t33_inputs_uncached,
    exact_bad_input_status,
    load_t33_inputs,
    query_bad_input,
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


def test_t33_adapter_rejects_a_mutated_t32_source(tmp_path: Path) -> None:
    changed = tmp_path / "t32.py"
    changed.write_bytes(
        (ROOT / ".timeloop/runs/t32_base19_semantic_leak_types.py").read_bytes()
        + b"\n"
    )
    with pytest.raises(EvidenceError, match="T32 runner raw SHA-256 changed"):
        _load_t33_inputs_uncached(ROOT, t32_runner_path=changed)


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


def weak_milestone_payload() -> dict[str, object]:
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    layer = next(item for item in frontier["layers"] if item["layer"] == 31)
    rows = [transition["input_state"] for transition in layer["transitions"]]
    atom = {"relation": "le", "terms": [["D0", 1]], "constant": 18}
    atom_digest = hashlib.sha256(canonical_bytes(atom)).hexdigest()
    core_digest = hashlib.sha256(canonical_bytes([atom])).hexdigest()
    return {
        "schema": "t33-base19-safe-region-milestone-v1",
        "source_digests": {
            "equations": "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040",
            "frontier": "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0",
            "provenances": "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302",
        },
        "t29_artifact_digests": {
            "certificate": "1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a",
            "dataset": "6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995",
            "evidence": "c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32",
            "independent": "9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644",
            "trace": "c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715",
        },
        "t30_artifact_digests": {
            "certificate": "3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892",
            "evidence": "4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a",
            "independent": "56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639",
            "report": "3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c",
        },
        "t32_source_digests": T32_SOURCE_DIGESTS,
        "t32_commits": ["df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77"],
        "t32_design_sha256": "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd",
        "t33_design_sha256": "dadd1fe42f32d6f61b72609394f2172ca4fac3a6979660d03453058a221322a0",
        "clause": {"atoms": [atom]},
        "provenance": {
            "clause": {"atoms": [atom]},
            "seed_pair": {"indices": [0, 1], "rows": rows[:2]},
            "pool_size": 1,
            "pool_sha256": hashlib.sha256(canonical_bytes([atom])).hexdigest(),
            "solver_version": "test",
            "solver_parameters": [["phase_selection", 0], ["random_seed", 0]],
            "named_core": [atom],
            "named_core_sha256": core_digest,
            "minimization_trace": [
                {
                    "removed_atom_sha256": atom_digest,
                    "candidate_sha256": hashlib.sha256(canonical_bytes([])).hexdigest(),
                    "status": "SAT",
                    "retained": True,
                }
            ],
            "promoted_indices": list(range(18)),
            "bounded_extent": 77_824,
        },
        "primary_safety_status": "UNSAT",
    }


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


def test_independent_milestone_rejects_a_bad_successor(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(canonical_bytes(weak_milestone_payload()) + b"\n")
    completed = run_independent_milestone(candidate)
    assert completed.returncode != 0
    assert "safe-region counterexample" in completed.stderr


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
