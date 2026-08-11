#!/usr/bin/env python3
"""Synthesize and certify a compact base-19 layer-30 safe-region cover."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_bad_image_projection import P30_VARIABLES, ProjectionAtom  # noqa: E402
from lychrel_invariant_certificate import canonical_bytes  # noqa: E402
from lychrel_reachability_separator import SemanticWitness  # noqa: E402
from lychrel_safe_region_cover import (  # noqa: E402
    CoreReductionStep,
    IncrementalSearchTranscript,
    RegionQueryRecord,
    SafeRegionClause,
    SafeRegionPredicate,
    SafeRegionProvenance,
    SearchVisit,
    SeedPair,
    SeedPairSearchTrace,
    canonical_conjunction,
    canonical_union,
    clause_extent,
    compactness_bytes,
    evaluate_safe_atom,
    evaluate_safe_clause,
    generate_seed_pair_pool,
)
from lychrel_semantic_leak_types import LeakType, StructuralLiteral  # noqa: E402
from t31_base19_bad_image_projection import (  # noqa: E402
    build_layer30_relation,
    replay_bad_image_witness,
)
from t32_base19_semantic_leak_types import (  # noqa: E402
    T32Inputs,
    find_first_leak_type,
    load_t32_inputs,
    synthesize_leak_family,
)

_REMOVED = "phase=0,n=0,column=82"
_T33_DESIGN_SHA256 = (
    "dadd1fe42f32d6f61b72609394f2172ca4fac3a6979660d03453058a221322a0"
)
T33_RESTART_DESIGN_SHA256 = (
    "10feaf957e889ca33b9f06441f88258179e2674e13248f72355adcd629b9c854"
)
_T32_DESIGN_SHA256 = (
    "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd"
)
T32_SOURCE_DIGESTS = {
    "library": "cf6ad87c8edf3ffa2c86449b9762f8c9d4254645eb71b7f88963a688a1bded11",
    "runner": "d9c90e0dc4ce910a6ddef66233b03bff31449a46662fba75628a44dca3ed9e57",
    "independent": "fb520b513dd5673e145b583ee8a5025c8113890fdb89139a48b528655ed506b5",
    "test": "a6ee921a8ba6304d3a48b0db0b893b6bd8077576acc27146b91d626ac00858bd",
}
T32_COMMITS = ("df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77")


class EvidenceError(RuntimeError):
    """Frozen T33 input evidence changed or is internally inconsistent."""


class SearchTerminated(EvidenceError):
    def __init__(self, status: str, detail: str | None) -> None:
        if status != "UNKNOWN":
            raise ValueError("unsupported terminal search status")
        if not detail:
            raise ValueError("terminal search detail must be nonempty")
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PairBudgetExhausted(EvidenceError):
    """The next canonical seed pair is outside the frozen pair budget."""


class RegionBudgetExhausted(EvidenceError):
    """The next distinct conjunction is outside the frozen region budget."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.trace: SeedPairSearchTrace | None = None


@dataclass(frozen=True)
class BadInputQueryResult:
    status: str
    witness: SemanticWitness | None
    equation_residuals: tuple[int, ...]
    q0_holds: bool | None

    def __post_init__(self) -> None:
        if self.status == "UNSAT":
            if self.witness is not None or self.equation_residuals or self.q0_holds is not None:
                raise ValueError("UNSAT bad-input result cannot carry a witness")
        elif self.status == "SAT":
            if (
                self.witness is None
                or self.equation_residuals != (0,) * 12
                or self.q0_holds is not False
            ):
                raise ValueError("SAT bad-input result requires an exact non-Q0 witness")
        else:
            raise ValueError("bad-input result status must be SAT or UNSAT")


@dataclass
class RegionSearchBudget:
    pair_limit: int = 153
    region_limit: int = 2_000
    seed_pair_count: int = 0
    region_test_count: int = 0
    _query_digests: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pair_limit, int)
            or isinstance(self.pair_limit, bool)
            or not 1 <= self.pair_limit <= 153
        ):
            raise ValueError("pair limit must be in 1..153")
        if (
            not isinstance(self.region_limit, int)
            or isinstance(self.region_limit, bool)
            or not 1 <= self.region_limit <= 2_000
        ):
            raise ValueError("region limit must be in 1..2,000")

    def enter_pair(self) -> None:
        if self.seed_pair_count >= self.pair_limit:
            raise PairBudgetExhausted(
                f"pair budget exhausted after {self.pair_limit} seed pairs"
            )
        self.seed_pair_count += 1

    def register_query(self, query_sha256: str) -> bool:
        if (
            not isinstance(query_sha256, str)
            or len(query_sha256) != 64
            or any(character not in "0123456789abcdef" for character in query_sha256)
        ):
            raise ValueError("query digest must be a lowercase SHA-256")
        if query_sha256 in self._query_digests:
            return False
        if self.region_test_count >= self.region_limit:
            raise RegionBudgetExhausted(
                f"region budget exhausted after {self.region_limit} conjunctions"
            )
        self._query_digests.add(query_sha256)
        self.region_test_count += 1
        return True


@dataclass(frozen=True)
class CandidateDecision:
    status: str
    provenance: SafeRegionProvenance | None
    detail: str | None

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "REJECT", "UNKNOWN"}:
            raise ValueError("unsupported candidate-decision status")
        if self.status == "PASS":
            if self.provenance is None or self.detail is not None:
                raise ValueError("candidate PASS must carry only provenance")
        elif self.provenance is not None or not self.detail:
            raise ValueError("candidate non-PASS must carry only detail")


@dataclass(frozen=True)
class PairSearchResult:
    status: str
    provenance: SafeRegionProvenance | None
    trace: SeedPairSearchTrace
    stop_detail: str | None

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "EXHAUSTED", "UNKNOWN"}:
            raise ValueError("unsupported pair-search status")
        if self.status == "PASS":
            if self.provenance is None or self.stop_detail is not None:
                raise ValueError("pair-search PASS fields differ")
        elif self.status == "EXHAUSTED":
            if self.provenance is not None or self.stop_detail is not None:
                raise ValueError("pair-search EXHAUSTED fields differ")
        elif self.provenance is not None or not self.stop_detail:
            raise ValueError("pair-search UNKNOWN fields differ")


@dataclass(frozen=True)
class FirstSafeRegionResult:
    status: str
    clause: SafeRegionClause | None
    provenance: SafeRegionProvenance | None
    seed_pair_count: int
    region_test_count: int
    primary_safety_status: str | None
    independent_status: str | None
    stop_detail: str | None
    search_transcript: IncrementalSearchTranscript

    def __post_init__(self) -> None:
        statuses = {
            "PASS",
            "NO_SAFE_REGION",
            "PAIR_BUDGET_EXHAUSTED",
            "REGION_BUDGET_EXHAUSTED",
            "UNKNOWN",
            "INDEPENDENT_DISAGREEMENT",
        }
        if self.status not in statuses:
            raise ValueError("unsupported first-safe-region status")
        if not 1 <= self.seed_pair_count <= 153:
            raise ValueError("first-safe-region pair count is outside 1..153")
        if not 0 <= self.region_test_count <= 2_000:
            raise ValueError("first-safe-region test count is outside 0..2,000")
        if len(self.search_transcript.pairs) != self.seed_pair_count:
            raise ValueError("first-safe-region transcript pair count differs")
        if len(self.search_transcript.queries) != self.region_test_count:
            raise ValueError("first-safe-region transcript query count differs")
        if self.status == "PASS":
            if (
                self.clause is None
                or self.provenance is None
                or self.primary_safety_status != "UNSAT"
                or self.independent_status != "PASS"
                or self.stop_detail is not None
            ):
                raise ValueError("first-safe-region PASS gates differ")
        elif self.clause is not None or self.provenance is not None or not self.stop_detail:
            raise ValueError("first-safe-region STOP must omit the candidate")

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "clause": None if self.clause is None else self.clause.to_payload(),
            "provenance": (
                None if self.provenance is None else self.provenance.to_payload()
            ),
            "seed_pair_count": self.seed_pair_count,
            "region_test_count": self.region_test_count,
            "primary_safety_status": self.primary_safety_status,
            "independent_status": self.independent_status,
            "stop_detail": self.stop_detail,
            "search_transcript": self.search_transcript.to_payload(),
        }


def deletion_minimize_core(
    core_candidate: tuple[ProjectionAtom, ...],
    status_for: Callable[[tuple[ProjectionAtom, ...]], str],
) -> tuple[tuple[ProjectionAtom, ...], tuple[CoreReductionStep, ...]]:
    """Deletion-minimize one acquired core in canonical atom order."""
    if not core_candidate or len(set(core_candidate)) != len(core_candidate):
        raise ValueError("core candidate must be nonempty and distinct")
    current = list(sorted(core_candidate, key=canonical_bytes))
    trace = []
    for atom in tuple(current):
        candidate = tuple(item for item in current if item != atom)
        status = status_for(candidate)
        if status not in {"SAT", "UNSAT"}:
            raise EvidenceError(f"core reduction returned {status}")
        retained = status == "SAT"
        trace.append(
            CoreReductionStep(
                hashlib.sha256(canonical_bytes(atom)).hexdigest(),
                hashlib.sha256(
                    canonical_bytes([item.to_payload() for item in candidate])
                ).hexdigest(),
                status,
                retained,
            )
        )
        if not retained:
            current = list(candidate)
    return tuple(current), tuple(trace)


def input_assignment_from_witness(witness: SemanticWitness) -> dict[str, int]:
    """Recover and validate the complete bounded input row from a witness."""
    values: dict[str, int] = {}
    for scoped_name, value in witness.input_state:
        if not scoped_name.startswith("input:"):
            raise ValueError("semantic witness input scope differs")
        name = scoped_name.removeprefix("input:")
        if name in values:
            raise ValueError("semantic witness repeats an input variable")
        values[name] = value
    if set(values) != set(P30_VARIABLES):
        raise ValueError("semantic witness input variables differ")
    assignment = {name: values[name] for name in P30_VARIABLES}
    for name, value in assignment.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("semantic witness input value must be an integer")
        if name == "D0":
            if not 0 <= value < 19:
                raise ValueError("semantic witness D0 is outside 0..18")
        elif value not in {0, 1}:
            raise ValueError("semantic witness carry is not Boolean")
    return assignment


def _atom_sha256(atom: ProjectionAtom) -> str:
    return hashlib.sha256(canonical_bytes(atom)).hexdigest()


def _conjunction_sha256(atoms: tuple[ProjectionAtom, ...]) -> str:
    return hashlib.sha256(
        canonical_bytes([atom.to_payload() for atom in atoms])
    ).hexdigest()


def branch_atoms(
    record: RegionQueryRecord,
    pool: tuple[ProjectionAtom, ...],
    prior_sat_inputs: tuple[tuple[tuple[str, int], ...], ...],
    promoted_assignments: tuple[dict[str, int], ...],
) -> tuple[tuple[ProjectionAtom, ...], tuple[ProjectionAtom, ...]]:
    """Return exact model violations and their deterministic branch order."""
    if record.status != "SAT" or record.witness is None:
        raise ValueError("branching requires a SAT record")
    if not pool or tuple(sorted(pool, key=canonical_bytes)) != pool or len(set(pool)) != len(pool):
        raise ValueError("branch pool must be canonical and distinct")
    assignment = input_assignment_from_witness(record.witness)
    violated = tuple(
        atom for atom in pool if not evaluate_safe_atom(atom, assignment)
    )

    def key(atom: ProjectionAtom) -> tuple[object, ...]:
        excluded = sum(
            not evaluate_safe_atom(atom, dict(prior)) for prior in prior_sat_inputs
        )
        coverage = sum(
            evaluate_safe_atom(atom, promoted) for promoted in promoted_assignments
        )
        extent = clause_extent(SafeRegionClause((atom,)))
        return (-excluded, -coverage, -extent, canonical_bytes(atom))

    return violated, tuple(sorted(violated, key=key))


def countermodel_guided_search(
    seed_pair: SeedPair,
    pool: tuple[ProjectionAtom, ...],
    promoted_assignments: tuple[dict[str, int], ...],
    budget: RegionSearchBudget,
    query_cache: dict[str, RegionQueryRecord],
    query_exact: Callable[[tuple[ProjectionAtom, ...]], RegionQueryRecord],
    verify_candidate: Callable[
        [
            tuple[ProjectionAtom, ...],
            tuple[ProjectionAtom, ...],
            tuple[CoreReductionStep, ...],
            RegionQueryRecord,
            Callable[[tuple[ProjectionAtom, ...]], RegionQueryRecord],
        ],
        CandidateDecision,
    ],
    *,
    max_atoms: int = 6,
) -> PairSearchResult:
    """Search one pool by branching only on replayed countermodel violations."""
    if not isinstance(max_atoms, int) or isinstance(max_atoms, bool) or not 1 <= max_atoms <= 6:
        raise ValueError("maximum search depth must be in 1..6")
    if tuple(sorted(pool, key=canonical_bytes)) != pool or len(set(pool)) != len(pool):
        raise ValueError("search pool must be canonical and distinct")
    full_pool = generate_seed_pair_pool(*seed_pair.rows)
    if not pool or not set(pool) <= set(full_pool):
        raise ValueError("search pool differs from the regenerated seed pool")
    visits: list[SearchVisit] = []
    prior_sat_inputs: list[tuple[tuple[str, int], ...]] = []

    def submit(
        conjunction: tuple[ProjectionAtom, ...],
        parent_sha256: str | None,
        purpose: str,
        *,
        force_fresh: bool = False,
    ) -> RegionQueryRecord:
        canonical = canonical_conjunction(
            conjunction, allow_empty=True, maximum=max_atoms
        )
        digest = _conjunction_sha256(canonical)
        cached = query_cache.get(digest)
        newly_registered = budget.register_query(digest)
        if newly_registered != (cached is None):
            raise EvidenceError("query cache and exact counter disagree")
        if force_fresh:
            if cached is None:
                raise EvidenceError("acceptance replay lacks a cached acquisition query")
            replayed = query_exact(canonical)
            if replayed.conjunction != canonical or replayed.conjunction_sha256 != digest:
                raise EvidenceError("fresh query returned a different conjunction")
            if replayed.status != cached.status:
                raise EvidenceError("fresh query disagrees with cached mathematical status")
            record = replayed
            fresh = False
        elif cached is None:
            record = query_exact(canonical)
            if record.conjunction != canonical or record.conjunction_sha256 != digest:
                raise EvidenceError("exact query returned a different conjunction")
            query_cache[digest] = record
            fresh = True
        else:
            record = cached
            fresh = False

        violated: tuple[ProjectionAtom, ...] = ()
        branches: tuple[ProjectionAtom, ...] = ()
        if record.status == "SAT":
            assignment = input_assignment_from_witness(record.witness)  # type: ignore[arg-type]
            canonical_input = tuple((name, assignment[name]) for name in P30_VARIABLES)
            if canonical_input not in prior_sat_inputs:
                prior_sat_inputs.append(canonical_input)
            violated, branches = branch_atoms(
                record,
                pool,
                tuple(prior_sat_inputs),
                promoted_assignments,
            )
        visits.append(
            SearchVisit(
                purpose,
                parent_sha256,
                digest,
                fresh,
                tuple(_atom_sha256(atom) for atom in violated),
                tuple(_atom_sha256(atom) for atom in branches),
            )
        )
        return record

    def visit(
        conjunction: tuple[ProjectionAtom, ...], parent_sha256: str | None
    ) -> SafeRegionProvenance | None:
        if len(conjunction) > max_atoms:
            raise AssertionError("search attempted more than six atoms")
        purpose = "ROOT" if parent_sha256 is None else "SEARCH"
        record = submit(conjunction, parent_sha256, purpose)
        if record.status == "UNSAT":
            if not conjunction:
                raise SearchTerminated(
                    "UNKNOWN", "empty conjunction was unexpectedly safe"
                )

            def status_for(candidate: tuple[ProjectionAtom, ...]) -> str:
                return submit(
                    candidate,
                    record.conjunction_sha256,
                    "REDUCTION",
                ).status

            minimized, reduction = deletion_minimize_core(conjunction, status_for)

            def fresh_acceptance(
                candidate: tuple[ProjectionAtom, ...],
            ) -> RegionQueryRecord:
                return submit(
                    candidate,
                    record.conjunction_sha256,
                    "ACCEPTANCE_REPLAY",
                    force_fresh=True,
                )

            decision = verify_candidate(
                minimized,
                conjunction,
                reduction,
                record,
                fresh_acceptance,
            )
            if decision.status == "PASS":
                return decision.provenance
            if decision.status == "REJECT":
                return None
            raise SearchTerminated(decision.status, decision.detail)
        current_visit = visits[-1]
        if not current_visit.branch_atom_sha256s or len(conjunction) == max_atoms:
            return None
        atom_by_digest = {_atom_sha256(atom): atom for atom in pool}
        for atom_digest in current_visit.branch_atom_sha256s:
            found = visit(
                canonical_union(conjunction, atom_by_digest[atom_digest]),
                record.conjunction_sha256,
            )
            if found is not None:
                return found
        return None

    pending_budget_error: RegionBudgetExhausted | None = None
    try:
        provenance = visit((), None)
        status = "PASS" if provenance is not None else "EXHAUSTED"
        detail = None
    except SearchTerminated as error:
        provenance = None
        status = error.status
        detail = error.detail
    except RegionBudgetExhausted as error:
        provenance = None
        status = "EXHAUSTED"
        detail = None
        pending_budget_error = error
    pool_sha256 = hashlib.sha256(
        canonical_bytes([atom.to_payload() for atom in full_pool])
    ).hexdigest()
    trace = SeedPairSearchTrace(seed_pair, len(full_pool), pool_sha256, tuple(visits))
    if pending_budget_error is not None:
        pending_budget_error.trace = trace
        raise pending_budget_error
    return PairSearchResult(status, provenance, trace, detail)


@dataclass(frozen=True)
class T33Inputs:
    t32_inputs: T32Inputs
    promoted_rows: tuple[tuple[int, ...], ...]
    t32_first_type: LeakType
    t32_first_type_status: str
    t32_first_type_sha256: str
    t32_first_type_inspected_witness_count: int
    t32_first_type_tested_candidate_count: int
    t32_family_status: str
    t32_family_inspected_witness_count: int
    t32_family_tested_candidate_count: int
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t32_source_digests: tuple[tuple[str, str], ...]
    t32_commits: tuple[str, ...]
    t32_design_sha256: str
    t33_design_sha256: str
    t33_restart_design_sha256: str

    def __post_init__(self) -> None:
        if len(self.promoted_rows) != 18 or len(set(self.promoted_rows)) != 18:
            raise ValueError("T33 requires 18 distinct promoted rows")
        if self.promoted_rows != self.t32_inputs.t31_inputs.promoted_rows:
            raise ValueError("T33 promoted rows differ from T32")
        expected_type = LeakType(
            (
                StructuralLiteral(0, "digit_order", "eq"),
                StructuralLiteral(0, "digit_sum", "lt19"),
            )
        )
        if self.t32_first_type != expected_type:
            raise ValueError("T32 first type differs")
        if (
            self.t32_first_type_status != "PASS"
            or self.t32_first_type_inspected_witness_count != 3
            or self.t32_first_type_tested_candidate_count != 31
        ):
            raise ValueError("T32 first-type milestone boundary differs")
        expected_digest = hashlib.sha256(
            canonical_bytes(self.t32_first_type.to_payload())
        ).hexdigest()
        if self.t32_first_type_sha256 != expected_digest:
            raise ValueError("T32 first-type digest differs")
        if (
            self.t32_family_status != "CANDIDATE_BUDGET_EXHAUSTED"
            or self.t32_family_inspected_witness_count != 8
            or self.t32_family_tested_candidate_count != 10_000
        ):
            raise ValueError("T32 family STOP boundary differs")
        if self.source_digests != self.t32_inputs.source_digests:
            raise ValueError("T33 source digests differ")
        if self.t29_artifact_digests != self.t32_inputs.t29_artifact_digests:
            raise ValueError("T33 T29 artifact digests differ")
        if self.t30_artifact_digests != self.t32_inputs.t30_artifact_digests:
            raise ValueError("T33 T30 artifact digests differ")
        if self.t32_source_digests != tuple(sorted(T32_SOURCE_DIGESTS.items())):
            raise ValueError("T33 T32 source digests differ")
        if self.t32_commits != T32_COMMITS:
            raise ValueError("T33 T32 commits differ")
        if self.t32_design_sha256 != _T32_DESIGN_SHA256:
            raise ValueError("T33 T32 design digest differs")
        if self.t33_design_sha256 != _T33_DESIGN_SHA256:
            raise ValueError("T33 design digest differs")
        if self.t33_restart_design_sha256 != T33_RESTART_DESIGN_SHA256:
            raise ValueError("T33 restart design digest differs")


def _bind_raw(path: Path, expected: str, context: str) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceError(f"cannot read {context}: {error}") from error
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise EvidenceError(f"{context} raw SHA-256 changed: {actual}")


def _load_t33_inputs_uncached(
    root: Path,
    *,
    t32_library_path: Path | None = None,
    t32_runner_path: Path | None = None,
    t32_independent_path: Path | None = None,
    t32_test_path: Path | None = None,
    design_path: Path | None = None,
    restart_design_path: Path | None = None,
) -> T33Inputs:
    """Bind frozen sources and replay the committed T32 PASS/STOP boundary."""
    root = Path(root)
    t32_paths = {
        "library": t32_library_path
        or root / ".timeloop/lib/lychrel_semantic_leak_types.py",
        "runner": t32_runner_path
        or root / ".timeloop/runs/t32_base19_semantic_leak_types.py",
        "independent": t32_independent_path
        or root / ".timeloop/runs/t32_base19_semantic_leak_types_independent.py",
        "test": t32_test_path
        or root / ".timeloop/tests/test_lychrel_semantic_leak_types.py",
    }
    for name, path in t32_paths.items():
        _bind_raw(path, T32_SOURCE_DIGESTS[name], f"T32 {name}")
    _bind_raw(
        design_path
        or root
        / "docs/superpowers/specs/2026-08-10-base19-safe-region-cover-restart-design.md",
        _T33_DESIGN_SHA256,
        "T33 design",
    )
    _bind_raw(
        restart_design_path
        or root
        / "docs/superpowers/specs/2026-08-10-base19-safe-region-incremental-core-restart-design.md",
        T33_RESTART_DESIGN_SHA256,
        "T33 restart design",
    )

    try:
        t32_inputs = load_t32_inputs(root)
        milestone = find_first_leak_type(t32_inputs)
        if milestone.status != "PASS" or milestone.leak_type is None:
            raise EvidenceError(f"T32 first-type replay stopped at {milestone.status}")
        family = synthesize_leak_family(t32_inputs, milestone)
    except (RuntimeError, ValueError) as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError(f"cannot replay T32 boundary: {error}") from error

    inputs = T33Inputs(
        t32_inputs=t32_inputs,
        promoted_rows=t32_inputs.t31_inputs.promoted_rows,
        t32_first_type=milestone.leak_type,
        t32_first_type_status=milestone.status,
        t32_first_type_sha256=hashlib.sha256(
            canonical_bytes(milestone.leak_type.to_payload())
        ).hexdigest(),
        t32_first_type_inspected_witness_count=milestone.inspected_witness_count,
        t32_first_type_tested_candidate_count=milestone.tested_candidate_count,
        t32_family_status=family.status,
        t32_family_inspected_witness_count=family.inspected_witness_count,
        t32_family_tested_candidate_count=family.tested_candidate_count,
        source_digests=t32_inputs.source_digests,
        t29_artifact_digests=t32_inputs.t29_artifact_digests,
        t30_artifact_digests=t32_inputs.t30_artifact_digests,
        t32_source_digests=tuple(sorted(T32_SOURCE_DIGESTS.items())),
        t32_commits=T32_COMMITS,
        t32_design_sha256=t32_inputs.design_sha256,
        t33_design_sha256=_T33_DESIGN_SHA256,
        t33_restart_design_sha256=T33_RESTART_DESIGN_SHA256,
    )
    statuses = replay_promoted_rows(inputs)
    if statuses != ("UNSAT",) * 18:
        raise EvidenceError(f"promoted bad-input replay differs: {statuses}")
    table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(row) for row in inputs.promoted_rows],
    }
    if len(canonical_bytes(table)) != 616:
        raise EvidenceError("T31 promoted table is no longer 616 bytes")
    return inputs


@cache
def load_t33_inputs(root: Path) -> T33Inputs:
    """Load and cache the immutable T33 input boundary."""
    return _load_t33_inputs_uncached(Path(root))


def z3_safe_atom(relation: object, atom: ProjectionAtom) -> object:
    """Translate one canonical layer-30 atom to the exact relation variables."""
    expression = sum(
        coefficient * relation.variables[relation.input_mapping[name]]
        for name, coefficient in atom.terms
    )
    if atom.relation == "eq":
        return expression == atom.constant
    if atom.relation == "le":
        return expression <= atom.constant
    assert atom.modulus is not None
    return (expression - atom.constant) % atom.modulus == 0


def z3_safe_clause(relation: object, clause: SafeRegionClause) -> object:
    """Translate a strict safe-region conjunction."""
    return relation.z3.And(*(z3_safe_atom(relation, atom) for atom in clause.atoms))


def _q0_expression(inputs: T33Inputs, relation: object) -> object:
    return relation.z3.And(
        *(
            sum(
                coefficient
                * relation.variables[relation.output_mapping[name]]
                for name, coefficient in atom.terms
            )
            == atom.constant
            for atom in inputs.t32_inputs.q0.clauses[0].atoms
        )
    )


def build_bad_input_solver(
    inputs: T33Inputs, clause: SafeRegionClause | None = None
) -> tuple[object, object]:
    """Build a fresh exact solver for ``B30`` and an optional input clause."""
    relation = build_layer30_relation(inputs.t32_inputs.t31_inputs)
    solver = relation.z3.Solver()
    solver.set(random_seed=0, phase_selection=0)
    solver.add(*relation.assertions)
    solver.add(relation.z3.Not(_q0_expression(inputs, relation)))
    if clause is not None:
        solver.add(z3_safe_clause(relation, clause))
    return relation, solver


def _solver_status(relation: object, solver: object, context: str) -> str:
    status = solver.check()
    if status == relation.z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return "SAT" if status == relation.z3.sat else "UNSAT"


def _validate_input_row(row: tuple[int, ...]) -> None:
    if len(row) != len(P30_VARIABLES):
        raise ValueError("layer-30 row width differs")
    for name, value in zip(P30_VARIABLES, row, strict=True):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"layer-30 row {name} must be an integer")
        if (name == "D0" and not 0 <= value < 19) or (
            name != "D0" and value not in {0, 1}
        ):
            raise ValueError(f"layer-30 row domain failure: {name}={value}")


def _canonical_assignment(
    relation: object, solver: object, context: str
) -> tuple[tuple[str, int], ...]:
    if _solver_status(relation, solver, context) != "SAT":
        raise EvidenceError(f"cannot minimize non-SAT {context}")
    for name, variable in sorted(relation.variables.items()):
        domain = (
            range(2)
            if name.startswith("c:")
            else range(
                1 if name.startswith("digit:p") and ":f0:d0" in name else 0,
                19,
            )
        )
        for value in domain:
            solver.push()
            solver.add(variable == value)
            status = _solver_status(relation, solver, f"{context} minimization")
            solver.pop()
            if status == "SAT":
                solver.add(variable == value)
                break
        else:
            raise EvidenceError(f"{context} variable has no domain value: {name}")
    if _solver_status(relation, solver, f"{context} finalization") != "SAT":
        raise EvidenceError(f"{context} became inconsistent")
    model = solver.model()
    return tuple(
        (name, model.eval(variable, model_completion=False).as_long())
        for name, variable in sorted(relation.variables.items())
    )


def _semantic_witness(
    relation: object, assignment: tuple[tuple[str, int], ...]
) -> SemanticWitness:
    values = dict(assignment)
    input_originals = set(relation.transfer.input_variables)
    output_originals = set(relation.transfer.output_variables)
    return SemanticWitness(
        input_state=tuple(
            sorted(
                (f"input:{canonical}", values[original])
                for canonical, original in relation.input_mapping.items()
            )
        ),
        output_state=tuple(
            sorted(
                (f"output:{canonical}", values[original])
                for canonical, original in relation.output_mapping.items()
            )
        ),
        local_state=tuple(
            (f"local:{name}", values[name])
            for name in sorted(set(values) - input_originals - output_originals)
        ),
    )


def query_bad_input(inputs: T33Inputs, row: tuple[int, ...]) -> BadInputQueryResult:
    """Decide one input and independently replay any exact SAT countermodel."""
    _validate_input_row(row)
    relation, solver = build_bad_input_solver(inputs)
    solver.add(
        *(
            relation.variables[relation.input_mapping[name]] == value
            for name, value in zip(P30_VARIABLES, row, strict=True)
        )
    )
    status = _solver_status(relation, solver, "exact bad-input query")
    if status == "UNSAT":
        return BadInputQueryResult("UNSAT", None, (), None)
    witness = _semantic_witness(
        relation,
        _canonical_assignment(relation, solver, "exact bad-input countermodel"),
    )
    replay = replay_bad_image_witness(inputs.t32_inputs.t31_inputs, witness)
    if replay.equation_residuals != (0,) * 12 or replay.q0_holds:
        raise EvidenceError("exact bad-input countermodel failed replay")
    return BadInputQueryResult(
        "SAT", witness, replay.equation_residuals, replay.q0_holds
    )


def exact_bad_input_status(inputs: T33Inputs, row: tuple[int, ...]) -> str:
    """Return the exact bad-input status after replaying any SAT witness."""
    return query_bad_input(inputs, row).status


def replay_promoted_rows(inputs: T33Inputs) -> tuple[str, ...]:
    """Replay all 18 promoted-input implications through fresh exact solvers."""
    return tuple(exact_bad_input_status(inputs, row) for row in inputs.promoted_rows)


def query_safe_conjunction(
    inputs: T33Inputs, atoms: tuple[ProjectionAtom, ...]
) -> RegionQueryRecord:
    """Return one immutable exact and independently replayed query record."""
    canonical = canonical_conjunction(atoms, allow_empty=True, maximum=6)
    relation, solver = build_bad_input_solver(inputs)
    solver.add(*(z3_safe_atom(relation, atom) for atom in canonical))
    status = _solver_status(relation, solver, "incremental safe-region query")
    if status == "UNSAT":
        return RegionQueryRecord.from_query(canonical, status="UNSAT")
    witness = _semantic_witness(
        relation,
        _canonical_assignment(relation, solver, "incremental countermodel"),
    )
    replay = replay_bad_image_witness(inputs.t32_inputs.t31_inputs, witness)
    if replay.equation_residuals != (0,) * 12 or replay.q0_holds:
        raise EvidenceError("incremental countermodel failed exact replay")
    return RegionQueryRecord.from_query(
        canonical,
        status="SAT",
        witness=witness,
        equation_residuals=replay.equation_residuals,
        q0_holds=replay.q0_holds,
    )


def verify_region_candidate(
    inputs: T33Inputs,
    seed_pair: SeedPair,
    pool: tuple[ProjectionAtom, ...],
    promoted_assignments: tuple[dict[str, int], ...],
    minimized: tuple[ProjectionAtom, ...],
    core_candidate: tuple[ProjectionAtom, ...],
    reduction: tuple[CoreReductionStep, ...],
    acquisition: RegionQueryRecord,
    fresh_acceptance: Callable[[tuple[ProjectionAtom, ...]], RegionQueryRecord],
) -> CandidateDecision:
    """Apply every finite and fresh-primary gate to one acquired safe core."""
    try:
        canonical_conjunction(minimized, allow_empty=False, maximum=6)
        canonical_conjunction(core_candidate, allow_empty=False, maximum=6)
    except ValueError as error:
        return CandidateDecision("REJECT", None, f"candidate grammar: {error}")
    if not set(core_candidate) <= set(pool):
        return CandidateDecision("REJECT", None, "candidate leaves its seed pool")
    if acquisition.status != "UNSAT" or acquisition.conjunction != core_candidate:
        return CandidateDecision("REJECT", None, "acquisition query differs")
    if not set(minimized) <= set(core_candidate):
        return CandidateDecision("REJECT", None, "minimized clause leaves its core")
    try:
        clause = SafeRegionClause(minimized)
    except ValueError as error:
        return CandidateDecision("REJECT", None, f"candidate clause: {error}")
    seed_assignments = tuple(
        dict(zip(P30_VARIABLES, row, strict=True)) for row in seed_pair.rows
    )
    if not all(evaluate_safe_clause(clause, assignment) for assignment in seed_assignments):
        return CandidateDecision("REJECT", None, "candidate does not cover both seeds")
    promoted_indices = tuple(
        index
        for index, assignment in enumerate(promoted_assignments)
        if evaluate_safe_clause(clause, assignment)
    )
    if len(promoted_indices) < 2 or not set(seed_pair.indices) <= set(promoted_indices):
        return CandidateDecision("REJECT", None, "candidate promoted coverage is too small")
    extent = clause_extent(clause)
    if extent < 4:
        return CandidateDecision("REJECT", None, "candidate bounded extent is below four")
    predicate = SafeRegionPredicate(30, P30_VARIABLES, (clause,))
    predicate_bytes, covered_table_bytes = compactness_bytes(
        predicate,
        tuple(inputs.promoted_rows[index] for index in promoted_indices),
    )
    if predicate_bytes >= covered_table_bytes:
        return CandidateDecision("REJECT", None, "candidate is not smaller than its row table")
    try:
        primary = fresh_acceptance(clause.atoms)
    except EvidenceError as error:
        return CandidateDecision("UNKNOWN", None, str(error))
    if primary.status != "UNSAT":
        return CandidateDecision("REJECT", None, "fresh primary query is not UNSAT")
    full_pool = generate_seed_pair_pool(*seed_pair.rows)
    pool_sha256 = hashlib.sha256(
        canonical_bytes([atom.to_payload() for atom in full_pool])
    ).hexdigest()
    candidate_sha256 = _conjunction_sha256(core_candidate)
    try:
        provenance = SafeRegionProvenance(
            clause=clause,
            seed_pair=seed_pair,
            pool_size=len(full_pool),
            pool_sha256=pool_sha256,
            solver_version=build_layer30_relation(
                inputs.t32_inputs.t31_inputs
            ).z3.get_version_string(),
            solver_parameters=(("phase_selection", 0), ("random_seed", 0)),
            core_candidate=core_candidate,
            core_candidate_sha256=candidate_sha256,
            acquisition_query_sha256=acquisition.conjunction_sha256,
            minimization_trace=reduction,
            promoted_indices=promoted_indices,
            bounded_extent=extent,
        )
    except ValueError as error:
        return CandidateDecision("REJECT", None, f"candidate provenance: {error}")
    return CandidateDecision("PASS", provenance, None)


def _milestone_payload(
    inputs: T33Inputs,
    clause: SafeRegionClause,
    provenance: SafeRegionProvenance,
    transcript: IncrementalSearchTranscript,
) -> dict[str, object]:
    source = dict(inputs.source_digests)
    return {
        "schema": "t33-base19-safe-region-milestone-v2",
        "status": "PASS",
        "source_digests": {
            name: source[name] for name in ("equations", "frontier", "provenances")
        },
        "t29_artifact_digests": dict(inputs.t29_artifact_digests),
        "t30_artifact_digests": dict(inputs.t30_artifact_digests),
        "t32_source_digests": dict(inputs.t32_source_digests),
        "t32_commits": list(inputs.t32_commits),
        "t32_design_sha256": inputs.t32_design_sha256,
        "t33_design_sha256": inputs.t33_design_sha256,
        "t33_restart_design_sha256": inputs.t33_restart_design_sha256,
        "clause": clause.to_payload(),
        "provenance": provenance.to_payload(),
        "seed_pair_count": len(transcript.pairs),
        "region_test_count": len(transcript.queries),
        "search_transcript": transcript.to_payload(),
        "primary_safety_status": "UNSAT",
    }


def milestone_result_payload(
    inputs: T33Inputs, result: FirstSafeRegionResult
) -> dict[str, object]:
    """Serialize one PASS or hard STOP with the complete frozen boundary."""
    source = dict(inputs.source_digests)
    payload: dict[str, object] = {
        "schema": "t33-base19-safe-region-milestone-v2",
        "status": result.status,
        "source_digests": {
            name: source[name] for name in ("equations", "frontier", "provenances")
        },
        "t29_artifact_digests": dict(inputs.t29_artifact_digests),
        "t30_artifact_digests": dict(inputs.t30_artifact_digests),
        "t32_source_digests": dict(inputs.t32_source_digests),
        "t32_commits": list(inputs.t32_commits),
        "t32_design_sha256": inputs.t32_design_sha256,
        "t33_design_sha256": inputs.t33_design_sha256,
        "t33_restart_design_sha256": inputs.t33_restart_design_sha256,
        "seed_pair_count": result.seed_pair_count,
        "region_test_count": result.region_test_count,
        "search_transcript": result.search_transcript.to_payload(),
        "primary_safety_status": result.primary_safety_status,
        "independent_status": result.independent_status,
        "stop_detail": result.stop_detail,
    }
    if result.status == "PASS":
        if result.clause is None or result.provenance is None:
            raise AssertionError("PASS result omitted its candidate")
        payload["clause"] = result.clause.to_payload()
        payload["provenance"] = result.provenance.to_payload()
    return payload


def _run_independent_milestone(
    inputs: T33Inputs,
    clause: SafeRegionClause,
    provenance: SafeRegionProvenance,
    transcript: IncrementalSearchTranscript,
) -> tuple[str, str | None]:
    repository_root = Path(__file__).resolve().parents[2]
    run_dir = repository_root / ".timeloop/runs"
    paths = (
        repository_root / "publication/base19-radial/instance/equations.json",
        repository_root
        / "publication/base19-radial/certificates/minimal-core-frontier.json",
        run_dir / "t27_base19_invariant_lift.json",
        run_dir / "t28_base19_tail_quotient.json",
        run_dir / "t28_base19_tail_quotient_independent.json",
        run_dir / "t29_base19_reachability_separator_trace.json",
        run_dir / "t29_base19_reachability_separator_dataset.json",
        run_dir / "t29_base19_reachability_separator.json",
        run_dir / "t29_base19_reachability_separator_certificate.json",
        run_dir / "t29_base19_reachability_separator_independent.json",
        run_dir / "t30_base19_exact_image_refinement.json",
        run_dir / "t30_base19_exact_image_refinement_certificate.json",
        run_dir / "t30_base19_exact_image_refinement_independent.json",
    )
    payload = _milestone_payload(inputs, clause, provenance, transcript)
    with tempfile.TemporaryDirectory(prefix="t33-safe-region-") as directory:
        candidate = Path(directory) / "candidate.json"
        candidate.write_bytes(canonical_bytes(payload) + b"\n")
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(run_dir / "t33_base19_safe_region_cover_independent.py"),
                "milestone",
                *(str(path) for path in paths),
                str(candidate),
            ],
            cwd=repository_root,
            text=True,
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        return "REJECT", completed.stderr.strip()
    try:
        audit = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return "REJECT", f"independent output is malformed: {error}"
    if (
        not isinstance(audit, dict)
        or audit.get("schema") != "t33-base19-safe-region-milestone-independent-v2"
        or audit.get("status") != "PASS"
        or audit.get("repository_imports") != []
        or audit.get("safety_status") != "UNSAT"
        or audit.get("seed_indices") != list(provenance.seed_pair.indices)
        or audit.get("promoted_indices") != list(provenance.promoted_indices)
        or audit.get("bounded_extent") != provenance.bounded_extent
        or audit.get("enumerated_input_count") != 77_824
        or audit.get("seed_pair_count") != len(transcript.pairs)
        or audit.get("region_test_count") != len(transcript.queries)
        or audit.get("query_record_count") != len(transcript.queries)
        or audit.get("transcript_status") != "PASS"
        or audit.get("t33_restart_design_sha256")
        != T33_RESTART_DESIGN_SHA256
    ):
        return "REJECT", "independent milestone gates differ"
    return "PASS", None


def _stop_first_region(
    status: str,
    budget: RegionSearchBudget,
    query_cache: dict[str, RegionQueryRecord],
    pair_traces: list[SeedPairSearchTrace],
    detail: str,
    *,
    primary_status: str | None = None,
    independent_status: str | None = None,
) -> FirstSafeRegionResult:
    transcript = IncrementalSearchTranscript(
        tuple(query_cache.values()), tuple(pair_traces)
    )
    return FirstSafeRegionResult(
        status=status,
        clause=None,
        provenance=None,
        seed_pair_count=budget.seed_pair_count,
        region_test_count=budget.region_test_count,
        primary_safety_status=primary_status,
        independent_status=independent_status,
        stop_detail=detail,
        search_transcript=transcript,
    )


_FIRST_REGION_CACHE: dict[tuple[int, int, int], FirstSafeRegionResult] = {}


def find_first_safe_region(
    inputs: T33Inputs,
    pair_limit: int = 153,
    region_limit: int = 2_000,
) -> FirstSafeRegionResult:
    """Find the first independently verified multi-input safe region."""
    cache_key = (id(inputs), pair_limit, region_limit)
    cached = _FIRST_REGION_CACHE.get(cache_key)
    if cached is not None:
        return cached
    budget = RegionSearchBudget(pair_limit, region_limit)
    query_cache: dict[str, RegionQueryRecord] = {}
    pair_traces: list[SeedPairSearchTrace] = []
    promoted_assignments = tuple(
        dict(zip(P30_VARIABLES, row, strict=True)) for row in inputs.promoted_rows
    )
    for first_index, second_index in itertools.combinations(range(18), 2):
        try:
            budget.enter_pair()
        except PairBudgetExhausted as error:
            result = _stop_first_region(
                "PAIR_BUDGET_EXHAUSTED",
                budget,
                query_cache,
                pair_traces,
                str(error),
            )
            _FIRST_REGION_CACHE[cache_key] = result
            return result
        seed_pair = SeedPair(
            (first_index, second_index),
            (inputs.promoted_rows[first_index], inputs.promoted_rows[second_index]),
        )
        pool = generate_seed_pair_pool(*seed_pair.rows)

        def verify(
            minimized: tuple[ProjectionAtom, ...],
            core_candidate: tuple[ProjectionAtom, ...],
            reduction: tuple[CoreReductionStep, ...],
            acquisition: RegionQueryRecord,
            fresh_acceptance: Callable[
                [tuple[ProjectionAtom, ...]], RegionQueryRecord
            ],
            _seed_pair: SeedPair = seed_pair,
            _pool: tuple[ProjectionAtom, ...] = pool,
        ) -> CandidateDecision:
            return verify_region_candidate(
                inputs,
                _seed_pair,
                _pool,
                promoted_assignments,
                minimized,
                core_candidate,
                reduction,
                acquisition,
                fresh_acceptance,
            )

        try:
            pair_result = countermodel_guided_search(
                seed_pair,
                pool,
                promoted_assignments,
                budget,
                query_cache,
                lambda atoms: query_safe_conjunction(inputs, atoms),
                verify,
            )
        except RegionBudgetExhausted as error:
            if error.trace is not None:
                pair_traces.append(error.trace)
            result = _stop_first_region(
                "REGION_BUDGET_EXHAUSTED",
                budget,
                query_cache,
                pair_traces,
                str(error),
            )
            _FIRST_REGION_CACHE[cache_key] = result
            return result
        except EvidenceError as error:
            result = _stop_first_region(
                "UNKNOWN", budget, query_cache, pair_traces, str(error)
            )
            _FIRST_REGION_CACHE[cache_key] = result
            return result
        pair_traces.append(pair_result.trace)
        if pair_result.status == "EXHAUSTED":
            continue
        if pair_result.status == "UNKNOWN":
            result = _stop_first_region(
                "UNKNOWN",
                budget,
                query_cache,
                pair_traces,
                pair_result.stop_detail or "pair search stopped without detail",
            )
            _FIRST_REGION_CACHE[cache_key] = result
            return result
        provenance = pair_result.provenance
        if provenance is None:
            raise AssertionError("pair-search PASS omitted provenance")
        clause = provenance.clause
        transcript = IncrementalSearchTranscript(
            tuple(query_cache.values()), tuple(pair_traces)
        )
        independent_status, detail = _run_independent_milestone(
            inputs, clause, provenance, transcript
        )
        if independent_status != "PASS":
            result = _stop_first_region(
                "INDEPENDENT_DISAGREEMENT",
                budget,
                query_cache,
                pair_traces,
                detail or "isolated milestone rejected the primary region",
                primary_status="UNSAT",
                independent_status=independent_status,
            )
            _FIRST_REGION_CACHE[cache_key] = result
            return result
        result = FirstSafeRegionResult(
            status="PASS",
            clause=clause,
            provenance=provenance,
            seed_pair_count=budget.seed_pair_count,
            region_test_count=budget.region_test_count,
            primary_safety_status="UNSAT",
            independent_status="PASS",
            stop_detail=None,
            search_transcript=transcript,
        )
        _FIRST_REGION_CACHE[cache_key] = result
        return result
    result = _stop_first_region(
        "NO_SAFE_REGION",
        budget,
        query_cache,
        pair_traces,
        "no safe region exists in the bounded seed-pair search",
    )
    _FIRST_REGION_CACHE[cache_key] = result
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("milestone", help="run the first safe-region milestone")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "milestone":
        raise EvidenceError(f"unsupported command: {args.command}")
    inputs = load_t33_inputs(Path(__file__).resolve().parents[2])
    result = find_first_safe_region(inputs)
    print(canonical_bytes(milestone_result_payload(inputs, result)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
