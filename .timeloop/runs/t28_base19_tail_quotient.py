#!/usr/bin/env python3
"""Construct and verify a symbolic quotient for the frozen base-19 tail."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from lychrel_invariant_certificate import LayerPredicate, LinearAtom, canonical_bytes
from lychrel_quotient_automaton import (
    ClassSpec,
    DecisionNode,
    EdgeWitness,
    LayerQuotient,
    QuotientCertificate,
    classify_state,
    layer_path_depth,
)
from t27_base19_invariant_lift import (
    EquationManifest,
    EvidenceError,
    FrontierCertificate,
    GrammarLimits,
    canonical_variable,
    canonicalize_state,
    load_promoted_inputs,
    separate_counterexample,
    synthesize_terminal_predicate,
)

_EQUATIONS_CONTENT_SHA256 = "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"
_FRONTIER_CONTENT_SHA256 = "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"
_PROVENANCES_SHA256 = "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"
_T27_EVIDENCE_SHA256 = "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686"


@dataclass(frozen=True)
class T28Inputs:
    manifest: EquationManifest
    frontier: FrontierCertificate
    terminal_predicate: LayerPredicate
    t27_evidence_sha256: str


@dataclass(frozen=True)
class CandidateClass:
    label: str
    allowed_next: tuple[str, ...]
    members: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class CandidatePartition:
    layer: int
    variables: tuple[str, ...]
    classes: tuple[CandidateClass, ...]


@dataclass(frozen=True)
class GuardLimits:
    coefficients: tuple[int, ...] = (-3, -2, -1, 0, 1, 2, 3)
    moduli: tuple[int, ...] = tuple(range(2, 21))
    max_classes: int = 8
    max_nodes: int = 64
    max_depth: int = 10

    def __post_init__(self) -> None:
        if self.coefficients != (-3, -2, -1, 0, 1, 2, 3):
            raise ValueError("T28 coefficients are frozen at -3..3")
        if self.moduli != tuple(range(2, 21)):
            raise ValueError("T28 congruence moduli are frozen at 2..20")
        if not 1 <= self.max_classes <= 8:
            raise ValueError("T28 class limit must be in 1..8")
        if not 1 <= self.max_nodes <= 64:
            raise ValueError("T28 node limit must be in 1..64")
        if not 0 <= self.max_depth <= 10:
            raise ValueError("T28 depth limit must be in 0..10")


class GuardSynthesisError(EvidenceError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _atom_holds_row(
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


def _label_conflicts(rows: tuple[tuple[tuple[int, ...], str], ...]) -> int:
    return sum(
        left_label != right_label
        for index, (_, left_label) in enumerate(rows)
        for _, right_label in rows[index + 1 :]
    )


def build_reduced_decision_dag(
    partition: CandidatePartition,
    atoms: tuple[LinearAtom, ...],
    limits: GuardLimits,
    outside_members: tuple[tuple[int, ...], ...] = (),
) -> LayerQuotient:
    """Fit a deterministic reduced decision DAG to a promoted partition."""
    if len(partition.classes) > limits.max_classes:
        raise GuardSynthesisError("class_limit_exceeded")
    examples = tuple(
        sorted(
            (
                *(
                    (member, class_spec.label)
                    for class_spec in partition.classes
                    for member in class_spec.members
                ),
                *((member, "outside") for member in outside_members),
            )
        )
    )
    if not examples or any(len(state) != len(partition.variables) for state, _ in examples):
        raise ValueError("candidate partition members must match their variables")
    if len({state for state, _ in examples}) != len(examples):
        raise ValueError("candidate partition members must be disjoint")
    candidates = tuple(sorted(set(atoms), key=canonical_bytes))

    Tree = tuple[object, ...]

    def learn(
        rows: tuple[tuple[tuple[int, ...], str], ...],
        available: tuple[LinearAtom, ...],
    ) -> Tree:
        labels = {label for _, label in rows}
        if len(labels) == 1:
            return ("leaf", next(iter(labels)))
        ranked = []
        parent_conflicts = _label_conflicts(rows)
        for atom in available:
            true_rows = tuple(
                row for row in rows if _atom_holds_row(atom, partition.variables, row[0])
            )
            false_rows = tuple(row for row in rows if row not in true_rows)
            if not true_rows or not false_rows:
                continue
            conflicts = _label_conflicts(true_rows) + _label_conflicts(false_rows)
            if conflicts >= parent_conflicts:
                continue
            relation_rank = {"eq": 0, "le": 1, "congruent": 2}[atom.relation]
            ranked.append(
                (
                    (
                        conflicts,
                        max(len(true_rows), len(false_rows)),
                        len(atom.terms),
                        sum(abs(coefficient) for _, coefficient in atom.terms),
                        relation_rank,
                        atom.modulus or 0,
                        canonical_bytes(atom),
                    ),
                    atom,
                    true_rows,
                    false_rows,
                )
            )
        if not ranked:
            raise GuardSynthesisError("guard_separator_not_found")
        _, chosen, true_rows, false_rows = min(ranked, key=lambda item: item[0])
        remaining = tuple(atom for atom in available if atom != chosen)
        return (
            "node",
            chosen,
            learn(true_rows, remaining),
            learn(false_rows, remaining),
        )

    root = learn(examples, candidates)

    def tree_depth(tree: Tree) -> int:
        if tree[0] == "leaf":
            return 0
        return 1 + max(
            tree_depth(tree[2]),  # type: ignore[arg-type]
            tree_depth(tree[3]),  # type: ignore[arg-type]
        )

    if tree_depth(root) > limits.max_depth:
        raise GuardSynthesisError("decision_depth_exceeded")
    unique_nodes: set[Tree] = set()

    def collect(tree: Tree) -> None:
        if tree[0] != "node" or tree in unique_nodes:
            return
        unique_nodes.add(tree)
        collect(tree[2])  # type: ignore[arg-type]
        collect(tree[3])  # type: ignore[arg-type]

    collect(root)
    if len(unique_nodes) > limits.max_nodes:
        raise GuardSynthesisError("decision_node_limit_exceeded")

    parents: dict[Tree, set[Tree]] = {tree: set() for tree in unique_nodes}
    for tree in unique_nodes:
        for child in (tree[2], tree[3]):
            if child[0] == "node":
                parents[child].add(tree)  # type: ignore[index]
    ready = [tree for tree, incoming in parents.items() if not incoming]
    ordered_nodes = []
    while ready:
        tree = min(ready, key=repr)
        ready.remove(tree)
        ordered_nodes.append(tree)
        for child in (tree[2], tree[3]):
            if child[0] != "node":
                continue
            parents[child].remove(tree)  # type: ignore[index]
            if not parents[child]:  # type: ignore[index]
                ready.append(child)  # type: ignore[arg-type]
    if len(ordered_nodes) != len(unique_nodes):
        raise EvidenceError("learned decision graph is cyclic")
    identifiers = {tree: index for index, tree in enumerate(ordered_nodes)}

    def target(tree: Tree) -> str:
        if tree[0] == "leaf":
            return "outside" if tree[1] == "outside" else f"class:{tree[1]}"
        return f"node:{identifiers[tree]}"

    nodes = tuple(
        DecisionNode(
            identifiers[tree],
            tree[1],  # type: ignore[arg-type]
            target(tree[2]),  # type: ignore[arg-type]
            target(tree[3]),  # type: ignore[arg-type]
        )
        for tree in ordered_nodes
    )
    classes = tuple(
        ClassSpec(
            item.label,
            "live" if item.allowed_next else "dead",
            item.allowed_next,
        )
        for item in partition.classes
    )
    layer = LayerQuotient(
        partition.layer,
        partition.variables,
        target(root),
        classes,
        nodes,
    )
    if layer_path_depth(layer) > limits.max_depth:
        raise GuardSynthesisError("decision_depth_exceeded")
    return layer


@dataclass(frozen=True)
class GuardCounterexample:
    state: tuple[int, ...]
    rejected_class: str
    reason: str


@dataclass(frozen=True)
class LayerSynthesis:
    status: str
    layer: int
    quotient: LayerQuotient | None
    witnesses: tuple[EdgeWitness, ...]
    iterations: int
    candidate_atom_count: int
    stop_reason: str | None = None
    counterexample: GuardCounterexample | None = None


def _state_assignment(
    variables: tuple[str, ...],
    state: tuple[int, ...],
) -> dict[str, int]:
    return dict(zip(variables, state, strict=True))


def _derive_separator_atom(
    partition: CandidatePartition,
    class_spec: CandidateClass,
    state: tuple[int, ...],
    limits: GuardLimits,
) -> LinearAtom | None:
    candidate = separate_counterexample(
        tuple(
            _state_assignment(partition.variables, member)
            for member in class_spec.members
        ),
        _state_assignment(partition.variables, state),
        partition.variables,
        GrammarLimits(
            coefficients=limits.coefficients,
            moduli=limits.moduli,
        ),
    )
    return None if candidate is None else candidate.atom


def derive_guard_atoms(
    partition: CandidatePartition,
    counterexamples: tuple[GuardCounterexample, ...],
    limits: GuardLimits,
) -> tuple[LinearAtom, ...]:
    """Derive frozen-grammar atoms separating promoted classes and CEGIS models."""
    atoms = set()
    for class_spec in partition.classes:
        negatives = [
            state
            for other in partition.classes
            if other.label != class_spec.label
            for state in other.members
        ]
        negatives.extend(
            item.state
            for item in counterexamples
            if item.rejected_class == class_spec.label
        )
        for state in sorted(set(negatives)):
            atom = _derive_separator_atom(partition, class_spec, state, limits)
            if atom is not None:
                atoms.add(atom)
    return tuple(sorted(atoms, key=canonical_bytes))


@dataclass(frozen=True)
class ExplicitTransfer:
    source_layer: int
    input_variables: tuple[str, ...]
    output_variables: tuple[str, ...]
    source_domain: tuple[tuple[int, ...], ...]
    transitions: tuple[tuple[tuple[int, ...], tuple[tuple[int, ...], ...]], ...]

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.source_domain))) != self.source_domain:
            raise ValueError("explicit source domain must be sorted and unique")
        if tuple(item[0] for item in self.transitions) != self.source_domain:
            raise ValueError("explicit transitions must cover the source domain in order")
        if any(len(state) != len(self.input_variables) for state in self.source_domain):
            raise ValueError("explicit input state width changed")
        for _, outputs in self.transitions:
            if tuple(sorted(set(outputs))) != outputs:
                raise ValueError("explicit outputs must be sorted and unique")
            if any(len(state) != len(self.output_variables) for state in outputs):
                raise ValueError("explicit output state width changed")


@dataclass(frozen=True)
class QuotientObligation:
    kind: str
    layer: int
    class_label: str
    status: str
    checked_count: int
    counterexample: dict[str, dict[str, int]] | None = None


@dataclass(frozen=True)
class QuotientCheck:
    status: str
    obligations: tuple[QuotientObligation, ...]


def _named_state(variables: tuple[str, ...], state: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(variables, state, strict=True))


def check_explicit_layer(
    transfer: ExplicitTransfer,
    source_labels: Mapping[tuple[int, ...], str],
    target_labels: Mapping[tuple[int, ...], str],
    classes: tuple[ClassSpec, ...],
    witnesses: tuple[EdgeWitness, ...],
) -> QuotientCheck:
    """Check quotient semantics over a complete finite relation."""
    if set(source_labels) != set(transfer.source_domain):
        raise ValueError("source labels must cover the explicit source domain")
    transitions = dict(transfer.transitions)
    obligations = []
    checked_count = len(transfer.source_domain)
    witness_by_edge = {
        (item.source_class, item.target_class): item for item in witnesses
    }
    if len(witness_by_edge) != len(witnesses):
        raise ValueError("explicit edge witnesses must be unique")

    for class_spec in sorted(classes, key=lambda item: item.label):
        members = tuple(
            state
            for state in transfer.source_domain
            if source_labels[state] == class_spec.label
        )
        if class_spec.kind == "dead":
            for state in members:
                if transitions[state]:
                    output = transitions[state][0]
                    obligations.append(
                        QuotientObligation(
                            "dead_has_no_successor",
                            transfer.source_layer,
                            class_spec.label,
                            "FAIL",
                            checked_count,
                            {
                                "input": _named_state(transfer.input_variables, state),
                                "output": _named_state(transfer.output_variables, output),
                            },
                        )
                    )
                    return QuotientCheck("FAIL", tuple(obligations))
            obligations.append(
                QuotientObligation(
                    "dead_has_no_successor",
                    transfer.source_layer,
                    class_spec.label,
                    "PASS",
                    checked_count,
                )
            )
            continue
        if class_spec.kind != "live":
            raise ValueError("explicit source classes must be live or dead")

        for state in members:
            if not transitions[state]:
                obligations.append(
                    QuotientObligation(
                        "live_has_successor",
                        transfer.source_layer,
                        class_spec.label,
                        "FAIL",
                        checked_count,
                        {"input": _named_state(transfer.input_variables, state)},
                    )
                )
                return QuotientCheck("FAIL", tuple(obligations))
        obligations.append(
            QuotientObligation(
                "live_has_successor",
                transfer.source_layer,
                class_spec.label,
                "PASS",
                checked_count,
            )
        )

        for state in members:
            for output in transitions[state]:
                if target_labels.get(output, "outside") not in class_spec.allowed_next:
                    obligations.append(
                        QuotientObligation(
                            "forbidden_successor",
                            transfer.source_layer,
                            class_spec.label,
                            "FAIL",
                            checked_count,
                            {
                                "input": _named_state(transfer.input_variables, state),
                                "output": _named_state(transfer.output_variables, output),
                            },
                        )
                    )
                    return QuotientCheck("FAIL", tuple(obligations))
        obligations.append(
            QuotientObligation(
                "forbidden_successor",
                transfer.source_layer,
                class_spec.label,
                "PASS",
                checked_count,
            )
        )

        for target_class in class_spec.allowed_next:
            witness = witness_by_edge.get((class_spec.label, target_class))
            valid = witness is not None
            if witness is not None:
                input_state = tuple(
                    dict(witness.input_state).get(name)
                    for name in transfer.input_variables
                )
                output_state = tuple(
                    dict(witness.output_state).get(name) for name in transfer.output_variables
                )
                valid = (
                    witness.source_layer == transfer.source_layer
                    and None not in input_state
                    and None not in output_state
                    and input_state in transitions
                    and output_state in transitions[input_state]
                    and source_labels[input_state] == class_spec.label
                    and target_labels.get(output_state) == target_class
                )
            if not valid:
                obligations.append(
                    QuotientObligation(
                        "edge_has_witness",
                        transfer.source_layer,
                        class_spec.label,
                        "FAIL",
                        checked_count,
                    )
                )
                return QuotientCheck("FAIL", tuple(obligations))
            obligations.append(
                QuotientObligation(
                    "edge_has_witness",
                    transfer.source_layer,
                    class_spec.label,
                    "PASS",
                    checked_count,
                )
            )
    return QuotientCheck("PASS", tuple(obligations))


def _canonical_to_original(layer: object, side: str) -> dict[str, str]:
    names = layer.input_variables if side == "input" else layer.output_variables
    return {canonical_variable(name, layer, side): name for name in names}


def _z3_layer_problem(
    inputs: T28Inputs,
    transfer_number: int,
) -> tuple[object, object, dict[str, object], tuple[object, ...], object]:
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("T28 exact checks require z3-solver") from error
    transfer = inputs.frontier.layers_by_number[transfer_number]
    try:
        equations = tuple(
            inputs.manifest.by_provenance[provenance]
            for provenance in transfer.equation_provenances
        )
    except KeyError as error:
        raise EvidenceError(f"T28 transfer references unknown equation: {error.args[0]}") from error
    names = sorted(
        set(transfer.input_variables)
        | set(transfer.output_variables)
        | {name for equation in equations for name in equation.variables}
    )
    variables = {
        name: z3.Int(
            "t28_"
            + str(transfer_number)
            + "_"
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
            constraints.extend((variable >= lower, variable < inputs.manifest.base))
    for equation in equations:
        constraints.append(equation.residual(variables, inputs.manifest.base) == 0)
    return z3, transfer, variables, tuple(constraints), equations


def _z3_atom_formula(
    z3: object,
    atom: object,
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
            f"decision atom references unknown variable: {error.args[0]}"
        ) from error
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    if atom.relation == "congruent":
        return (total - atom.constant) % atom.modulus == 0
    raise EvidenceError(f"unsupported decision relation: {atom.relation}")


def _z3_classifier(
    z3: object,
    layer: LayerQuotient,
    canonical_to_original: Mapping[str, str],
    variables: Mapping[str, object],
) -> tuple[object, dict[str, int]]:
    codes = {class_spec.label: index for index, class_spec in enumerate(layer.classes)}
    expressions: dict[int, object] = {}

    def target_expression(target: str) -> object:
        if target == "outside":
            return z3.IntVal(-1)
        kind, value = target.split(":", 1)
        if kind == "class":
            return z3.IntVal(codes[value])
        return expressions[int(value)]

    for node in reversed(layer.nodes):
        expressions[node.node_id] = z3.If(
            _z3_atom_formula(z3, node.atom, canonical_to_original, variables),
            target_expression(node.when_true),
            target_expression(node.when_false),
        )
    if layer.root == "outside":
        return z3.IntVal(-1), codes
    root_kind, root_value = layer.root.split(":", 1)
    if root_kind == "class":
        return z3.IntVal(codes[root_value]), codes
    return expressions[int(root_value)], codes


def _check_status(z3: object, solver: object, context: str) -> object:
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(f"{context} returned UNKNOWN: {solver.reason_unknown()}")
    return status


def _lexicographic_model(
    z3: object,
    solver: object,
    variables: Mapping[str, object],
    ordered_names: tuple[str, ...],
    base: int,
) -> object:
    if _check_status(z3, solver, "counterexample search") != z3.sat:
        raise EvidenceError("cannot canonicalize an UNSAT counterexample")
    for name in ordered_names:
        domain = range(2) if name.startswith("c:") else range(base)
        for value in domain:
            solver.push()
            solver.add(variables[name] == value)
            status = _check_status(z3, solver, "counterexample minimization")
            solver.pop()
            if status == z3.sat:
                solver.add(variables[name] == value)
                break
        else:
            raise EvidenceError(f"counterexample variable has no value: {name}")
    if _check_status(z3, solver, "counterexample finalization") != z3.sat:
        raise EvidenceError("canonical counterexample became inconsistent")
    return solver.model()


def _model_state(
    model: object,
    variables: Mapping[str, object],
    canonical_to_original: Mapping[str, str],
) -> dict[str, int]:
    return {
        canonical: model.eval(variables[original], model_completion=True).as_long()
        for canonical, original in canonical_to_original.items()
    }


def _domain_size(names: tuple[str, ...], base: int) -> int:
    result = 1
    for name in names:
        result *= 2 if name.startswith("c:") else base
    return result


def check_reachable_coverage(
    inputs: T28Inputs,
    layer: LayerQuotient,
) -> QuotientCheck:
    """Require every promoted state at a named cut to avoid outside."""
    promoted = inputs.frontier.layers_by_number[layer.layer]
    expected_variables = _canonical_variables(inputs, layer.layer)
    if layer.variables != expected_variables:
        raise EvidenceError("quotient variables differ from the promoted frontier")
    for state in promoted.output_states:
        assignment = canonicalize_state(promoted, "output", state)
        if classify_state(layer, assignment) == "outside":
            return QuotientCheck(
                "FAIL",
                (
                    QuotientObligation(
                        "promoted_coverage",
                        layer.layer,
                        "ALL",
                        "FAIL",
                        promoted.output_state_count,
                        {"input": assignment},
                    ),
                ),
            )
    return QuotientCheck(
        "PASS",
        (
            QuotientObligation(
                "promoted_coverage",
                layer.layer,
                "ALL",
                "PASS",
                promoted.output_state_count,
            ),
        ),
    )


def check_terminal_classes(
    inputs: T28Inputs,
    terminal: LayerQuotient,
) -> QuotientCheck:
    """Exclude each effective terminal class with all 12 layer-33 equations."""
    if terminal.layer != 32 or any(item.kind != "terminal" for item in terminal.classes):
        raise EvidenceError("terminal checker requires the layer-32 terminal seed")
    z3, transfer, variables, constraints, _ = _z3_layer_problem(inputs, 33)
    input_mapping = _canonical_to_original(transfer, "input")
    if terminal.variables != tuple(input_mapping):
        raise EvidenceError("terminal variables differ from the layer-33 input")
    classifier, codes = _z3_classifier(z3, terminal, input_mapping, variables)
    checked_count = _domain_size(transfer.input_variables, inputs.manifest.base)
    obligations = []
    for class_spec in terminal.classes:
        solver = z3.Solver()
        solver.add(*constraints, classifier == codes[class_spec.label])
        status = _check_status(z3, solver, "terminal exclusion")
        if status == z3.sat:
            model = _lexicographic_model(
                z3,
                solver,
                variables,
                transfer.input_variables,
                inputs.manifest.base,
            )
            obligations.append(
                QuotientObligation(
                    "terminal_exclusion",
                    32,
                    class_spec.label,
                    "FAIL",
                    checked_count,
                    {"input": _model_state(model, variables, input_mapping)},
                )
            )
            return QuotientCheck("FAIL", tuple(obligations))
        obligations.append(
            QuotientObligation(
                "terminal_exclusion",
                32,
                class_spec.label,
                "PASS",
                checked_count,
            )
        )
    return QuotientCheck("PASS", tuple(obligations))


def _contains_quantifier(z3: object, expression: object) -> bool:
    if z3.is_quantifier(expression):
        return True
    return any(_contains_quantifier(z3, child) for child in expression.children())


def _project_successor_relation(
    z3: object,
    variables: Mapping[str, object],
    input_names: tuple[str, ...],
    constraints: tuple[object, ...],
) -> object:
    quantified = [variables[name] for name in variables if name not in input_names]
    relation = z3.And(*constraints)
    if not quantified:
        return relation
    goal = z3.Goal()
    goal.add(z3.Exists(quantified, relation))
    try:
        projected = z3.Tactic("qe")(goal).as_expr()
    except z3.Z3Exception as error:
        raise EvidenceError(f"successor projection failed: {error}") from error
    if _contains_quantifier(z3, projected):
        raise EvidenceError("successor projection retained a quantifier")
    return projected


def _witness_holds(
    inputs: T28Inputs,
    current: LayerQuotient,
    following: LayerQuotient,
    transfer: object,
    equations: tuple[object, ...],
    witness: EdgeWitness,
) -> bool:
    input_mapping = _canonical_to_original(transfer, "input")
    output_mapping = _canonical_to_original(transfer, "output")
    assignment = {
        input_mapping[name]: value for name, value in witness.input_state
    } | {output_mapping[name]: value for name, value in witness.output_state} | dict(
        witness.local_state
    )
    equation_names = {name for equation in equations for name in equation.variables}
    all_names = set(transfer.input_variables) | set(transfer.output_variables) | equation_names
    if set(assignment) != all_names:
        return False
    for name, value in assignment.items():
        if name.startswith("c:"):
            if value not in (0, 1):
                return False
        else:
            lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
            if not lower <= value < inputs.manifest.base:
                return False
    if any(equation.residual(assignment, inputs.manifest.base) != 0 for equation in equations):
        return False
    return (
        witness.source_layer == current.layer
        and classify_state(current, dict(witness.input_state)) == witness.source_class
        and classify_state(following, dict(witness.output_state)) == witness.target_class
    )


def check_layer_semantics(
    inputs: T28Inputs,
    current: LayerQuotient,
    following: LayerQuotient,
    witnesses: tuple[EdgeWitness, ...],
) -> QuotientCheck:
    """Check one symbolic quotient transfer over the complete bounded domain."""
    if following.layer != current.layer + 1:
        raise EvidenceError("quotient layers must be consecutive")
    z3, transfer, variables, constraints, equations = _z3_layer_problem(
        inputs, following.layer
    )
    input_mapping = _canonical_to_original(transfer, "input")
    output_mapping = _canonical_to_original(transfer, "output")
    if current.variables != tuple(input_mapping) or following.variables != tuple(output_mapping):
        raise EvidenceError("quotient variables differ from the exact transfer")
    source_classifier, source_codes = _z3_classifier(
        z3, current, input_mapping, variables
    )
    target_classifier, target_codes = _z3_classifier(
        z3, following, output_mapping, variables
    )
    checked_count = _domain_size(transfer.input_variables, inputs.manifest.base)
    obligations = []
    projected_relation: object | None = None
    witness_by_edge = {
        (item.source_class, item.target_class): item for item in witnesses
    }

    for class_spec in current.classes:
        source_formula = source_classifier == source_codes[class_spec.label]
        if class_spec.kind == "dead":
            solver = z3.Solver()
            solver.add(*constraints, source_formula)
            status = _check_status(z3, solver, "dead-class exclusion")
            if status == z3.sat:
                ordered = tuple(
                    dict.fromkeys(
                        (*transfer.input_variables, *transfer.output_variables, *variables)
                    )
                )
                model = _lexicographic_model(
                    z3, solver, variables, ordered, inputs.manifest.base
                )
                return QuotientCheck(
                    "FAIL",
                    (
                        *obligations,
                        QuotientObligation(
                            "dead_has_no_successor",
                            current.layer,
                            class_spec.label,
                            "FAIL",
                            checked_count,
                            {
                                "input": _model_state(model, variables, input_mapping),
                                "output": _model_state(model, variables, output_mapping),
                            },
                        ),
                    ),
                )
            obligations.append(
                QuotientObligation(
                    "dead_has_no_successor",
                    current.layer,
                    class_spec.label,
                    "PASS",
                    checked_count,
                )
            )
            continue
        if class_spec.kind != "live":
            raise EvidenceError("nonterminal source class must be live or dead")

        if projected_relation is None:
            projected_relation = _project_successor_relation(
                z3, variables, transfer.input_variables, constraints
            )
        solver = z3.Solver()
        solver.add(source_formula, z3.Not(projected_relation))
        status = _check_status(z3, solver, "live successor existence")
        if status == z3.sat:
            model = _lexicographic_model(
                z3,
                solver,
                variables,
                transfer.input_variables,
                inputs.manifest.base,
            )
            return QuotientCheck(
                "FAIL",
                (
                    *obligations,
                    QuotientObligation(
                        "live_has_successor",
                        current.layer,
                        class_spec.label,
                        "FAIL",
                        checked_count,
                        {"input": _model_state(model, variables, input_mapping)},
                    ),
                ),
            )
        obligations.append(
            QuotientObligation(
                "live_has_successor",
                current.layer,
                class_spec.label,
                "PASS",
                checked_count,
            )
        )

        allowed_codes = [target_codes[label] for label in class_spec.allowed_next]
        solver = z3.Solver()
        solver.add(
            *constraints,
            source_formula,
            z3.Not(z3.Or(*(target_classifier == code for code in allowed_codes))),
        )
        status = _check_status(z3, solver, "forbidden successor")
        if status == z3.sat:
            ordered = tuple(
                dict.fromkeys(
                    (*transfer.input_variables, *transfer.output_variables, *variables)
                )
            )
            model = _lexicographic_model(
                z3, solver, variables, ordered, inputs.manifest.base
            )
            return QuotientCheck(
                "FAIL",
                (
                    *obligations,
                    QuotientObligation(
                        "forbidden_successor",
                        current.layer,
                        class_spec.label,
                        "FAIL",
                        checked_count,
                        {
                            "input": _model_state(model, variables, input_mapping),
                            "output": _model_state(model, variables, output_mapping),
                        },
                    ),
                ),
            )
        obligations.append(
            QuotientObligation(
                "forbidden_successor",
                current.layer,
                class_spec.label,
                "PASS",
                checked_count,
            )
        )

        for target_label in class_spec.allowed_next:
            witness = witness_by_edge.get((class_spec.label, target_label))
            if witness is None or not _witness_holds(
                inputs, current, following, transfer, equations, witness
            ):
                return QuotientCheck(
                    "FAIL",
                    (
                        *obligations,
                        QuotientObligation(
                            "edge_has_witness",
                            current.layer,
                            class_spec.label,
                            "FAIL",
                            checked_count,
                        ),
                    ),
                )
            obligations.append(
                QuotientObligation(
                    "edge_has_witness",
                    current.layer,
                    class_spec.label,
                    "PASS",
                    checked_count,
                )
            )
    return QuotientCheck("PASS", tuple(obligations))


def check_quotient_certificate(
    inputs: T28Inputs,
    certificate: QuotientCertificate,
) -> QuotientCheck:
    """Check identity, promoted coverage, transfers, and terminal exclusion."""
    if certificate.base != inputs.manifest.base:
        raise EvidenceError("quotient certificate base differs from frozen inputs")
    if certificate.removed != inputs.frontier.removed:
        raise EvidenceError("quotient certificate removal differs from frozen inputs")
    expected_digests = {
        "equations": inputs.manifest.content_sha256,
        "frontier": inputs.frontier.content_sha256,
        "provenances": inputs.frontier.provenances_sha256,
        "t27_evidence": inputs.t27_evidence_sha256,
    }
    if dict(certificate.source_digests) != expected_digests:
        raise EvidenceError("quotient certificate source digests differ")

    obligations = []
    for layer in certificate.layers:
        coverage = check_reachable_coverage(inputs, layer)
        obligations.extend(coverage.obligations)
        if coverage.status != "PASS":
            return QuotientCheck("FAIL", tuple(obligations))
    for current, following in zip(certificate.layers, certificate.layers[1:], strict=False):
        layer_witnesses = tuple(
            witness
            for witness in certificate.witnesses
            if witness.source_layer == current.layer
        )
        check = check_layer_semantics(
            inputs,
            current,
            following,
            layer_witnesses,
        )
        obligations.extend(check.obligations)
        if check.status != "PASS":
            return QuotientCheck("FAIL", tuple(obligations))
    terminal = check_terminal_classes(inputs, certificate.layers[-1])
    obligations.extend(terminal.obligations)
    return QuotientCheck(terminal.status, tuple(obligations))


def _extract_edge_witnesses(
    inputs: T28Inputs,
    current: LayerQuotient,
    following: LayerQuotient,
) -> tuple[EdgeWitness, ...]:
    z3, transfer, variables, constraints, _ = _z3_layer_problem(inputs, following.layer)
    input_mapping = _canonical_to_original(transfer, "input")
    output_mapping = _canonical_to_original(transfer, "output")
    source_classifier, source_codes = _z3_classifier(
        z3, current, input_mapping, variables
    )
    target_classifier, target_codes = _z3_classifier(
        z3, following, output_mapping, variables
    )
    frontier_names = set(transfer.input_variables) | set(transfer.output_variables)
    local_names = tuple(sorted(set(variables) - frontier_names))
    ordered_names = tuple(
        dict.fromkeys((*transfer.input_variables, *transfer.output_variables, *local_names))
    )
    witnesses = []
    for class_spec in current.classes:
        for target_label in class_spec.allowed_next:
            solver = z3.Solver()
            solver.add(
                *constraints,
                source_classifier == source_codes[class_spec.label],
                target_classifier == target_codes[target_label],
            )
            status = _check_status(z3, solver, "edge witness extraction")
            if status != z3.sat:
                raise EvidenceError(
                    f"declared quotient edge has no exact model: "
                    f"{class_spec.label}->{target_label}"
                )
            model = _lexicographic_model(
                z3,
                solver,
                variables,
                ordered_names,
                inputs.manifest.base,
            )
            witnesses.append(
                EdgeWitness(
                    current.layer,
                    class_spec.label,
                    target_label,
                    tuple(sorted(
                        (canonical, model.eval(variables[original]).as_long())
                        for canonical, original in input_mapping.items()
                    )),
                    tuple(sorted(
                        (canonical, model.eval(variables[original]).as_long())
                        for canonical, original in output_mapping.items()
                    )),
                    tuple(sorted(
                        (name, model.eval(variables[name]).as_long())
                        for name in local_names
                    )),
                )
            )
    return tuple(witnesses)


def _fallback_counterexample(partition: CandidatePartition, reason: str) -> GuardCounterexample:
    first = partition.classes[0]
    other = next(item for item in partition.classes[1:] if item.members)
    return GuardCounterexample(other.members[0], first.label, reason)


def synthesize_layer(
    inputs: T28Inputs,
    partition: CandidatePartition,
    following: LayerQuotient,
    limits: GuardLimits,
) -> LayerSynthesis:
    """Refine one promoted quotient partition from exact semantic models."""
    counterexamples: tuple[GuardCounterexample, ...] = ()
    atoms = derive_guard_atoms(partition, (), limits)
    atom_count = len(atoms)
    iteration = 0
    while True:
        iteration += 1
        try:
            quotient = build_reduced_decision_dag(
                partition,
                atoms,
                limits,
                outside_members=tuple(item.state for item in counterexamples),
            )
        except GuardSynthesisError as error:
            return LayerSynthesis(
                "STOP",
                partition.layer,
                None,
                (),
                iteration,
                atom_count,
                error.reason,
                counterexamples[-1]
                if counterexamples
                else _fallback_counterexample(partition, error.reason),
            )
        coverage = check_reachable_coverage(inputs, quotient)
        if coverage.status != "PASS":
            raise EvidenceError("learned quotient misses its promoted training states")
        witnesses = _extract_edge_witnesses(inputs, quotient, following)
        exact = check_layer_semantics(inputs, quotient, following, witnesses)
        if exact.status == "PASS":
            return LayerSynthesis(
                "PASS",
                partition.layer,
                quotient,
                witnesses,
                iteration,
                atom_count,
            )
        obligation = exact.obligations[-1]
        if obligation.counterexample is None or "input" not in obligation.counterexample:
            raise EvidenceError("failed exact guard check omitted its input counterexample")
        state = tuple(
            obligation.counterexample["input"][variable]
            for variable in partition.variables
        )
        counterexample = GuardCounterexample(
            state,
            obligation.class_label,
            obligation.kind,
        )
        if counterexample in counterexamples:
            return LayerSynthesis(
                "STOP",
                partition.layer,
                None,
                (),
                iteration,
                atom_count,
                "counterexample_cycle",
                counterexample,
            )
        class_spec = next(
            item
            for item in partition.classes
            if item.label == counterexample.rejected_class
        )
        atom = _derive_separator_atom(
            partition,
            class_spec,
            counterexample.state,
            limits,
        )
        if atom is None:
            return LayerSynthesis(
                "STOP",
                partition.layer,
                None,
                (),
                iteration,
                atom_count,
                "guard_separator_not_found",
                counterexample,
            )
        atoms = tuple(sorted({*atoms, atom}, key=canonical_bytes))
        atom_count = len(atoms)
        counterexamples = (*counterexamples, counterexample)


def build_layer31_milestone(root: Path) -> LayerSynthesis:
    """Prove or finitely stop the exact four-class layer-31 milestone."""
    inputs = load_t28_inputs(root)
    partitions = discover_reachable_quotient(inputs, 31, 32)
    partition = partitions[0]
    if len(partition.classes) != 4 or sorted(
        len(item.members) for item in partition.classes
    ) != [1, 2, 3, 12]:
        raise EvidenceError("layer-31 candidate partition changed")
    terminal = build_terminal_seed(inputs)
    terminal_check = check_terminal_classes(inputs, terminal)
    if terminal_check.status != "PASS":
        raise EvidenceError("terminal seed failed before layer-31 synthesis")
    return synthesize_layer(inputs, partition, terminal, GuardLimits())


def load_t28_inputs(
    root: Path,
    *,
    t27_evidence_path: Path | None = None,
) -> T28Inputs:
    """Bind T28 to the exact promoted obstruction and achieved T27 lemma."""
    root = Path(root)
    manifest, frontier = load_promoted_inputs(root)
    if manifest.content_sha256 != _EQUATIONS_CONTENT_SHA256:
        raise EvidenceError("T28 equation content digest changed")
    if frontier.content_sha256 != _FRONTIER_CONTENT_SHA256:
        raise EvidenceError("T28 frontier content digest changed")
    if frontier.provenances_sha256 != _PROVENANCES_SHA256:
        raise EvidenceError("T28 provenance digest changed")
    evidence_path = t27_evidence_path or (
        root / ".timeloop" / "runs" / "t27_base19_invariant_lift.json"
    )
    try:
        evidence_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    except OSError as error:
        raise EvidenceError(f"cannot read frozen T27 evidence: {error}") from error
    if evidence_digest != _T27_EVIDENCE_SHA256:
        raise EvidenceError("T28 frozen T27 evidence digest changed")
    terminal_predicate = synthesize_terminal_predicate(
        (manifest, frontier),
        GrammarLimits(),
    )
    return T28Inputs(
        manifest=manifest,
        frontier=frontier,
        terminal_predicate=terminal_predicate,
        t27_evidence_sha256=evidence_digest,
    )


def _terminal_family_label(clause: object) -> str:
    atoms = clause.atoms
    if any(atom.relation == "congruent" and atom.modulus == 19 for atom in atoms):
        return "T_RESIDUE"
    if any(
        atom.relation == "eq" and atom.constant == 13 and len(atom.terms) == 4
        for atom in atoms
    ):
        return "T_PHASE_ZERO"
    if any(
        atom.relation == "eq"
        and atom.constant == 14
        and any(name == "D0" for name, _ in atom.terms)
        for atom in atoms
    ):
        return "T_HIGH_DIGIT"
    raise EvidenceError("T27 terminal clause cannot be assigned a semantic name")


def build_terminal_seed(inputs: T28Inputs) -> LayerQuotient:
    """Compile the three independently checked T27 clauses into one DAG."""
    predicate = inputs.terminal_predicate
    families = {_terminal_family_label(clause): clause for clause in predicate.clauses}
    expected = {"T_HIGH_DIGIT", "T_PHASE_ZERO", "T_RESIDUE"}
    if set(families) != expected or len(families) != len(predicate.clauses):
        raise EvidenceError("T27 terminal family names are not unique and complete")
    ordered = tuple(sorted(families.items()))
    starts: dict[str, int] = {}
    offset = 0
    for label, clause in ordered:
        starts[label] = offset
        offset += len(clause.atoms)

    nodes = []
    for family_index, (label, clause) in enumerate(ordered):
        fallback = (
            f"node:{starts[ordered[family_index + 1][0]]}"
            if family_index + 1 < len(ordered)
            else "outside"
        )
        start = starts[label]
        for atom_index, atom in enumerate(clause.atoms):
            node_id = start + atom_index
            success = (
                f"node:{node_id + 1}"
                if atom_index + 1 < len(clause.atoms)
                else f"class:{label}"
            )
            nodes.append(DecisionNode(node_id, atom, success, fallback))

    seed = LayerQuotient(
        layer=32,
        variables=predicate.variables,
        root="node:0",
        classes=tuple(ClassSpec(label, "terminal", ()) for label in sorted(expected)),
        nodes=tuple(nodes),
    )
    layer32 = inputs.frontier.layers_by_number[32]
    labels = tuple(
        classify_state(seed, canonicalize_state(layer32, "output", state))
        for state in layer32.output_states
    )
    if "outside" in labels or sorted(labels.count(label) for label in set(labels)) != [6, 8, 8]:
        raise EvidenceError("compiled terminal seed changed promoted family coverage")
    return seed


def _canonical_variables(inputs: T28Inputs, layer_number: int) -> tuple[str, ...]:
    layer = inputs.frontier.layers_by_number[layer_number]
    if not layer.output_states:
        return ()
    return tuple(canonicalize_state(layer, "output", layer.output_states[0]))


def discover_reachable_quotient(
    inputs: T28Inputs,
    start_layer: int = 25,
    end_layer: int = 32,
) -> tuple[CandidatePartition, ...]:
    """Group promoted states by exact successor-class signatures."""
    if not 25 <= start_layer <= end_layer or end_layer != 32:
        raise ValueError("reachable quotient discovery requires layers start..32")
    seed = build_terminal_seed(inputs)
    layer32 = inputs.frontier.layers_by_number[32]
    terminal_groups: dict[str, list[tuple[int, ...]]] = {}
    labels_by_state: dict[tuple[int, ...], str] = {}
    for state in layer32.output_states:
        label = classify_state(seed, canonicalize_state(layer32, "output", state))
        if label == "outside":
            raise EvidenceError("terminal seed misses a promoted layer-32 state")
        terminal_groups.setdefault(label, []).append(state)
        labels_by_state[state] = label
    partitions: dict[int, CandidatePartition] = {
        32: CandidatePartition(
            layer=32,
            variables=seed.variables,
            classes=tuple(
                CandidateClass(label, (), tuple(sorted(members)))
                for label, members in sorted(terminal_groups.items())
            ),
        )
    }

    for layer_number in range(31, start_layer - 1, -1):
        source_layer = inputs.frontier.layers_by_number[layer_number]
        transfer = inputs.frontier.layers_by_number[layer_number + 1]
        transitions = {item.input_state: item.output_states for item in transfer.transitions}
        if set(transitions) != set(source_layer.output_states):
            raise EvidenceError(f"layer {layer_number} transition inputs changed")
        grouped: dict[tuple[str, ...], list[tuple[int, ...]]] = {}
        for state in source_layer.output_states:
            try:
                signature = tuple(
                    sorted({labels_by_state[output] for output in transitions[state]})
                )
            except KeyError as error:
                raise EvidenceError(
                    f"layer {layer_number} successor lacks a quotient label"
                ) from error
            grouped.setdefault(signature, []).append(state)

        classes = []
        state_labels: dict[tuple[int, ...], str] = {}
        live_index = 0
        for signature, members in sorted(grouped.items()):
            if signature:
                label = f"Q{live_index:02d}"
                live_index += 1
            else:
                label = "DEAD"
            ordered_members = tuple(sorted(members))
            classes.append(CandidateClass(label, signature, ordered_members))
            state_labels.update({member: label for member in ordered_members})
        partitions[layer_number] = CandidatePartition(
            layer=layer_number,
            variables=_canonical_variables(inputs, layer_number),
            classes=tuple(classes),
        )
        labels_by_state = state_labels
    return tuple(partitions[layer] for layer in range(start_layer, end_layer + 1))


def explicit_relation_payload(
    inputs: T28Inputs,
    start_layer: int,
    end_layer: int,
) -> dict[str, object]:
    """Serialize only promoted states and exact edges for size comparison."""
    if not 25 <= start_layer <= end_layer <= 32:
        raise ValueError("explicit relation interval must lie in 25..32")
    layers = []
    for layer_number in range(start_layer, end_layer + 1):
        source = inputs.frontier.layers_by_number[layer_number]
        transfer = inputs.frontier.layers_by_number[layer_number + 1]
        states = [
            list(canonicalize_state(source, "output", state).values())
            for state in source.output_states
        ]
        edges = []
        for transition in transfer.transitions:
            source_values = list(
                canonicalize_state(transfer, "input", transition.input_state).values()
            )
            for output in transition.output_states:
                edges.append(
                    {
                        "input": source_values,
                        "output": list(
                            canonicalize_state(transfer, "output", output).values()
                        ),
                    }
                )
        edges.sort(key=lambda item: (item["input"], item["output"]))
        layers.append(
            {
                "layer": layer_number,
                "variables": list(_canonical_variables(inputs, layer_number)),
                "next_variables": list(
                    canonicalize_state(transfer, "output", transfer.output_states[0])
                    if transfer.output_states
                    else ()
                ),
                "states": states,
                "edges": edges,
            }
        )
    return {"layers": layers}
