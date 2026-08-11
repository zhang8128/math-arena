"""Typed certificates and finite grammar for the base-19 safe-region cover."""

from __future__ import annotations

import hashlib
import itertools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

from lychrel_bad_image_projection import P30_VARIABLES, ProjectionAtom
from lychrel_invariant_certificate import canonical_bytes
from lychrel_reachability_separator import SemanticWitness

_SCHEMA = "t33-base19-safe-region-cover-certificate-v1"
_PASS = "SAFE_REGION_COVER_PASS"
_REMOVED = "phase=0,n=0,column=82"
_SOURCE_NAMES = {"equations", "frontier", "provenances"}
_T29_NAMES = {"evidence", "trace", "dataset", "certificate", "independent"}
_T30_NAMES = {"evidence", "certificate", "independent", "report"}
_T32_NAMES = {"library", "runner", "independent", "test"}
_T32_COMMITS = ("df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_digest(value: object, context: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{context} must be a lowercase SHA-256")


def _validate_digest_map(
    entries: tuple[tuple[str, str], ...], names: set[str], context: str
) -> None:
    if tuple(sorted(entries)) != entries or len(entries) != len(names):
        raise ValueError(f"{context} digest names differ")
    if set(dict(entries)) != names:
        raise ValueError(f"{context} digest names differ")
    for name, digest in entries:
        _validate_digest(digest, f"{context} digest {name}")


def _validate_atom(atom: ProjectionAtom, context: str) -> None:
    if len(atom.terms) > 2:
        raise ValueError(f"{context} support exceeds two variables")
    outside = sorted(name for name, _ in atom.terms if name not in P30_VARIABLES)
    if outside:
        raise ValueError(f"{context} variable scope differs: {outside}")
    if any(abs(coefficient) > 3 for _, coefficient in atom.terms):
        raise ValueError(f"{context} coefficient magnitude exceeds three")
    if atom.relation == "congruent" and (
        atom.modulus is None or not 2 <= atom.modulus <= 19
    ):
        raise ValueError(f"{context} congruence modulus differs")


@dataclass(frozen=True)
class SafeRegionClause:
    atoms: tuple[ProjectionAtom, ...]

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("a safe-region clause must contain at least one atom")
        if len(self.atoms) > 6:
            raise ValueError("a safe-region clause may contain at most six atoms")
        if len(set(self.atoms)) != len(self.atoms):
            raise ValueError("a safe-region clause may not repeat an atom")
        for atom in self.atoms:
            if not isinstance(atom, ProjectionAtom):
                raise ValueError("safe-region clause entries must be projection atoms")
            _validate_atom(atom, "safe-region atom")
        object.__setattr__(self, "atoms", tuple(sorted(self.atoms, key=canonical_bytes)))

    def to_payload(self) -> dict[str, object]:
        return {"atoms": [atom.to_payload() for atom in self.atoms]}


@dataclass(frozen=True)
class SafeRegionPredicate:
    layer: int
    variables: tuple[str, ...]
    clauses: tuple[SafeRegionClause, ...]

    def __post_init__(self) -> None:
        if self.layer != 30:
            raise ValueError("safe-region predicate must be at layer 30")
        if self.variables != P30_VARIABLES:
            raise ValueError("safe-region predicate variable scope differs")
        if not self.clauses:
            raise ValueError("safe-region predicate must contain a clause")
        if len(self.clauses) > 6:
            raise ValueError("safe-region predicate may contain at most six clauses")
        if len(set(self.clauses)) != len(self.clauses):
            raise ValueError("safe-region predicate may not repeat a clause")
        if any(not isinstance(clause, SafeRegionClause) for clause in self.clauses):
            raise ValueError("safe-region predicate entries must be clauses")
        object.__setattr__(
            self, "clauses", tuple(sorted(self.clauses, key=canonical_bytes))
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "variables": list(self.variables),
            "clauses": [clause.to_payload() for clause in self.clauses],
        }


def _validate_assignment(assignment: Mapping[str, int]) -> None:
    if set(assignment) != set(P30_VARIABLES):
        raise ValueError("layer-30 assignment keys differ")
    for name in P30_VARIABLES:
        value = assignment[name]
        if not _is_int(value):
            raise ValueError(f"layer-30 assignment {name} must be an integer")
        if name == "D0":
            if not 0 <= value < 19:
                raise ValueError("layer-30 D0 must be in 0..18")
        elif value not in {0, 1}:
            raise ValueError(f"layer-30 carry {name} must be zero or one")


def _atom_holds(atom: ProjectionAtom, assignment: Mapping[str, int]) -> bool:
    total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def evaluate_safe_atom(atom: ProjectionAtom, assignment: Mapping[str, int]) -> bool:
    """Evaluate one strict T33 atom on a complete bounded input."""
    _validate_atom(atom, "safe-region atom")
    _validate_assignment(assignment)
    return _atom_holds(atom, assignment)


def canonical_conjunction(
    atoms: tuple[ProjectionAtom, ...], *, allow_empty: bool, maximum: int
) -> tuple[ProjectionAtom, ...]:
    """Return a validated canonical conjunction without silently deduplicating."""
    if not _is_int(maximum) or not 0 <= maximum <= 6:
        raise ValueError("conjunction maximum must be in 0..6")
    if not atoms and not allow_empty:
        raise ValueError("query conjunction must be nonempty")
    if len(atoms) > maximum:
        if maximum == 6:
            raise ValueError("query conjunction may contain at most six atoms")
        raise ValueError(f"query conjunction may contain at most {maximum} atoms")
    if len(set(atoms)) != len(atoms):
        raise ValueError("query conjunction must be canonical and distinct")
    for atom in atoms:
        if not isinstance(atom, ProjectionAtom):
            raise ValueError("query conjunction entries must be projection atoms")
        _validate_atom(atom, "query atom")
    canonical = tuple(sorted(atoms, key=canonical_bytes))
    if canonical != atoms:
        raise ValueError("query conjunction must be canonical and distinct")
    return canonical


def canonical_union(
    conjunction: tuple[ProjectionAtom, ...], atom: ProjectionAtom
) -> tuple[ProjectionAtom, ...]:
    """Add one absent atom to a bounded conjunction in canonical order."""
    canonical_conjunction(conjunction, allow_empty=True, maximum=6)
    if atom in conjunction:
        raise ValueError("query conjunction already contains branch atom")
    return tuple(sorted((*conjunction, atom), key=canonical_bytes))


def evaluate_safe_clause(
    clause: SafeRegionClause, assignment: Mapping[str, int]
) -> bool:
    """Evaluate one strict T33 clause on a complete bounded input."""
    _validate_assignment(assignment)
    return all(_atom_holds(atom, assignment) for atom in clause.atoms)


def evaluate_safe_predicate(
    predicate: SafeRegionPredicate, assignment: Mapping[str, int]
) -> int | None:
    """Return the first matching canonical clause index, or ``None``."""
    _validate_assignment(assignment)
    for index, clause in enumerate(predicate.clauses):
        if all(_atom_holds(atom, assignment) for atom in clause.atoms):
            return index
    return None


@cache
def bounded_layer30_rows() -> tuple[tuple[int, ...], ...]:
    """Return the exact 2^12 * 19 layer-30 input domain in canonical order."""
    return tuple(
        (*carries, digit)
        for carries in itertools.product((0, 1), repeat=12)
        for digit in range(19)
    )


@cache
def clause_extent(clause: SafeRegionClause) -> int:
    """Count bounded assignments satisfying a clause without table materialization."""
    used = tuple(
        name
        for name in P30_VARIABLES
        if any(name == term_name for atom in clause.atoms for term_name, _ in atom.terms)
    )
    domains = tuple(range(19) if name == "D0" else (0, 1) for name in used)
    satisfying = 0
    assignment = {name: 0 for name in P30_VARIABLES}
    for values in itertools.product(*domains):
        assignment.update(zip(used, values, strict=True))
        if all(_atom_holds(atom, assignment) for atom in clause.atoms):
            satisfying += 1
    free_multiplier = math.prod(
        19 if name == "D0" else 2 for name in P30_VARIABLES if name not in used
    )
    return satisfying * free_multiplier


def first_match_ownership(
    predicate: SafeRegionPredicate, promoted_rows: tuple[tuple[int, ...], ...]
) -> tuple[tuple[int, ...], ...]:
    """Return promoted-row indices owned by each canonical first-match clause."""
    owned: list[list[int]] = [[] for _ in predicate.clauses]
    for index, row in enumerate(promoted_rows):
        if len(row) != len(P30_VARIABLES):
            raise ValueError("promoted row width differs")
        owner = evaluate_safe_predicate(
            predicate, dict(zip(P30_VARIABLES, row, strict=True))
        )
        if owner is not None:
            owned[owner].append(index)
    return tuple(tuple(indices) for indices in owned)


def compactness_bytes(
    predicate: SafeRegionPredicate, promoted_rows: tuple[tuple[int, ...], ...]
) -> tuple[int, int]:
    """Measure the canonical predicate and explicit promoted-row table."""
    if any(len(row) != len(P30_VARIABLES) for row in promoted_rows):
        raise ValueError("promoted row width differs")
    table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(row) for row in promoted_rows],
    }
    return len(canonical_bytes(predicate.to_payload())), len(canonical_bytes(table))


def _linear_value(
    terms: tuple[tuple[str, int], ...], assignment: Mapping[str, int]
) -> int:
    return sum(coefficient * assignment[name] for name, coefficient in terms)


def _primitive_forms() -> tuple[tuple[tuple[str, int], ...], ...]:
    forms: list[tuple[tuple[str, int], ...]] = []
    coefficients = (-3, -2, -1, 1, 2, 3)
    for support in (1, 2):
        for names in itertools.combinations(P30_VARIABLES, support):
            for selected in itertools.product(coefficients, repeat=support):
                if math.gcd(*(abs(value) for value in selected)) != 1:
                    continue
                forms.append(tuple(zip(names, selected, strict=True)))
    return tuple(forms)


@cache
def generate_seed_pair_pool(
    first: tuple[int, ...], second: tuple[int, ...]
) -> tuple[ProjectionAtom, ...]:
    """Generate the complete normalized T33 atom pool for two seed rows."""
    if len(first) != len(P30_VARIABLES) or len(second) != len(P30_VARIABLES):
        raise ValueError("seed-pair row width differs")
    if first == second:
        raise ValueError("seed-pair rows must be distinct")
    first_assignment = dict(zip(P30_VARIABLES, first, strict=True))
    second_assignment = dict(zip(P30_VARIABLES, second, strict=True))
    _validate_assignment(first_assignment)
    _validate_assignment(second_assignment)
    atoms: set[ProjectionAtom] = set()
    for terms in _primitive_forms():
        first_value = _linear_value(terms, first_assignment)
        second_value = _linear_value(terms, second_assignment)
        if first_value == second_value:
            atoms.add(ProjectionAtom("eq", terms, first_value))
        atoms.add(ProjectionAtom("le", terms, max(first_value, second_value)))
        negated = tuple((name, -coefficient) for name, coefficient in terms)
        atoms.add(ProjectionAtom("le", negated, -min(first_value, second_value)))
        for modulus in range(2, 20):
            if (first_value - second_value) % modulus == 0:
                try:
                    atoms.add(
                        ProjectionAtom(
                            "congruent", terms, first_value % modulus, modulus
                        )
                    )
                except ValueError:
                    continue
    result = []
    for atom in sorted(atoms, key=canonical_bytes):
        try:
            clause = SafeRegionClause((atom,))
        except ValueError:
            continue
        if clause_extent(clause) < 77_824:
            result.append(atom)
    return tuple(result)


@dataclass(frozen=True)
class SeedPair:
    indices: tuple[int, int]
    rows: tuple[tuple[int, ...], tuple[int, ...]]

    def __post_init__(self) -> None:
        if (
            len(self.indices) != 2
            or any(not _is_int(index) for index in self.indices)
            or not 0 <= self.indices[0] < self.indices[1] < 18
        ):
            raise ValueError("seed-pair indices must be ordered in 0..17")
        if len(self.rows) != 2 or self.rows[0] == self.rows[1]:
            raise ValueError("seed-pair rows must be distinct")
        for row in self.rows:
            if len(row) != len(P30_VARIABLES):
                raise ValueError("seed-pair row width differs")
            _validate_assignment(dict(zip(P30_VARIABLES, row, strict=True)))

    def to_payload(self) -> dict[str, object]:
        return {
            "indices": list(self.indices),
            "rows": [list(row) for row in self.rows],
        }


@dataclass(frozen=True)
class CoreReductionStep:
    removed_atom_sha256: str
    candidate_sha256: str
    status: str
    retained: bool

    def __post_init__(self) -> None:
        _validate_digest(self.removed_atom_sha256, "removed-atom digest")
        _validate_digest(self.candidate_sha256, "reduced-candidate digest")
        if self.status not in {"SAT", "UNSAT"}:
            raise ValueError("core-reduction status must be SAT or UNSAT")
        if not isinstance(self.retained, bool):
            raise ValueError("core-reduction retained flag must be Boolean")
        if self.retained != (self.status == "SAT"):
            raise ValueError("core-reduction retained flag disagrees with status")

    def to_payload(self) -> dict[str, object]:
        return {
            "removed_atom_sha256": self.removed_atom_sha256,
            "candidate_sha256": self.candidate_sha256,
            "status": self.status,
            "retained": self.retained,
        }


def _conjunction_digest(conjunction: tuple[ProjectionAtom, ...]) -> str:
    return hashlib.sha256(
        canonical_bytes([atom.to_payload() for atom in conjunction])
    ).hexdigest()


@dataclass(frozen=True)
class RegionQueryRecord:
    conjunction: tuple[ProjectionAtom, ...]
    conjunction_sha256: str
    status: str
    witness: SemanticWitness | None
    equation_residuals: tuple[int, ...]
    q0_holds: bool | None

    def __post_init__(self) -> None:
        canonical_conjunction(self.conjunction, allow_empty=True, maximum=6)
        _validate_digest(self.conjunction_sha256, "query conjunction digest")
        if self.conjunction_sha256 != _conjunction_digest(self.conjunction):
            raise ValueError("query conjunction digest differs")
        if self.status == "SAT":
            if (
                not isinstance(self.witness, SemanticWitness)
                or self.equation_residuals != (0,) * 12
                or self.q0_holds is not False
            ):
                raise ValueError("SAT query requires an exact non-Q0 witness")
        elif self.status == "UNSAT":
            if (
                self.witness is not None
                or self.equation_residuals
                or self.q0_holds is not None
            ):
                raise ValueError("UNSAT query forbids witness replay fields")
        else:
            raise ValueError("query status must be SAT or UNSAT")

    @classmethod
    def from_query(
        cls,
        conjunction: tuple[ProjectionAtom, ...],
        *,
        status: str,
        witness: SemanticWitness | None = None,
        equation_residuals: tuple[int, ...] = (),
        q0_holds: bool | None = None,
    ) -> RegionQueryRecord:
        canonical = canonical_conjunction(
            conjunction, allow_empty=True, maximum=6
        )
        return cls(
            canonical,
            _conjunction_digest(canonical),
            status,
            witness,
            equation_residuals,
            q0_holds,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "conjunction": [
                hashlib.sha256(canonical_bytes(atom)).hexdigest()
                for atom in self.conjunction
            ],
            "conjunction_sha256": self.conjunction_sha256,
            "status": self.status,
            "witness": None if self.witness is None else self.witness.to_payload(),
            "equation_residuals": list(self.equation_residuals),
            "q0_holds": self.q0_holds,
        }


@dataclass(frozen=True)
class SearchVisit:
    purpose: str
    parent_sha256: str | None
    query_sha256: str
    fresh_query: bool
    violated_atom_sha256s: tuple[str, ...]
    branch_atom_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.purpose not in {
            "ROOT",
            "SEARCH",
            "REDUCTION",
            "ACCEPTANCE_REPLAY",
        }:
            raise ValueError("search-visit purpose differs")
        if self.parent_sha256 is not None:
            _validate_digest(self.parent_sha256, "search-visit parent digest")
        _validate_digest(self.query_sha256, "search-visit query digest")
        if not isinstance(self.fresh_query, bool):
            raise ValueError("search-visit fresh-query flag must be Boolean")
        for digest in (*self.violated_atom_sha256s, *self.branch_atom_sha256s):
            _validate_digest(digest, "search-visit atom digest")
        if (
            len(set(self.violated_atom_sha256s))
            != len(self.violated_atom_sha256s)
            or len(set(self.branch_atom_sha256s))
            != len(self.branch_atom_sha256s)
            or set(self.violated_atom_sha256s) != set(self.branch_atom_sha256s)
        ):
            raise ValueError("search-visit branch atoms differ from violated atoms")

    def to_payload(self) -> dict[str, object]:
        return {
            "purpose": self.purpose,
            "parent_sha256": self.parent_sha256,
            "query_sha256": self.query_sha256,
            "fresh_query": self.fresh_query,
            "violated_atom_sha256s": list(self.violated_atom_sha256s),
            "branch_atom_sha256s": list(self.branch_atom_sha256s),
        }


@dataclass(frozen=True)
class SeedPairSearchTrace:
    seed_pair: SeedPair
    pool_size: int
    pool_sha256: str
    visits: tuple[SearchVisit, ...]

    def __post_init__(self) -> None:
        pool = generate_seed_pair_pool(*self.seed_pair.rows)
        if self.pool_size != len(pool):
            raise ValueError("search-trace pool size differs from its seeds")
        _validate_digest(self.pool_sha256, "search-trace pool digest")
        actual_digest = hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in pool])
        ).hexdigest()
        if self.pool_sha256 != actual_digest:
            raise ValueError("search-trace pool digest differs from its seeds")
        if not self.visits or any(
            not isinstance(visit, SearchVisit) for visit in self.visits
        ):
            raise ValueError("search trace must contain visits")
        pool_digests = {
            hashlib.sha256(canonical_bytes(atom)).hexdigest() for atom in pool
        }
        if any(
            digest not in pool_digests
            for visit in self.visits
            for digest in (
                *visit.violated_atom_sha256s,
                *visit.branch_atom_sha256s,
            )
        ):
            raise ValueError("search visit names an atom outside the seed pool")

    def to_payload(self) -> dict[str, object]:
        return {
            "seed_pair": self.seed_pair.to_payload(),
            "pool_size": self.pool_size,
            "pool_sha256": self.pool_sha256,
            "visits": [visit.to_payload() for visit in self.visits],
        }


@dataclass(frozen=True)
class IncrementalSearchTranscript:
    queries: tuple[RegionQueryRecord, ...]
    pairs: tuple[SeedPairSearchTrace, ...]

    def __post_init__(self) -> None:
        if not self.queries or not self.pairs:
            raise ValueError("incremental transcript must contain queries and pairs")
        if len({query.conjunction_sha256 for query in self.queries}) != len(
            self.queries
        ):
            raise ValueError("incremental transcript repeats a query")
        if tuple(pair.seed_pair.indices for pair in self.pairs) != tuple(
            sorted(pair.seed_pair.indices for pair in self.pairs)
        ) or len({pair.seed_pair.indices for pair in self.pairs}) != len(self.pairs):
            raise ValueError("incremental transcript seed pairs are not ordered")
        query_by_digest = {
            query.conjunction_sha256: query for query in self.queries
        }
        fresh_digests = []
        for pair in self.pairs:
            pool = set(generate_seed_pair_pool(*pair.seed_pair.rows))
            seen_in_pair: set[str] = set()
            for visit in pair.visits:
                query = query_by_digest.get(visit.query_sha256)
                if query is None:
                    raise ValueError("search visit does not resolve to a query record")
                if not set(query.conjunction) <= pool:
                    raise ValueError("search query contains an atom outside the seed pool")
                if visit.parent_sha256 is not None and (
                    visit.parent_sha256 not in query_by_digest
                    or visit.parent_sha256 not in seen_in_pair
                ):
                    raise ValueError("search-visit parent does not resolve earlier")
                if query.status == "UNSAT" and (
                    visit.violated_atom_sha256s or visit.branch_atom_sha256s
                ):
                    raise ValueError("UNSAT search visit cannot carry branch atoms")
                if visit.fresh_query:
                    fresh_digests.append(visit.query_sha256)
                seen_in_pair.add(visit.query_sha256)
        if tuple(fresh_digests) != tuple(
            query.conjunction_sha256 for query in self.queries
        ) or len(set(fresh_digests)) != len(fresh_digests):
            raise ValueError("each query must have exactly one fresh visit in first-query order")

    def to_payload(self) -> dict[str, object]:
        return {
            "queries": [query.to_payload() for query in self.queries],
            "pairs": [pair.to_payload() for pair in self.pairs],
        }


@dataclass(frozen=True)
class SafeRegionProvenance:
    clause: SafeRegionClause
    seed_pair: SeedPair
    pool_size: int
    pool_sha256: str
    solver_version: str
    solver_parameters: tuple[tuple[str, int], ...]
    core_candidate: tuple[ProjectionAtom, ...]
    core_candidate_sha256: str
    acquisition_query_sha256: str
    minimization_trace: tuple[CoreReductionStep, ...]
    promoted_indices: tuple[int, ...]
    bounded_extent: int

    def __post_init__(self) -> None:
        if not _is_int(self.pool_size) or self.pool_size < len(self.core_candidate):
            raise ValueError("safe-region pool size differs")
        _validate_digest(self.pool_sha256, "safe-region pool digest")
        regenerated_pool = generate_seed_pair_pool(*self.seed_pair.rows)
        if self.pool_size != len(regenerated_pool):
            raise ValueError("safe-region pool size differs from its seeds")
        regenerated_digest = hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in regenerated_pool])
        ).hexdigest()
        if self.pool_sha256 != regenerated_digest:
            raise ValueError("safe-region pool digest differs from its seeds")
        if not isinstance(self.solver_version, str) or not self.solver_version:
            raise ValueError("safe-region solver version must be nonempty")
        if tuple(sorted(self.solver_parameters)) != self.solver_parameters or any(
            not isinstance(name, str) or not name or not _is_int(value)
            for name, value in self.solver_parameters
        ):
            raise ValueError("safe-region solver parameters differ")
        canonical_conjunction(self.core_candidate, allow_empty=False, maximum=6)
        if not set(self.core_candidate) <= set(regenerated_pool):
            raise ValueError("core candidate contains an atom outside the seed pool")
        _validate_digest(self.core_candidate_sha256, "core-candidate digest")
        actual_core = hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in self.core_candidate])
        ).hexdigest()
        if self.core_candidate_sha256 != actual_core:
            raise ValueError("core-candidate digest differs")
        _validate_digest(self.acquisition_query_sha256, "acquisition query digest")
        if self.acquisition_query_sha256 != actual_core:
            raise ValueError("acquisition query digest differs from core candidate")
        if not set(self.clause.atoms) <= set(self.core_candidate):
            raise ValueError("safe-region clause is not a subset of its core candidate")
        if not self.minimization_trace:
            raise ValueError("safe-region minimization trace must be nonempty")
        core_digests = {
            hashlib.sha256(canonical_bytes(atom)).hexdigest()
            for atom in self.core_candidate
        }
        if any(
            step.removed_atom_sha256 not in core_digests
            for step in self.minimization_trace
        ):
            raise ValueError("minimization trace names an atom outside the core")
        if (
            tuple(sorted(set(self.promoted_indices))) != self.promoted_indices
            or len(self.promoted_indices) < 2
            or any(not _is_int(index) or not 0 <= index < 18 for index in self.promoted_indices)
        ):
            raise ValueError("safe-region promoted indices differ")
        if not set(self.seed_pair.indices) <= set(self.promoted_indices):
            raise ValueError("safe-region seeds are not covered")
        if not _is_int(self.bounded_extent) or self.bounded_extent < 4:
            raise ValueError("safe-region bounded extent must be at least four")

    def to_payload(self) -> dict[str, object]:
        return {
            "clause": self.clause.to_payload(),
            "seed_pair": self.seed_pair.to_payload(),
            "pool_size": self.pool_size,
            "pool_sha256": self.pool_sha256,
            "solver_version": self.solver_version,
            "solver_parameters": [list(item) for item in self.solver_parameters],
            "core_candidate": [atom.to_payload() for atom in self.core_candidate],
            "core_candidate_sha256": self.core_candidate_sha256,
            "acquisition_query_sha256": self.acquisition_query_sha256,
            "minimization_trace": [step.to_payload() for step in self.minimization_trace],
            "promoted_indices": list(self.promoted_indices),
            "bounded_extent": self.bounded_extent,
        }


@dataclass(frozen=True)
class SafeRegionCoverCertificate:
    schema: str
    status: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t32_source_digests: tuple[tuple[str, str], ...]
    t32_commits: tuple[str, ...]
    t32_design_sha256: str
    t33_design_sha256: str
    t32_first_type_status: str
    t32_first_type_sha256: str
    t32_first_type_inspected_witness_count: int
    t32_first_type_tested_candidate_count: int
    t32_family_status: str
    t32_family_inspected_witness_count: int
    t32_family_tested_candidate_count: int
    predicate: SafeRegionPredicate
    provenances: tuple[SafeRegionProvenance, ...]
    seed_pair_count: int
    region_test_count: int
    cover_candidate_count: int
    promoted_count: int
    promoted_sha256: str
    promoted_coverage: tuple[int, ...]
    first_match_ownership: tuple[tuple[int, ...], ...]
    clause_extents: tuple[int, ...]
    predicate_extent: int
    predicate_bytes: int
    promoted_table_bytes: int
    clause_safety_statuses: tuple[str, ...]
    primary_safety_status: str
    independent_status: str
    enumerated_input_count: int

    def __post_init__(self) -> None:
        if self.schema != _SCHEMA:
            raise ValueError("unsupported safe-region certificate schema")
        if self.status != _PASS:
            raise ValueError("safe-region certificate status must be PASS")
        if self.base != 19 or self.removed != _REMOVED:
            raise ValueError("safe-region base or removed coordinate differs")
        _validate_digest_map(self.source_digests, _SOURCE_NAMES, "source")
        _validate_digest_map(self.t29_artifact_digests, _T29_NAMES, "T29 artifact")
        _validate_digest_map(self.t30_artifact_digests, _T30_NAMES, "T30 artifact")
        _validate_digest_map(self.t32_source_digests, _T32_NAMES, "T32 source")
        if self.t32_commits != _T32_COMMITS:
            raise ValueError("T32 commits differ")
        _validate_digest(self.t32_design_sha256, "T32 design digest")
        _validate_digest(self.t33_design_sha256, "T33 design digest")
        if (
            self.t32_first_type_status != "PASS"
            or self.t32_first_type_inspected_witness_count != 3
            or self.t32_first_type_tested_candidate_count != 31
        ):
            raise ValueError("T32 first-type replay differs")
        _validate_digest(self.t32_first_type_sha256, "T32 first-type digest")
        if (
            self.t32_family_status != "CANDIDATE_BUDGET_EXHAUSTED"
            or self.t32_family_inspected_witness_count != 8
            or self.t32_family_tested_candidate_count != 10_000
        ):
            raise ValueError("T32 family replay differs")
        if len(self.provenances) != len(self.predicate.clauses):
            raise ValueError("safe-region provenance count differs")
        if tuple(item.clause for item in self.provenances) != self.predicate.clauses:
            raise ValueError("safe-region provenances differ from predicate clauses")
        if not _is_int(self.seed_pair_count) or not 1 <= self.seed_pair_count <= 153:
            raise ValueError("seed-pair count is outside 1..153")
        if not _is_int(self.region_test_count) or not 1 <= self.region_test_count <= 5_000:
            raise ValueError("region-test count is outside 1..5,000")
        if (
            not _is_int(self.cover_candidate_count)
            or not 1 <= self.cover_candidate_count <= 10_000
        ):
            raise ValueError("cover-candidate count is outside 1..10,000")
        if self.promoted_count != 18:
            raise ValueError("certificate requires 18 promoted rows")
        _validate_digest(self.promoted_sha256, "promoted-row digest")
        if self.promoted_coverage != tuple(range(18)):
            raise ValueError("promoted coverage must contain all 18 rows")
        if len(self.first_match_ownership) != len(self.predicate.clauses):
            raise ValueError("first-match ownership count differs")
        if any(len(indices) < 2 for indices in self.first_match_ownership):
            raise ValueError("each clause must own at least two promoted rows")
        flattened = tuple(
            index for indices in self.first_match_ownership for index in indices
        )
        if tuple(sorted(flattened)) != tuple(range(18)) or len(set(flattened)) != 18:
            raise ValueError("first-match ownership must partition promoted rows")
        if tuple(item.promoted_indices for item in self.provenances) != tuple(
            tuple(
                index
                for index in range(18)
                if index in set(item.promoted_indices)
            )
            for item in self.provenances
        ):
            raise ValueError("provenance promoted indices are not canonical")
        if set().union(*(set(item.promoted_indices) for item in self.provenances)) != set(
            range(18)
        ):
            raise ValueError("provenance coverage differs")
        if self.clause_extents != tuple(
            provenance.bounded_extent for provenance in self.provenances
        ) or any(extent < 4 for extent in self.clause_extents):
            raise ValueError("clause extent records differ")
        if not _is_int(self.predicate_extent) or not 4 <= self.predicate_extent <= 77_824:
            raise ValueError("predicate extent differs")
        if self.promoted_table_bytes != 616 or self.predicate_bytes >= 616:
            raise ValueError("predicate must be smaller than the 616-byte table")
        actual_predicate_bytes = len(canonical_bytes(self.predicate.to_payload()))
        if self.predicate_bytes != actual_predicate_bytes:
            raise ValueError("predicate byte count differs")
        if self.clause_safety_statuses != ("UNSAT",) * len(self.predicate.clauses):
            raise ValueError("clause safety statuses differ")
        if self.primary_safety_status != "UNSAT":
            raise ValueError("primary safety status must be UNSAT")
        if self.independent_status != "PASS":
            raise ValueError("independent status must be PASS")
        if self.enumerated_input_count != 77_824:
            raise ValueError("certificate requires 77,824 enumerated inputs")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "t29_artifact_digests": dict(self.t29_artifact_digests),
            "t30_artifact_digests": dict(self.t30_artifact_digests),
            "t32_source_digests": dict(self.t32_source_digests),
            "t32_commits": list(self.t32_commits),
            "t32_design_sha256": self.t32_design_sha256,
            "t33_design_sha256": self.t33_design_sha256,
            "t32_first_type_status": self.t32_first_type_status,
            "t32_first_type_sha256": self.t32_first_type_sha256,
            "t32_first_type_inspected_witness_count": self.t32_first_type_inspected_witness_count,
            "t32_first_type_tested_candidate_count": self.t32_first_type_tested_candidate_count,
            "t32_family_status": self.t32_family_status,
            "t32_family_inspected_witness_count": self.t32_family_inspected_witness_count,
            "t32_family_tested_candidate_count": self.t32_family_tested_candidate_count,
            "predicate": self.predicate.to_payload(),
            "provenances": [item.to_payload() for item in self.provenances],
            "seed_pair_count": self.seed_pair_count,
            "region_test_count": self.region_test_count,
            "cover_candidate_count": self.cover_candidate_count,
            "promoted_count": self.promoted_count,
            "promoted_sha256": self.promoted_sha256,
            "promoted_coverage": list(self.promoted_coverage),
            "first_match_ownership": [list(item) for item in self.first_match_ownership],
            "clause_extents": list(self.clause_extents),
            "predicate_extent": self.predicate_extent,
            "predicate_bytes": self.predicate_bytes,
            "promoted_table_bytes": self.promoted_table_bytes,
            "clause_safety_statuses": list(self.clause_safety_statuses),
            "primary_safety_status": self.primary_safety_status,
            "independent_status": self.independent_status,
            "enumerated_input_count": self.enumerated_input_count,
        }


def _require_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys differ")


def _parse_digest_map(
    value: object, names: set[str], context: str
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} digests must be an object")
    entries = tuple(sorted((str(name), digest) for name, digest in value.items()))
    if any(not isinstance(digest, str) for _, digest in entries):
        raise ValueError(f"{context} digests must be strings")
    result = tuple((name, digest) for name, digest in entries)
    _validate_digest_map(result, names, context)
    return result


def _parse_atom(value: object) -> ProjectionAtom:
    if not isinstance(value, Mapping):
        raise ValueError("safe-region atom must be an object")
    relation = value.get("relation")
    expected = {"relation", "terms", "constant"}
    if relation == "congruent":
        expected.add("modulus")
    _require_keys(value, expected, "safe-region atom")
    terms_value = value["terms"]
    if not isinstance(terms_value, list):
        raise ValueError("safe-region atom terms must be a list")
    terms: list[tuple[str, int]] = []
    for term in terms_value:
        if (
            not isinstance(term, list)
            or len(term) != 2
            or not isinstance(term[0], str)
            or not _is_int(term[1])
        ):
            raise ValueError("safe-region atom term is malformed")
        terms.append((term[0], term[1]))
    if not isinstance(relation, str) or not _is_int(value["constant"]):
        raise ValueError("safe-region atom relation or constant is malformed")
    modulus = value.get("modulus")
    if modulus is not None and not _is_int(modulus):
        raise ValueError("safe-region atom modulus is malformed")
    atom = ProjectionAtom(relation, tuple(terms), value["constant"], modulus)
    _validate_atom(atom, "safe-region atom")
    if atom.to_payload() != dict(value):
        raise ValueError("safe-region atom is not canonical")
    return atom


def _parse_clause(value: object) -> SafeRegionClause:
    if not isinstance(value, Mapping):
        raise ValueError("safe-region clause must be an object")
    _require_keys(value, {"atoms"}, "safe-region clause")
    atoms = value["atoms"]
    if not isinstance(atoms, list):
        raise ValueError("safe-region clause atoms must be a list")
    clause = SafeRegionClause(tuple(_parse_atom(atom) for atom in atoms))
    if clause.to_payload() != dict(value):
        raise ValueError("safe-region clause is not canonical")
    return clause


def _parse_predicate(value: object) -> SafeRegionPredicate:
    if not isinstance(value, Mapping):
        raise ValueError("safe-region predicate must be an object")
    _require_keys(value, {"layer", "variables", "clauses"}, "safe-region predicate")
    variables = value["variables"]
    clauses = value["clauses"]
    if not _is_int(value["layer"]) or not isinstance(variables, list) or not all(
        isinstance(name, str) for name in variables
    ):
        raise ValueError("safe-region predicate header is malformed")
    if not isinstance(clauses, list):
        raise ValueError("safe-region predicate clauses must be a list")
    predicate = SafeRegionPredicate(
        value["layer"], tuple(variables), tuple(_parse_clause(item) for item in clauses)
    )
    if predicate.to_payload() != dict(value):
        raise ValueError("safe-region predicate is not canonical")
    return predicate


def _parse_int_tuple(value: object, context: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(not _is_int(item) for item in value):
        raise ValueError(f"{context} must be an integer list")
    return tuple(value)


def _parse_seed_pair(value: object) -> SeedPair:
    if not isinstance(value, Mapping):
        raise ValueError("seed pair must be an object")
    _require_keys(value, {"indices", "rows"}, "seed pair")
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("seed-pair rows must be a two-row list")
    return SeedPair(
        _parse_int_tuple(value["indices"], "seed-pair indices"),
        tuple(_parse_int_tuple(row, "seed-pair row") for row in rows),  # type: ignore[arg-type]
    )


def _parse_reduction(value: object) -> CoreReductionStep:
    if not isinstance(value, Mapping):
        raise ValueError("core reduction must be an object")
    _require_keys(
        value,
        {"removed_atom_sha256", "candidate_sha256", "status", "retained"},
        "core reduction",
    )
    string_names = ("removed_atom_sha256", "candidate_sha256", "status")
    if not all(
        isinstance(value[name], str) for name in string_names
    ) or not isinstance(value["retained"], bool):
        raise ValueError("core reduction is malformed")
    return CoreReductionStep(
        value["removed_atom_sha256"],  # type: ignore[arg-type]
        value["candidate_sha256"],  # type: ignore[arg-type]
        value["status"],  # type: ignore[arg-type]
        value["retained"],
    )


def _parse_witness_assignment(
    value: object, context: str, *, allow_empty: bool = False
) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping) or (not value and not allow_empty):
        raise ValueError(f"{context} must be an object")
    if any(
        not isinstance(name, str) or not name or not _is_int(item)
        for name, item in value.items()
    ):
        raise ValueError(f"{context} is malformed")
    return tuple(sorted((name, item) for name, item in value.items()))


def _parse_semantic_witness(value: object) -> SemanticWitness:
    if not isinstance(value, Mapping):
        raise ValueError("semantic witness must be an object")
    _require_keys(
        value,
        {"input_state", "output_state", "local_state"},
        "semantic witness",
    )
    return SemanticWitness(
        _parse_witness_assignment(value["input_state"], "witness input"),
        _parse_witness_assignment(value["output_state"], "witness output"),
        _parse_witness_assignment(
            value["local_state"], "witness local", allow_empty=True
        ),
    )


def parse_region_query_record(
    value: object, atom_by_sha256: Mapping[str, ProjectionAtom]
) -> RegionQueryRecord:
    """Strictly parse one digest-bound incremental query record."""
    if not isinstance(value, Mapping):
        raise ValueError("region query record must be an object")
    _require_keys(
        value,
        {
            "conjunction",
            "conjunction_sha256",
            "status",
            "witness",
            "equation_residuals",
            "q0_holds",
        },
        "region query record",
    )
    conjunction_value = value["conjunction"]
    if not isinstance(conjunction_value, list) or any(
        not isinstance(digest, str) for digest in conjunction_value
    ):
        raise ValueError("query conjunction digests must be a string list")
    for digest, atom in atom_by_sha256.items():
        _validate_digest(digest, "query atom-map digest")
        if digest != hashlib.sha256(canonical_bytes(atom)).hexdigest():
            raise ValueError("query atom-map digest differs")
    try:
        conjunction = tuple(atom_by_sha256[digest] for digest in conjunction_value)
    except KeyError as error:
        raise ValueError("query conjunction atom digest does not resolve") from error
    if not isinstance(value["conjunction_sha256"], str) or not isinstance(
        value["status"], str
    ):
        raise ValueError("region query record header is malformed")
    residuals = _parse_int_tuple(value["equation_residuals"], "equation residuals")
    q0_holds = value["q0_holds"]
    if q0_holds is not None and not isinstance(q0_holds, bool):
        raise ValueError("query Q0 replay field must be Boolean or null")
    witness_value = value["witness"]
    record = RegionQueryRecord(
        conjunction=conjunction,
        conjunction_sha256=value["conjunction_sha256"],
        status=value["status"],
        witness=(
            None
            if witness_value is None
            else _parse_semantic_witness(witness_value)
        ),
        equation_residuals=residuals,
        q0_holds=q0_holds,
    )
    if record.to_payload() != dict(value):
        raise ValueError("region query record is not canonical")
    return record


def parse_search_visit(value: object) -> SearchVisit:
    """Strictly parse one pair-local solver submission."""
    if not isinstance(value, Mapping):
        raise ValueError("search visit must be an object")
    _require_keys(
        value,
        {
            "purpose",
            "parent_sha256",
            "query_sha256",
            "fresh_query",
            "violated_atom_sha256s",
            "branch_atom_sha256s",
        },
        "search visit",
    )
    if (
        not isinstance(value["purpose"], str)
        or not isinstance(value["query_sha256"], str)
        or not isinstance(value["fresh_query"], bool)
        or (
            value["parent_sha256"] is not None
            and not isinstance(value["parent_sha256"], str)
        )
    ):
        raise ValueError("search visit header is malformed")
    digest_fields = []
    for name in ("violated_atom_sha256s", "branch_atom_sha256s"):
        field_value = value[name]
        if not isinstance(field_value, list) or any(
            not isinstance(item, str) for item in field_value
        ):
            raise ValueError(f"search visit {name} must be a string list")
        digest_fields.append(tuple(field_value))
    visit = SearchVisit(
        value["purpose"],
        value["parent_sha256"],
        value["query_sha256"],
        value["fresh_query"],
        digest_fields[0],
        digest_fields[1],
    )
    if visit.to_payload() != dict(value):
        raise ValueError("search visit is not canonical")
    return visit


def parse_seed_pair_search_trace(value: object) -> SeedPairSearchTrace:
    """Strictly parse one seed-pair search trace."""
    if not isinstance(value, Mapping):
        raise ValueError("seed-pair search trace must be an object")
    _require_keys(
        value,
        {"seed_pair", "pool_size", "pool_sha256", "visits"},
        "seed-pair search trace",
    )
    visits_value = value["visits"]
    if (
        not _is_int(value["pool_size"])
        or not isinstance(value["pool_sha256"], str)
        or not isinstance(visits_value, list)
    ):
        raise ValueError("seed-pair search trace is malformed")
    trace = SeedPairSearchTrace(
        _parse_seed_pair(value["seed_pair"]),
        value["pool_size"],
        value["pool_sha256"],
        tuple(parse_search_visit(item) for item in visits_value),
    )
    if trace.to_payload() != dict(value):
        raise ValueError("seed-pair search trace is not canonical")
    return trace


def parse_incremental_search_transcript(
    value: object,
) -> IncrementalSearchTranscript:
    """Strictly parse a complete bounded-search transcript."""
    if not isinstance(value, Mapping):
        raise ValueError("incremental search transcript must be an object")
    _require_keys(value, {"queries", "pairs"}, "incremental search transcript")
    query_values = value["queries"]
    pair_values = value["pairs"]
    if not isinstance(query_values, list) or not isinstance(pair_values, list):
        raise ValueError("incremental search transcript lists are malformed")
    pairs = tuple(parse_seed_pair_search_trace(item) for item in pair_values)
    atom_by_sha256: dict[str, ProjectionAtom] = {}
    for pair in pairs:
        for atom in generate_seed_pair_pool(*pair.seed_pair.rows):
            digest = hashlib.sha256(canonical_bytes(atom)).hexdigest()
            previous = atom_by_sha256.setdefault(digest, atom)
            if previous != atom:
                raise ValueError("seed-pool atom digest collision")
    transcript = IncrementalSearchTranscript(
        tuple(
            parse_region_query_record(item, atom_by_sha256)
            for item in query_values
        ),
        pairs,
    )
    if transcript.to_payload() != dict(value):
        raise ValueError("incremental search transcript is not canonical")
    return transcript


def _parse_provenance(value: object) -> SafeRegionProvenance:
    if not isinstance(value, Mapping):
        raise ValueError("safe-region provenance must be an object")
    expected = {
        "clause",
        "seed_pair",
        "pool_size",
        "pool_sha256",
        "solver_version",
        "solver_parameters",
        "core_candidate",
        "core_candidate_sha256",
        "acquisition_query_sha256",
        "minimization_trace",
        "promoted_indices",
        "bounded_extent",
    }
    _require_keys(value, expected, "safe-region provenance")
    parameters_value = value["solver_parameters"]
    if not isinstance(parameters_value, list):
        raise ValueError("solver parameters must be a list")
    parameters: list[tuple[str, int]] = []
    for item in parameters_value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not _is_int(item[1])
        ):
            raise ValueError("solver parameter is malformed")
        parameters.append((item[0], item[1]))
    core_value = value["core_candidate"]
    trace_value = value["minimization_trace"]
    if not isinstance(core_value, list) or not isinstance(trace_value, list):
        raise ValueError("core or minimization trace is malformed")
    scalar_ints = (value["pool_size"], value["bounded_extent"])
    scalar_strings = (
        value["pool_sha256"],
        value["solver_version"],
        value["core_candidate_sha256"],
        value["acquisition_query_sha256"],
    )
    if any(not _is_int(item) for item in scalar_ints) or any(
        not isinstance(item, str) for item in scalar_strings
    ):
        raise ValueError("safe-region provenance scalar is malformed")
    provenance = SafeRegionProvenance(
        clause=_parse_clause(value["clause"]),
        seed_pair=_parse_seed_pair(value["seed_pair"]),
        pool_size=value["pool_size"],  # type: ignore[arg-type]
        pool_sha256=value["pool_sha256"],  # type: ignore[arg-type]
        solver_version=value["solver_version"],  # type: ignore[arg-type]
        solver_parameters=tuple(parameters),
        core_candidate=tuple(_parse_atom(item) for item in core_value),
        core_candidate_sha256=value["core_candidate_sha256"],  # type: ignore[arg-type]
        acquisition_query_sha256=value["acquisition_query_sha256"],  # type: ignore[arg-type]
        minimization_trace=tuple(_parse_reduction(item) for item in trace_value),
        promoted_indices=_parse_int_tuple(value["promoted_indices"], "promoted indices"),
        bounded_extent=value["bounded_extent"],  # type: ignore[arg-type]
    )
    if provenance.to_payload() != dict(value):
        raise ValueError("safe-region provenance is not canonical")
    return provenance


def parse_safe_region_cover_certificate(
    payload: Mapping[str, object],
) -> SafeRegionCoverCertificate:
    """Strictly parse one canonical T33 PASS certificate."""
    expected = {
        "schema",
        "status",
        "base",
        "removed",
        "source_digests",
        "t29_artifact_digests",
        "t30_artifact_digests",
        "t32_source_digests",
        "t32_commits",
        "t32_design_sha256",
        "t33_design_sha256",
        "t32_first_type_status",
        "t32_first_type_sha256",
        "t32_first_type_inspected_witness_count",
        "t32_first_type_tested_candidate_count",
        "t32_family_status",
        "t32_family_inspected_witness_count",
        "t32_family_tested_candidate_count",
        "predicate",
        "provenances",
        "seed_pair_count",
        "region_test_count",
        "cover_candidate_count",
        "promoted_count",
        "promoted_sha256",
        "promoted_coverage",
        "first_match_ownership",
        "clause_extents",
        "predicate_extent",
        "predicate_bytes",
        "promoted_table_bytes",
        "clause_safety_statuses",
        "primary_safety_status",
        "independent_status",
        "enumerated_input_count",
    }
    _require_keys(payload, expected, "safe-region certificate")
    strings = {
        name: payload[name]
        for name in (
            "schema",
            "status",
            "removed",
            "t32_design_sha256",
            "t33_design_sha256",
            "t32_first_type_status",
            "t32_first_type_sha256",
            "t32_family_status",
            "promoted_sha256",
            "primary_safety_status",
            "independent_status",
        )
    }
    if any(not isinstance(value, str) for value in strings.values()):
        raise ValueError("safe-region certificate string field is malformed")
    int_names = (
        "base",
        "t32_first_type_inspected_witness_count",
        "t32_first_type_tested_candidate_count",
        "t32_family_inspected_witness_count",
        "t32_family_tested_candidate_count",
        "seed_pair_count",
        "region_test_count",
        "cover_candidate_count",
        "promoted_count",
        "predicate_extent",
        "predicate_bytes",
        "promoted_table_bytes",
        "enumerated_input_count",
    )
    if any(not _is_int(payload[name]) for name in int_names):
        raise ValueError("safe-region certificate integer field is malformed")
    commits = payload["t32_commits"]
    provenances = payload["provenances"]
    ownership = payload["first_match_ownership"]
    safety = payload["clause_safety_statuses"]
    if not isinstance(commits, list) or not all(isinstance(item, str) for item in commits):
        raise ValueError("T32 commits must be a string list")
    if not isinstance(provenances, list) or not isinstance(ownership, list):
        raise ValueError("certificate provenance or ownership is malformed")
    if not isinstance(safety, list) or not all(isinstance(item, str) for item in safety):
        raise ValueError("clause safety statuses must be a string list")
    certificate = SafeRegionCoverCertificate(
        schema=strings["schema"],  # type: ignore[arg-type]
        status=strings["status"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=strings["removed"],  # type: ignore[arg-type]
        source_digests=_parse_digest_map(payload["source_digests"], _SOURCE_NAMES, "source"),
        t29_artifact_digests=_parse_digest_map(
            payload["t29_artifact_digests"], _T29_NAMES, "T29 artifact"
        ),
        t30_artifact_digests=_parse_digest_map(
            payload["t30_artifact_digests"], _T30_NAMES, "T30 artifact"
        ),
        t32_source_digests=_parse_digest_map(
            payload["t32_source_digests"], _T32_NAMES, "T32 source"
        ),
        t32_commits=tuple(commits),
        t32_design_sha256=strings["t32_design_sha256"],  # type: ignore[arg-type]
        t33_design_sha256=strings["t33_design_sha256"],  # type: ignore[arg-type]
        t32_first_type_status=strings["t32_first_type_status"],  # type: ignore[arg-type]
        t32_first_type_sha256=strings["t32_first_type_sha256"],  # type: ignore[arg-type]
        t32_first_type_inspected_witness_count=payload["t32_first_type_inspected_witness_count"],  # type: ignore[arg-type]
        t32_first_type_tested_candidate_count=payload["t32_first_type_tested_candidate_count"],  # type: ignore[arg-type]
        t32_family_status=strings["t32_family_status"],  # type: ignore[arg-type]
        t32_family_inspected_witness_count=payload["t32_family_inspected_witness_count"],  # type: ignore[arg-type]
        t32_family_tested_candidate_count=payload["t32_family_tested_candidate_count"],  # type: ignore[arg-type]
        predicate=_parse_predicate(payload["predicate"]),
        provenances=tuple(_parse_provenance(item) for item in provenances),
        seed_pair_count=payload["seed_pair_count"],  # type: ignore[arg-type]
        region_test_count=payload["region_test_count"],  # type: ignore[arg-type]
        cover_candidate_count=payload["cover_candidate_count"],  # type: ignore[arg-type]
        promoted_count=payload["promoted_count"],  # type: ignore[arg-type]
        promoted_sha256=strings["promoted_sha256"],  # type: ignore[arg-type]
        promoted_coverage=_parse_int_tuple(payload["promoted_coverage"], "promoted coverage"),
        first_match_ownership=tuple(
            _parse_int_tuple(item, "first-match ownership") for item in ownership
        ),
        clause_extents=_parse_int_tuple(payload["clause_extents"], "clause extents"),
        predicate_extent=payload["predicate_extent"],  # type: ignore[arg-type]
        predicate_bytes=payload["predicate_bytes"],  # type: ignore[arg-type]
        promoted_table_bytes=payload["promoted_table_bytes"],  # type: ignore[arg-type]
        clause_safety_statuses=tuple(safety),
        primary_safety_status=strings["primary_safety_status"],  # type: ignore[arg-type]
        independent_status=strings["independent_status"],  # type: ignore[arg-type]
        enumerated_input_count=payload["enumerated_input_count"],  # type: ignore[arg-type]
    )
    if certificate.to_payload() != dict(payload):
        raise ValueError("safe-region certificate is not canonical")
    return certificate
