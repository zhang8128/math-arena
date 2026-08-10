#!/usr/bin/env python3
"""Synthesize and verify a reachability-aware base-19 separator."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    LayerPredicate,
    LinearAtom,
    canonical_bytes,
)
from lychrel_reachability_separator import (  # noqa: E402
    CounterexampleTrace,
    SemanticWitness,
    SeparatorCertificate,
    SeparatorDataset,
    finite_separation_failures,
)
from t27_base19_invariant_lift import (  # noqa: E402
    EvidenceError,
    GrammarLimits,
    canonical_variable,
    separate_counterexample,
)
from t28_base19_tail_quotient import (  # noqa: E402
    CandidatePartition,
    GuardCounterexample,
    GuardLimits,
    T28Inputs,
    derive_guard_atoms,
    discover_reachable_quotient,
    load_t28_inputs,
    replay_layer31_counterexample_trace,
)

_SOURCE_DIGESTS = (
    (
        "equations",
        "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040",
    ),
    (
        "frontier",
        "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0",
    ),
    (
        "provenances",
        "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302",
    ),
    (
        "t27_evidence",
        "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686",
    ),
    (
        "t28_evidence",
        "b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47",
    ),
    (
        "t28_independent",
        "7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e",
    ),
)
_EXPECTED_CLASS_FAMILIES = {
    "DEAD": (),
    "Q00": ("T_HIGH_DIGIT",),
    "Q01": ("T_PHASE_ZERO",),
    "Q02": ("T_RESIDUE",),
}
_EXPECTED_CLASS_SIZES = {"DEAD": 12, "Q00": 2, "Q01": 1, "Q02": 3}


@dataclass(frozen=True)
class SeparatorLimits:
    coefficients: tuple[int, ...] = tuple(range(-3, 4))
    moduli: tuple[int, ...] = tuple(range(2, 21))
    max_clauses: int = 3
    max_atoms_per_clause: int = 12
    max_candidate_atoms: int = 512

    def __post_init__(self) -> None:
        if self.coefficients != tuple(range(-3, 4)):
            raise ValueError("separator coefficients must remain frozen at -3..3")
        if self.moduli != tuple(range(2, 21)):
            raise ValueError("separator moduli must remain frozen at 2..20")
        if self.max_clauses != 3:
            raise ValueError("separator clause ceiling must remain three")
        if self.max_atoms_per_clause != 12:
            raise ValueError("separator clause width must remain twelve")
        if self.max_candidate_atoms < 1 or self.max_candidate_atoms > 512:
            raise ValueError("candidate atom ceiling must lie in 1..512")


@dataclass(frozen=True)
class T29Inputs:
    t28_inputs: T28Inputs
    partition: CandidatePartition
    source_digests: tuple[tuple[str, str], ...]
    removed: str
    final_counterexample: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if self.partition.layer != 31:
            raise ValueError("T29 requires the layer-31 partition")
        if self.source_digests != _SOURCE_DIGESTS:
            raise ValueError("T29 source digests differ from the frozen identities")
        if self.removed != "phase=0,n=0,column=82":
            raise ValueError("T29 removed-coordinate identity changed")


@dataclass(frozen=True)
class AtomPool:
    atoms: tuple[LinearAtom, ...]

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("candidate atom pool must be nonempty")
        if self.atoms != tuple(sorted(set(self.atoms), key=canonical_bytes)):
            raise ValueError("candidate atom pool must be canonical")


@dataclass(frozen=True)
class FiniteSeparatorResult:
    status: str
    predicate: LayerPredicate | None
    objective: tuple[int, int, int, int, int, int, int, bytes] | None
    failures: tuple[tuple[str, tuple[int, ...]], ...] = ()
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status == "PASS":
            if self.predicate is None or self.objective is None or self.failures:
                raise ValueError("finite PASS requires one replayed optimum")
            if self.stop_reason is not None:
                raise ValueError("finite PASS cannot carry a stop reason")
        elif self.status == "STOP":
            if self.predicate is not None or self.objective is not None:
                raise ValueError("finite STOP cannot carry a predicate")
            if not self.stop_reason:
                raise ValueError("finite STOP requires a reason")
        else:
            raise ValueError("finite status must be PASS or STOP")


@dataclass(frozen=True)
class SemanticCheck:
    status: str
    witness: SemanticWitness | None
    equation_count: int

    def __post_init__(self) -> None:
        if self.equation_count < 1:
            raise ValueError("semantic check requires at least one equation")
        if self.status == "SAT":
            if self.witness is None:
                raise ValueError("semantic SAT requires a complete witness")
        elif self.status == "UNSAT":
            if self.witness is not None:
                raise ValueError("semantic UNSAT cannot carry a witness")
        else:
            raise ValueError("semantic status must be SAT or UNSAT")


def _read_mapping(path: Path, context: str) -> tuple[bytes, Mapping[str, object]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read frozen {context}: {error}") from error
    if not isinstance(payload, Mapping):
        raise EvidenceError(f"frozen {context} must be a JSON object")
    return raw, payload


def _require_digest(raw: bytes, expected: str, context: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise EvidenceError(f"T29 frozen {context} digest changed")


def _parse_final_counterexample(payload: Mapping[str, object]) -> tuple[tuple[str, int], ...]:
    counterexample = payload.get("counterexample")
    if not isinstance(counterexample, Mapping):
        raise EvidenceError("T28 evidence omitted its final counterexample")
    if (
        counterexample.get("rejected_class") != "DEAD"
        or counterexample.get("obligation") != "dead_has_no_successor"
    ):
        raise EvidenceError("T28 final counterexample identity changed")
    state = counterexample.get("state")
    if not isinstance(state, Mapping) or any(
        not isinstance(name, str)
        or not isinstance(value, int)
        or isinstance(value, bool)
        for name, value in state.items()
    ):
        raise EvidenceError("T28 final counterexample state is malformed")
    assignment = tuple(sorted((name, value) for name, value in state.items()))
    if len(assignment) != 14:
        raise EvidenceError("T28 final counterexample scope changed")
    return assignment


def _validate_partition(partition: CandidatePartition) -> None:
    if len(partition.variables) != 14 or len(set(partition.variables)) != 14:
        raise EvidenceError("T29 layer-31 variable scope changed")
    families = {item.label: item.allowed_next for item in partition.classes}
    sizes = {item.label: len(item.members) for item in partition.classes}
    if families != _EXPECTED_CLASS_FAMILIES:
        raise EvidenceError("T29 layer-31 class families changed")
    if sizes != _EXPECTED_CLASS_SIZES:
        raise EvidenceError("T29 layer-31 class sizes changed")


def load_t29_inputs(
    root: Path,
    *,
    t27_evidence_path: Path | None = None,
    t28_evidence_path: Path | None = None,
    t28_independent_path: Path | None = None,
) -> T29Inputs:
    """Load and bind every frozen source used by the T29 finite question."""
    root = Path(root)
    primary_path = t28_evidence_path or (
        root / ".timeloop" / "runs" / "t28_base19_tail_quotient.json"
    )
    independent_path = t28_independent_path or (
        root / ".timeloop" / "runs" / "t28_base19_tail_quotient_independent.json"
    )
    primary_raw, primary = _read_mapping(primary_path, "T28 evidence")
    independent_raw, independent = _read_mapping(
        independent_path,
        "T28 independent audit",
    )
    source = dict(_SOURCE_DIGESTS)
    _require_digest(primary_raw, source["t28_evidence"], "T28 evidence")
    _require_digest(
        independent_raw,
        source["t28_independent"],
        "T28 independent audit",
    )
    if (
        primary.get("schema") != "t28-base19-tail-quotient-evidence-v1"
        or primary.get("status") != "STOP"
        or primary.get("stop_reason") != "decision_depth_exceeded"
    ):
        raise EvidenceError("T28 primary boundary changed")
    if primary.get("frozen_hashes") != dict(_SOURCE_DIGESTS[:4]):
        raise EvidenceError("T28 primary source identities changed")
    if (
        independent.get("schema")
        != "t28-base19-tail-quotient-independent-v1"
        or independent.get("status") != "STOP"
        or independent.get("primary_evidence_sha256") != source["t28_evidence"]
        or independent.get("counterexample_successor_exists") is not True
    ):
        raise EvidenceError("T28 independent boundary changed")

    t28_inputs = load_t28_inputs(root, t27_evidence_path=t27_evidence_path)
    partition = discover_reachable_quotient(t28_inputs, 31, 32)[0]
    _validate_partition(partition)
    if primary.get("layer31_variables") != list(partition.variables):
        raise EvidenceError("T28 serialized layer-31 scope changed")
    return T29Inputs(
        t28_inputs=t28_inputs,
        partition=partition,
        source_digests=_SOURCE_DIGESTS,
        removed=str(primary.get("removed")),
        final_counterexample=_parse_final_counterexample(primary),
    )


def _project_state(
    state: tuple[int, ...],
    source_variables: tuple[str, ...],
    target_variables: tuple[str, ...],
) -> tuple[int, ...]:
    assignment = dict(zip(source_variables, state, strict=True))
    return tuple(assignment[variable] for variable in target_variables)


def build_separator_dataset(
    inputs: T29Inputs,
    trace: CounterexampleTrace,
) -> SeparatorDataset:
    """Build the exact finite T29 classification question."""
    variables = tuple(sorted(inputs.partition.variables))
    if trace.variables != variables:
        raise EvidenceError("T29 trace variable scope changed")
    if (
        len(trace.steps) != 221
        or trace.terminal_iteration != 222
        or trace.stop_reason != "decision_depth_exceeded"
    ):
        raise EvidenceError("T29 trace boundary changed")
    if any(
        step.rejected_class != "DEAD"
        or step.obligation != "dead_has_no_successor"
        for step in trace.steps
    ):
        raise EvidenceError("T29 trace obligation identity changed")
    if trace.steps[-1].input_state != inputs.final_counterexample:
        raise EvidenceError("T29 trace final state disagrees with T28 evidence")

    classes = {item.label: item for item in inputs.partition.classes}
    positives = tuple(
        sorted(
            _project_state(member, inputs.partition.variables, variables)
            for member in classes["DEAD"].members
        )
    )
    live_controls = tuple(
        sorted(
            _project_state(member, inputs.partition.variables, variables)
            for label in ("Q00", "Q01", "Q02")
            for member in classes[label].members
        )
    )
    trace_negatives = tuple(
        sorted(tuple(value for _, value in step.input_state) for step in trace.steps)
    )
    return SeparatorDataset(
        variables=variables,
        positives=positives,
        trace_negatives=trace_negatives,
        live_controls=live_controls,
    )


def trace_payload(trace: CounterexampleTrace) -> dict[str, object]:
    """Serialize a trace with its frozen source identities and exact count."""
    payload = trace.to_payload()
    payload["source_digests"] = dict(_SOURCE_DIGESTS)
    payload["counts"] = {"counterexamples": len(trace.steps)}
    return payload


def dataset_payload(dataset: SeparatorDataset) -> dict[str, object]:
    """Serialize the exact finite dataset canonically."""
    return {
        "schema": "t29-base19-reachability-separator-dataset-v1",
        "source_digests": dict(_SOURCE_DIGESTS),
        **dataset.to_payload(),
        "counts": {
            "positives": len(dataset.positives),
            "trace_negatives": len(dataset.trace_negatives),
            "live_controls": len(dataset.live_controls),
        },
    }


def _atom_holds_state(
    atom: LinearAtom,
    variables: tuple[str, ...],
    state: tuple[int, ...],
) -> bool:
    assignment = dict(zip(variables, state, strict=True))
    total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def _checked_atom_pool(
    atoms: set[LinearAtom],
    limits: SeparatorLimits,
) -> AtomPool:
    ordered = tuple(sorted(atoms, key=canonical_bytes))
    if len(ordered) > limits.max_candidate_atoms:
        raise EvidenceError("candidate_atom_pool_exceeded")
    return AtomPool(ordered)


def _state_mapping(
    variables: tuple[str, ...],
    state: tuple[int, ...],
) -> dict[str, int]:
    return dict(zip(variables, state, strict=True))


def build_candidate_atom_pool(
    inputs: T29Inputs,
    dataset: SeparatorDataset,
    limits: SeparatorLimits,
) -> AtomPool:
    """Reconstruct T28's atoms and add deterministic T29 separator seeds."""
    if dataset.variables != tuple(sorted(inputs.partition.variables)):
        raise EvidenceError("candidate pool dataset scope changed")
    guard_limits = GuardLimits(
        coefficients=limits.coefficients,
        moduli=limits.moduli,
    )
    counterexamples = tuple(
        GuardCounterexample(
            tuple(
                _state_mapping(dataset.variables, state)[variable]
                for variable in inputs.partition.variables
            ),
            "DEAD",
            "dead_has_no_successor",
        )
        for state in dataset.trace_negatives
    )
    reconstructed = derive_guard_atoms(
        inputs.partition,
        counterexamples,
        guard_limits,
    )
    if len(reconstructed) != 37:
        raise EvidenceError(
            f"T28 reconstructed atom count changed: {len(reconstructed)}"
        )
    atoms = set(reconstructed)
    _checked_atom_pool(atoms, limits)

    for clause in inputs.t28_inputs.terminal_predicate.clauses:
        atoms.update(clause.atoms)
    _checked_atom_pool(atoms, limits)

    grammar = GrammarLimits(
        coefficients=limits.coefficients,
        moduli=limits.moduli,
    )
    positive_maps = tuple(
        _state_mapping(dataset.variables, state) for state in dataset.positives
    )
    negatives = (*dataset.trace_negatives, *dataset.live_controls)
    for state in negatives:
        candidate = separate_counterexample(
            positive_maps,
            _state_mapping(dataset.variables, state),
            dataset.variables,
            grammar,
        )
        if candidate is not None:
            atoms.add(candidate.atom)
    _checked_atom_pool(atoms, limits)

    seed = tuple(sorted(atoms, key=canonical_bytes))
    positive_components: dict[tuple[bool, ...], list[dict[str, int]]] = {}
    for state, assignment in zip(dataset.positives, positive_maps, strict=True):
        truth = tuple(
            _atom_holds_state(atom, dataset.variables, state) for atom in seed
        )
        positive_components.setdefault(truth, []).append(assignment)
    for truth in sorted(positive_components):
        component = tuple(positive_components[truth])
        for state in negatives:
            candidate = separate_counterexample(
                component,
                _state_mapping(dataset.variables, state),
                dataset.variables,
                grammar,
            )
            if candidate is not None:
                atoms.add(candidate.atom)
        _checked_atom_pool(atoms, limits)
    return _checked_atom_pool(atoms, limits)


def check_finite_separator(
    dataset: SeparatorDataset,
    predicate: LayerPredicate,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Replay one finite separator against all three labeled parts."""
    return finite_separation_failures(predicate, dataset)


def _z3_atom(
    z3: object,
    atom: LinearAtom,
    canonical_to_original: Mapping[str, str],
    variables: Mapping[str, object],
) -> object:
    try:
        total = sum(
            coefficient * variables[canonical_to_original[name]]
            for name, coefficient in atom.terms
        )
    except KeyError as error:
        raise EvidenceError(
            f"semantic predicate references unknown input: {error.args[0]}"
        ) from error
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def _solver_status(z3: object, solver: object, context: str) -> object:
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return status


def _lexicographic_equation_model(
    z3: object,
    solver: object,
    variables: Mapping[str, object],
    base: int,
) -> object:
    if _solver_status(z3, solver, "semantic witness search") != z3.sat:
        raise EvidenceError("cannot canonicalize an UNSAT semantic witness")
    for name in sorted(variables):
        if name.startswith("c:"):
            domain = range(2)
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            domain = range(lower, base)
        for value in domain:
            solver.push()
            solver.add(variables[name] == value)
            status = _solver_status(z3, solver, "semantic witness minimization")
            solver.pop()
            if status == z3.sat:
                solver.add(variables[name] == value)
                break
        else:
            raise EvidenceError(f"semantic witness variable has no value: {name}")
    if _solver_status(z3, solver, "semantic witness finalization") != z3.sat:
        raise EvidenceError("canonical semantic witness became inconsistent")
    return solver.model()


def check_semantic_dead_region(
    inputs: T29Inputs,
    predicate: LayerPredicate,
) -> SemanticCheck:
    """Ask whether any exact layer-31 successor starts inside the predicate."""
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("semantic separator checking requires z3-solver") from error
    transfer = inputs.t28_inputs.frontier.layers_by_number[32]
    equations = tuple(
        inputs.t28_inputs.manifest.by_provenance[provenance]
        for provenance in transfer.equation_provenances
    )
    names = tuple(
        sorted(
            set(transfer.input_variables)
            | set(transfer.output_variables)
            | {name for equation in equations for name in equation.variables}
        )
    )
    variables = {
        name: z3.Int(
            "t29_semantic_"
            + "".join(character if character.isalnum() else "_" for character in name)
        )
        for name in names
    }
    constraints = []
    for name, variable in variables.items():
        if name.startswith("c:"):
            constraints.extend((variable >= 0, variable <= 1))
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            constraints.extend(
                (variable >= lower, variable < inputs.t28_inputs.manifest.base)
            )
    constraints.extend(
        equation.residual(variables, inputs.t28_inputs.manifest.base) == 0
        for equation in equations
    )
    input_mapping = {
        canonical_variable(name, transfer, "input"): name
        for name in transfer.input_variables
    }
    output_mapping = {
        canonical_variable(name, transfer, "output"): name
        for name in transfer.output_variables
    }
    if predicate.layer != 31 or predicate.variables != tuple(sorted(input_mapping)):
        raise EvidenceError("semantic predicate scope differs from layer 31")
    predicate_formula = z3.Or(
        *(
            z3.And(
                *(
                    _z3_atom(z3, atom, input_mapping, variables)
                    for atom in clause.atoms
                )
            )
            for clause in predicate.clauses
        )
    )
    solver = z3.Solver()
    solver.add(*constraints, predicate_formula)
    status = _solver_status(z3, solver, "semantic dead-region query")
    if status == z3.unsat:
        return SemanticCheck("UNSAT", None, len(equations))
    model = _lexicographic_equation_model(
        z3,
        solver,
        variables,
        inputs.t28_inputs.manifest.base,
    )
    assignment = {
        name: model.eval(variable, model_completion=True).as_long()
        for name, variable in variables.items()
    }
    if any(
        equation.residual(assignment, inputs.t28_inputs.manifest.base) != 0
        for equation in equations
    ):
        raise EvidenceError("semantic witness failed integer equation replay")
    input_originals = set(transfer.input_variables)
    output_originals = set(transfer.output_variables)
    local_names = tuple(sorted(set(variables) - input_originals - output_originals))
    witness = SemanticWitness(
        input_state=tuple(
            sorted(
                (f"input:{canonical}", assignment[original])
                for canonical, original in input_mapping.items()
            )
        ),
        output_state=tuple(
            sorted(
                (f"output:{canonical}", assignment[original])
                for canonical, original in output_mapping.items()
            )
        ),
        local_state=tuple(
            (f"local:{name}", assignment[name]) for name in local_names
        ),
    )
    return SemanticCheck("SAT", witness, len(equations))


def synthesize_finite_separator(
    dataset: SeparatorDataset,
    pool: AtomPool,
    limits: SeparatorLimits,
) -> FiniteSeparatorResult:
    """Select the cheapest bounded DNF separating the frozen finite dataset."""
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("finite separator synthesis requires z3-solver") from error
    if len(pool.atoms) > limits.max_candidate_atoms:
        raise EvidenceError("candidate_atom_pool_exceeded")
    scope = set(dataset.variables)
    if any(
        any(variable not in scope for variable, _ in atom.terms)
        for atom in pool.atoms
    ):
        raise EvidenceError("candidate atom lies outside the dataset scope")

    solver = z3.Optimize()
    active = tuple(z3.Bool(f"t29_clause_{clause}_active") for clause in range(3))
    selected = tuple(
        tuple(
            z3.Bool(f"t29_clause_{clause}_atom_{atom}")
            for atom in range(len(pool.atoms))
        )
        for clause in range(3)
    )
    widths = tuple(
        z3.Sum(*(z3.If(choice, 1, 0) for choice in row))
        for row in selected
    )
    solver.add(active[0])
    for clause in range(3):
        solver.add(
            z3.Implies(active[clause], widths[clause] >= 1),
            widths[clause] <= limits.max_atoms_per_clause,
        )
        for choice in selected[clause]:
            solver.add(z3.Implies(choice, active[clause]))
        if clause:
            solver.add(z3.Implies(active[clause], active[clause - 1]))

    positives = dataset.positives
    negatives = (*dataset.trace_negatives, *dataset.live_controls)
    positive_truth = tuple(
        tuple(_atom_holds_state(atom, dataset.variables, state) for atom in pool.atoms)
        for state in positives
    )
    negative_truth = tuple(
        tuple(_atom_holds_state(atom, dataset.variables, state) for atom in pool.atoms)
        for state in negatives
    )
    for truth in positive_truth:
        solver.add(
            z3.Or(
                *(
                    z3.And(
                        active[clause],
                        *(
                            z3.Not(selected[clause][index])
                            for index, holds in enumerate(truth)
                            if not holds
                        ),
                    )
                    for clause in range(3)
                )
            )
        )
    for truth in negative_truth:
        rejecting = tuple(index for index, holds in enumerate(truth) if not holds)
        for clause in range(3):
            solver.add(
                z3.Implies(
                    active[clause],
                    z3.Or(*(selected[clause][index] for index in rejecting)),
                )
            )

    bit_weights = tuple(1 << (len(pool.atoms) - index - 1) for index in range(len(pool.atoms)))
    clause_codes = tuple(
        z3.Sum(
            *(
                z3.If(selected[clause][index], bit_weights[index], 0)
                for index in range(len(pool.atoms))
            )
        )
        for clause in range(3)
    )
    solver.add(clause_codes[0] >= clause_codes[1], clause_codes[1] >= clause_codes[2])
    clause_count = z3.Sum(*(z3.If(item, 1, 0) for item in active))
    total_atoms = z3.Sum(*widths)
    maximum_width = z3.Int("t29_maximum_clause_width")
    solver.add(maximum_width >= 0, *(maximum_width >= width for width in widths))
    coefficient_support = z3.Sum(
        *(
            z3.If(selected[clause][index], len(atom.terms), 0)
            for clause in range(3)
            for index, atom in enumerate(pool.atoms)
        )
    )
    absolute_sum = z3.Sum(
        *(
            z3.If(
                selected[clause][index],
                sum(abs(coefficient) for _, coefficient in atom.terms),
                0,
            )
            for clause in range(3)
            for index, atom in enumerate(pool.atoms)
        )
    )
    relation_rank = {"eq": 0, "le": 1, "congruent": 2}
    relation_code = z3.Sum(
        *(
            z3.If(selected[clause][index], relation_rank[atom.relation], 0)
            for clause in range(3)
            for index, atom in enumerate(pool.atoms)
        )
    )
    modulus_code = z3.Sum(
        *(
            z3.If(selected[clause][index], atom.modulus or 0, 0)
            for clause in range(3)
            for index, atom in enumerate(pool.atoms)
        )
    )
    for objective in (
        clause_count,
        total_atoms,
        maximum_width,
        coefficient_support,
        absolute_sum,
        relation_code,
        modulus_code,
    ):
        solver.minimize(objective)
    solver.maximize(
        z3.Sum(
            *(
                code * (1 << ((2 - index) * len(pool.atoms)))
                for index, code in enumerate(clause_codes)
            )
        )
    )
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(
            f"finite separator synthesis returned UNKNOWN: {solver.reason_unknown()}"
        )
    if status == z3.unsat:
        first_uncovered = next(
            (
                state
                for state, truth in zip(positives, positive_truth, strict=True)
                if not any(truth)
            ),
            positives[0],
        )
        return FiniteSeparatorResult(
            status="STOP",
            predicate=None,
            objective=None,
            failures=(("positive", first_uncovered),),
            stop_reason="finite_separator_not_found",
        )
    model = solver.model()
    clauses = tuple(
        Conjunction(
            tuple(
                atom
                for index, atom in enumerate(pool.atoms)
                if z3.is_true(model.eval(selected[clause][index], model_completion=True))
            )
        )
        for clause in range(3)
        if z3.is_true(model.eval(active[clause], model_completion=True))
    )
    predicate = LayerPredicate(layer=31, variables=dataset.variables, clauses=clauses)
    failures = check_finite_separator(dataset, predicate)
    if failures:
        raise EvidenceError("optimized finite separator failed exact replay")
    objective_values = (
        len(predicate.clauses),
        sum(len(clause.atoms) for clause in predicate.clauses),
        max(len(clause.atoms) for clause in predicate.clauses),
        sum(len(atom.terms) for clause in predicate.clauses for atom in clause.atoms),
        sum(
            abs(coefficient)
            for clause in predicate.clauses
            for atom in clause.atoms
            for _, coefficient in atom.terms
        ),
        sum(relation_rank[atom.relation] for clause in predicate.clauses for atom in clause.atoms),
        sum((atom.modulus or 0) for clause in predicate.clauses for atom in clause.atoms),
        canonical_bytes(predicate),
    )
    return FiniteSeparatorResult(
        status="PASS",
        predicate=predicate,
        objective=objective_values,
    )


def _objective_payload(
    objective: tuple[int, int, int, int, int, int, int, bytes],
) -> dict[str, object]:
    return {
        "clause_count": objective[0],
        "total_atoms": objective[1],
        "maximum_width": objective[2],
        "coefficient_support": objective[3],
        "absolute_sum": objective[4],
        "relation_code": objective[5],
        "modulus_code": objective[6],
        "canonical_predicate": objective[7].decode("utf-8"),
    }


def _baseline_digest(baseline: Mapping[str, object], name: str) -> str:
    value = baseline.get(name)
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise EvidenceError(f"T29 baseline {name} is not a SHA-256")
    return value


def decide_t29_gate(
    baseline: Mapping[str, object],
    finite_result: FiniteSeparatorResult,
    semantic_result: SemanticCheck | None,
) -> tuple[dict[str, object], SeparatorCertificate | None]:
    """Preserve finite separation while gating any semantic promotion."""
    source_digests = baseline.get("source_digests")
    if source_digests != _SOURCE_DIGESTS:
        raise EvidenceError("T29 baseline source identities changed")
    trace_sha256 = _baseline_digest(baseline, "trace_sha256")
    dataset_sha256 = _baseline_digest(baseline, "dataset_sha256")
    pool_size = baseline.get("pool_size")
    counts = baseline.get("counts")
    if (
        not isinstance(pool_size, int)
        or isinstance(pool_size, bool)
        or not 1 <= pool_size <= 512
        or not isinstance(counts, Mapping)
    ):
        raise EvidenceError("T29 finite baseline is malformed")
    evidence: dict[str, object] = {
        "schema": "t29-base19-reachability-separator-evidence-v1",
        "base": 19,
        "removed": "phase=0,n=0,column=82",
        "source_digests": dict(_SOURCE_DIGESTS),
        "trace_sha256": trace_sha256,
        "dataset_sha256": dataset_sha256,
        "pool_size": pool_size,
        "counts": dict(counts),
        "limits": {
            "coefficients": list(range(-3, 4)),
            "moduli": list(range(2, 21)),
            "max_clauses": 3,
            "max_atoms_per_clause": 12,
            "max_candidate_atoms": 512,
        },
        "primary_sources": [
            "https://arxiv.org/abs/2504.08617",
            "https://arxiv.org/abs/1610.01722",
            "https://arxiv.org/abs/0906.4492",
        ],
        "prism": {
            "role": "hypothesis_generator_only",
            "usable_artifact": False,
            "mathematical_premise": False,
        },
        "claim_boundary": [
            "the frozen base-19 radial obstruction only",
            "the exact layer-31 to layer-32 local relation only",
            "finite separation covers only the 239 serialized examples",
        ],
        "limitations": [
            "Finite separation is not a reachability or inductive-invariant theorem.",
            "Semantic SAT prevents promotion to a universal dead-region theorem.",
            "No other base, topology family, lower layer, Lean bridge, or publication was changed.",
        ],
    }
    if finite_result.status == "STOP":
        evidence.update(
            {
                "status": "FINITE_SEPARATOR_STOP",
                "stop_reason": finite_result.stop_reason,
                "finite_failures": [
                    {"part": part, "state": list(state)}
                    for part, state in finite_result.failures
                ],
                "semantic_status": "NOT_RUN",
            }
        )
        return evidence, None
    if finite_result.predicate is None or finite_result.objective is None:
        raise EvidenceError("finite PASS omitted its predicate or objective")
    if semantic_result is None:
        semantic_status = "NOT_RUN"
        semantic_witness = None
        status = "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        stop_reason = "semantic_check_not_run"
    else:
        semantic_status = semantic_result.status
        semantic_witness = semantic_result.witness
        if semantic_status == "UNSAT":
            status = "SEMANTIC_DEAD_REGION_PASS"
            stop_reason = None
        else:
            status = "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
            stop_reason = "semantic_successor_found"
    certificate = SeparatorCertificate(
        schema="t29-base19-reachability-separator-certificate-v1",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=_SOURCE_DIGESTS,
        trace_sha256=trace_sha256,
        dataset_sha256=dataset_sha256,
        predicate=finite_result.predicate,
        finite_status="PASS",
        semantic_status=semantic_status,
        semantic_witness=semantic_witness,
    )
    evidence.update(
        {
            "status": status,
            "stop_reason": stop_reason,
            "finite_status": "PASS",
            "finite_predicate": finite_result.predicate.to_payload(),
            "finite_objective": _objective_payload(finite_result.objective),
            "semantic_status": semantic_status,
            "semantic_equation_count": (
                None if semantic_result is None else semantic_result.equation_count
            ),
            "semantic_counterexample": (
                None if semantic_witness is None else semantic_witness.to_payload()
            ),
            "certificate_sha256": hashlib.sha256(
                canonical_bytes(certificate)
            ).hexdigest(),
        }
    )
    return evidence, certificate


def build_t29_primary(
    root: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    SeparatorCertificate | None,
]:
    """Run the frozen T29 finite and conditional semantic milestones."""
    inputs = load_t29_inputs(root)
    layer_result, trace = replay_layer31_counterexample_trace(root)
    if (
        layer_result.status != "STOP"
        or layer_result.iterations != 222
        or layer_result.stop_reason != "decision_depth_exceeded"
    ):
        raise EvidenceError("T28 replay result changed before T29 synthesis")
    dataset = build_separator_dataset(inputs, trace)
    limits = SeparatorLimits()
    pool = build_candidate_atom_pool(inputs, dataset, limits)
    finite_result = synthesize_finite_separator(dataset, pool, limits)
    trace_document = trace_payload(trace)
    dataset_document = dataset_payload(dataset)
    baseline = {
        "source_digests": inputs.source_digests,
        "trace_sha256": hashlib.sha256(canonical_bytes(trace_document)).hexdigest(),
        "dataset_sha256": hashlib.sha256(
            canonical_bytes(dataset_document)
        ).hexdigest(),
        "pool_size": len(pool.atoms),
        "counts": {
            "positives": len(dataset.positives),
            "trace_negatives": len(dataset.trace_negatives),
            "live_controls": len(dataset.live_controls),
        },
    }
    semantic_result = (
        None
        if finite_result.status != "PASS" or finite_result.predicate is None
        else check_semantic_dead_region(inputs, finite_result.predicate)
    )
    evidence, certificate = decide_t29_gate(
        baseline,
        finite_result,
        semantic_result,
    )
    evidence["trace"] = {
        "counterexample_count": len(trace.steps),
        "terminal_iteration": trace.terminal_iteration,
        "stop_reason": trace.stop_reason,
    }
    return evidence, trace_document, dataset_document, certificate


def render_t29_report(evidence: Mapping[str, object]) -> str:
    """Render the achieved T29 boundary without semantic overclaiming."""
    status = str(evidence["status"])
    counts = evidence.get("counts", {})
    lines = [
        "# T29 base-19 reachability separator",
        "",
        f"Status: **{status}**",
        "",
        "## Claim boundary",
        "",
        "This result concerns only the frozen base-19 radial obstruction and "
        "its exact layer-31 to layer-32 relation.",
        "",
        "## Finite separator",
        "",
    ]
    if evidence.get("finite_status") == "PASS":
        lines.extend(
            [
                "The serialized predicate is a finite-only separator.",
                f"It covers {counts.get('positives')} promoted dead states and rejects "
                f"{counts.get('trace_negatives')} trace negatives plus "
                f"{counts.get('live_controls')} live controls.",
                f"Candidate atom pool: {evidence.get('pool_size')}.",
                "",
                "```json",
                json.dumps(evidence.get("finite_predicate"), sort_keys=True),
                "```",
            ]
        )
    else:
        lines.append(f"Finite synthesis stopped: `{evidence.get('stop_reason')}`.")
    lines.extend(["", "## Semantic check", ""])
    semantic_status = evidence.get("semantic_status")
    if semantic_status == "SAT":
        lines.extend(
            [
                "An exact semantic successor exists, so the finite predicate "
                "is not a universal dead region.",
                "",
                "```json",
                json.dumps(evidence.get("semantic_counterexample"), sort_keys=True),
                "```",
            ]
        )
    elif semantic_status == "UNSAT":
        lines.append("The exact 12-equation successor query is UNSAT.")
    else:
        lines.append("Semantic promotion was not run.")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            *(f"- {item}" for item in evidence.get("limitations", [])),
            "",
        ]
    )
    return "\n".join(lines)


def _write_canonical_json(path: Path, payload: object) -> None:
    path.write_bytes(canonical_bytes(payload) + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    evidence, trace, dataset, certificate = build_t29_primary(root)
    _write_canonical_json(arguments.evidence, evidence)
    _write_canonical_json(arguments.trace, trace)
    _write_canonical_json(arguments.dataset, dataset)
    arguments.report.write_text(render_t29_report(evidence), encoding="utf-8")
    if certificate is None:
        arguments.certificate.unlink(missing_ok=True)
    else:
        _write_canonical_json(arguments.certificate, certificate)


if __name__ == "__main__":
    main()
