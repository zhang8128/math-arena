#!/usr/bin/env python3
"""Construct and verify a symbolic quotient for the frozen base-19 tail."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from lychrel_invariant_certificate import LayerPredicate
from lychrel_quotient_automaton import (
    ClassSpec,
    DecisionNode,
    LayerQuotient,
    classify_state,
)
from t27_base19_invariant_lift import (
    EquationManifest,
    EvidenceError,
    FrontierCertificate,
    GrammarLimits,
    canonicalize_state,
    load_promoted_inputs,
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
