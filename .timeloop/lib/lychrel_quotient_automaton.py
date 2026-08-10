"""Typed symbolic quotient automata for radial reverse-add frontiers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from lychrel_invariant_certificate import LinearAtom

_LABEL_RE = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_CLASS_KINDS = frozenset({"live", "dead", "terminal"})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class ClassSpec:
    label: str
    kind: str
    allowed_next: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "label": self.label,
            "kind": self.kind,
            "allowed_next": list(self.allowed_next),
        }


@dataclass(frozen=True)
class DecisionNode:
    node_id: int
    atom: LinearAtom
    when_true: str
    when_false: str

    def to_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "atom": self.atom.to_payload(),
            "when_true": self.when_true,
            "when_false": self.when_false,
        }


@dataclass(frozen=True)
class LayerQuotient:
    layer: int
    variables: tuple[str, ...]
    root: str
    classes: tuple[ClassSpec, ...]
    nodes: tuple[DecisionNode, ...]

    def __post_init__(self) -> None:
        if not _is_int(self.layer):
            raise ValueError("layer must be an integer")
        if not self.variables or any(
            not isinstance(variable, str) or not variable for variable in self.variables
        ):
            raise ValueError("layer variables must be nonempty strings")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("layer variables must be unique")
        if not 1 <= len(self.classes) <= 8:
            raise ValueError("a layer must contain between one and eight classes")

        labels: set[str] = set()
        for class_spec in self.classes:
            if not _LABEL_RE.fullmatch(class_spec.label):
                raise ValueError(f"invalid class label: {class_spec.label}")
            if class_spec.label in labels:
                raise ValueError(f"duplicate class label: {class_spec.label}")
            labels.add(class_spec.label)
            if class_spec.kind not in _CLASS_KINDS:
                raise ValueError(f"invalid class kind: {class_spec.kind}")
            if class_spec.kind == "live" and not class_spec.allowed_next:
                raise ValueError("a live class must declare an allowed edge")
            if class_spec.kind != "live" and class_spec.allowed_next:
                raise ValueError("dead and terminal classes may not declare edges")
            if (
                len(set(class_spec.allowed_next)) != len(class_spec.allowed_next)
                or class_spec.allowed_next != tuple(sorted(class_spec.allowed_next))
                or any(not _LABEL_RE.fullmatch(label) for label in class_spec.allowed_next)
            ):
                raise ValueError("allowed class labels must be canonical")

        if len(self.nodes) > 64:
            raise ValueError("a layer may contain at most 64 decision nodes")
        if tuple(node.node_id for node in self.nodes) != tuple(range(len(self.nodes))):
            raise ValueError("decision node IDs must be contiguous from zero")
        scope = set(self.variables)
        triples: set[tuple[LinearAtom, str, str]] = set()
        for node in self.nodes:
            if node.when_true == node.when_false:
                raise ValueError("a decision node may not have equal branches")
            if any(name not in scope for name, _ in node.atom.terms):
                raise ValueError("decision atom variables must be in layer scope")
            triple = (node.atom, node.when_true, node.when_false)
            if triple in triples:
                raise ValueError("decision DAG contains an unreduced duplicate subtree")
            triples.add(triple)
            self._validate_target(node.when_true, labels, minimum_node=node.node_id + 1)
            self._validate_target(node.when_false, labels, minimum_node=node.node_id + 1)
        self._validate_target(self.root, labels, minimum_node=0)

        reachable_nodes: set[int] = set()

        def visit(target: str) -> None:
            kind, value = _target_kind(target)
            if kind != "node":
                return
            node_id = int(value)
            if node_id in reachable_nodes:
                return
            reachable_nodes.add(node_id)
            node = self.nodes[node_id]
            visit(node.when_true)
            visit(node.when_false)

        visit(self.root)
        if reachable_nodes != set(range(len(self.nodes))):
            raise ValueError("decision DAG contains an unreachable node")
        if self.layer < 32 and layer_path_depth(self) > 10:
            raise ValueError("synthesized decision depth exceeds ten")

        object.__setattr__(
            self,
            "classes",
            tuple(sorted(self.classes, key=lambda item: item.label)),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "variables": list(self.variables),
            "root": self.root,
            "classes": [class_spec.to_payload() for class_spec in self.classes],
            "nodes": [node.to_payload() for node in self.nodes],
        }

    def _validate_target(
        self,
        target: str,
        labels: set[str],
        *,
        minimum_node: int,
    ) -> None:
        kind, value = _target_kind(target)
        if kind == "outside":
            return
        if kind == "class":
            if value not in labels:
                raise ValueError(f"decision target references unknown class: {value}")
            return
        node_id = int(value)
        if node_id < minimum_node:
            raise ValueError("decision node edges must point forward")
        if node_id >= len(self.nodes):
            raise ValueError(f"decision target references missing node: {node_id}")


def _target_kind(target: str) -> tuple[str, str]:
    if target == "outside":
        return "outside", ""
    if not isinstance(target, str):
        raise ValueError("decision targets must be strings")
    kind, separator, value = target.partition(":")
    if separator != ":" or kind not in {"node", "class"} or not value:
        raise ValueError(f"invalid decision target: {target}")
    if kind == "node" and (not value.isascii() or not value.isdigit()):
        raise ValueError(f"invalid decision node target: {target}")
    return kind, value


def _validate_assignment(
    assignment: tuple[tuple[str, int], ...],
    context: str,
) -> None:
    if tuple(sorted(assignment)) != assignment:
        raise ValueError(f"{context} assignment must be sorted")
    names: set[str] = set()
    for item in assignment:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"{context} assignment items must be pairs")
        name, value = item
        if not isinstance(name, str) or not name or name in names or not _is_int(value):
            raise ValueError(f"{context} assignment is invalid")
        names.add(name)


@dataclass(frozen=True)
class EdgeWitness:
    source_layer: int
    source_class: str
    target_class: str
    input_state: tuple[tuple[str, int], ...]
    output_state: tuple[tuple[str, int], ...]
    local_state: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not _is_int(self.source_layer):
            raise ValueError("witness source layer must be an integer")
        if not _LABEL_RE.fullmatch(self.source_class) or not _LABEL_RE.fullmatch(
            self.target_class
        ):
            raise ValueError("witness class labels are invalid")
        _validate_assignment(self.input_state, "witness input")
        _validate_assignment(self.output_state, "witness output")
        _validate_assignment(self.local_state, "witness local")

    def to_payload(self) -> dict[str, object]:
        return {
            "source_layer": self.source_layer,
            "source_class": self.source_class,
            "target_class": self.target_class,
            "input_state": dict(self.input_state),
            "output_state": dict(self.output_state),
            "local_state": dict(self.local_state),
        }


@dataclass(frozen=True)
class QuotientCertificate:
    schema: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    start_layer: int
    layers: tuple[LayerQuotient, ...]
    witnesses: tuple[EdgeWitness, ...]

    def __post_init__(self) -> None:
        if self.schema != "t28-tail-quotient-certificate-v1":
            raise ValueError(f"unsupported quotient certificate schema: {self.schema}")
        if not _is_int(self.base) or self.base < 2:
            raise ValueError("certificate base must be an integer at least two")
        if not isinstance(self.removed, str) or not self.removed:
            raise ValueError("certificate removed coordinate must be nonempty")
        if not _is_int(self.start_layer) or not 25 <= self.start_layer <= 31:
            raise ValueError("certificate start layer must be in 25..31")
        expected_digest_names = {"equations", "frontier", "provenances", "t27_evidence"}
        if dict(self.source_digests).keys() != expected_digest_names:
            raise ValueError("certificate source digest names differ")
        if tuple(sorted(self.source_digests)) != self.source_digests:
            raise ValueError("certificate source digests must be sorted")
        for name, digest in self.source_digests:
            if (
                not isinstance(name, str)
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(f"invalid certificate source digest: {name}")

        expected_layers = tuple(range(self.start_layer, 33))
        if tuple(layer.layer for layer in self.layers) != expected_layers:
            raise ValueError("certificate layers must be contiguous through layer 32")
        for layer in self.layers[:-1]:
            if any(class_spec.kind == "terminal" for class_spec in layer.classes):
                raise ValueError("only layer 32 may contain terminal classes")
        if any(class_spec.kind != "terminal" for class_spec in self.layers[-1].classes):
            raise ValueError("layer 32 must contain only terminal classes")

        declared_edges: set[tuple[int, str, str]] = set()
        layers_by_number = {layer.layer: layer for layer in self.layers}
        for layer, following in zip(self.layers, self.layers[1:], strict=False):
            following_labels = {class_spec.label for class_spec in following.classes}
            for class_spec in layer.classes:
                for target in class_spec.allowed_next:
                    if target not in following_labels:
                        raise ValueError(f"allowed edge references unknown next class: {target}")
                    declared_edges.add((layer.layer, class_spec.label, target))

        witness_edges = [
            (witness.source_layer, witness.source_class, witness.target_class)
            for witness in self.witnesses
        ]
        if len(set(witness_edges)) != len(witness_edges) or set(witness_edges) != declared_edges:
            raise ValueError("certificate witnesses must match declared edges exactly")
        for witness in self.witnesses:
            try:
                source = layers_by_number[witness.source_layer]
                target = layers_by_number[witness.source_layer + 1]
            except KeyError as error:
                raise ValueError("witness layer is outside the certificate") from error
            input_names = {name for name, _ in witness.input_state}
            output_names = {name for name, _ in witness.output_state}
            local_names = {name for name, _ in witness.local_state}
            if input_names != set(source.variables) or output_names != set(target.variables):
                raise ValueError("witness frontier assignment does not match its layer")
            if input_names & local_names or output_names & local_names:
                raise ValueError("witness local assignment overlaps a frontier")

        object.__setattr__(
            self,
            "witnesses",
            tuple(
                sorted(
                    self.witnesses,
                    key=lambda witness: (
                        witness.source_layer,
                        witness.source_class,
                        witness.target_class,
                        witness.input_state,
                        witness.output_state,
                        witness.local_state,
                    ),
                )
            ),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "start_layer": self.start_layer,
            "layers": [layer.to_payload() for layer in self.layers],
            "witnesses": [witness.to_payload() for witness in self.witnesses],
        }


def _atom_holds(atom: LinearAtom, assignment: Mapping[str, int]) -> bool:
    total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def classify_state(layer: LayerQuotient, assignment: Mapping[str, int]) -> str:
    """Follow a layer's decision DAG to a semantic class or outside."""
    if set(assignment) != set(layer.variables) or any(
        not _is_int(value) for value in assignment.values()
    ):
        raise ValueError("assignment must exactly match the integral layer scope")
    nodes = {node.node_id: node for node in layer.nodes}
    target = layer.root
    while target.startswith("node:"):
        node = nodes[int(target.removeprefix("node:"))]
        target = node.when_true if _atom_holds(node.atom, assignment) else node.when_false
    if target == "outside":
        return target
    return target.removeprefix("class:")


def layer_path_depth(layer: LayerQuotient) -> int:
    """Return the maximum number of decisions on a root-to-leaf path."""
    nodes = {node.node_id: node for node in layer.nodes}

    def depth(target: str) -> int:
        if not target.startswith("node:"):
            return 0
        node = nodes[int(target.removeprefix("node:"))]
        return 1 + max(depth(node.when_true), depth(node.when_false))

    return depth(layer.root)


def certificate_core_payload(certificate: QuotientCertificate) -> dict[str, object]:
    """Return only class guards and edges for explanatory-size comparison."""
    return {
        "start_layer": certificate.start_layer,
        "layers": [layer.to_payload() for layer in certificate.layers],
    }


def _require_exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{context} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _parse_atom(payload: object) -> LinearAtom:
    if not isinstance(payload, Mapping):
        raise ValueError("decision atom must be an object")
    relation = payload.get("relation")
    expected = {"relation", "terms", "constant"}
    if relation == "congruent":
        expected.add("modulus")
    _require_exact_keys(payload, expected, "decision atom")
    terms_payload = payload["terms"]
    if not isinstance(terms_payload, list):
        raise ValueError("decision atom terms must be a list")
    terms: list[tuple[str, int]] = []
    for term in terms_payload:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("decision atom terms must be two-item lists")
        name, coefficient = term
        if not isinstance(name, str) or not _is_int(coefficient):
            raise ValueError("decision atom term is invalid")
        terms.append((name, coefficient))
    constant = payload["constant"]
    modulus = payload.get("modulus")
    if not _is_int(constant) or (modulus is not None and not _is_int(modulus)):
        raise ValueError("decision atom constant or modulus is invalid")
    return LinearAtom(
        relation=relation,  # type: ignore[arg-type]
        terms=tuple(terms),
        constant=constant,
        modulus=modulus,  # type: ignore[arg-type]
    )


def _parse_class(payload: object) -> ClassSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("class specification must be an object")
    _require_exact_keys(payload, {"label", "kind", "allowed_next"}, "class")
    allowed = payload["allowed_next"]
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise ValueError("class allowed_next must be a list of strings")
    return ClassSpec(
        label=payload["label"],  # type: ignore[arg-type]
        kind=payload["kind"],  # type: ignore[arg-type]
        allowed_next=tuple(allowed),
    )


def _parse_node(payload: object) -> DecisionNode:
    if not isinstance(payload, Mapping):
        raise ValueError("decision node must be an object")
    _require_exact_keys(
        payload,
        {"node_id", "atom", "when_true", "when_false"},
        "decision node",
    )
    node_id = payload["node_id"]
    if not _is_int(node_id):
        raise ValueError("decision node ID must be an integer")
    return DecisionNode(
        node_id=node_id,
        atom=_parse_atom(payload["atom"]),
        when_true=payload["when_true"],  # type: ignore[arg-type]
        when_false=payload["when_false"],  # type: ignore[arg-type]
    )


def _parse_layer(payload: object) -> LayerQuotient:
    if not isinstance(payload, Mapping):
        raise ValueError("quotient layer must be an object")
    _require_exact_keys(
        payload,
        {"layer", "variables", "root", "classes", "nodes"},
        "quotient layer",
    )
    layer = payload["layer"]
    variables = payload["variables"]
    classes = payload["classes"]
    nodes = payload["nodes"]
    if not _is_int(layer):
        raise ValueError("serialized layer number must be an integer")
    if not isinstance(variables, list) or any(
        not isinstance(variable, str) for variable in variables
    ):
        raise ValueError("serialized layer variables must be strings")
    if not isinstance(classes, list) or not isinstance(nodes, list):
        raise ValueError("serialized classes and nodes must be lists")
    return LayerQuotient(
        layer=layer,
        variables=tuple(variables),
        root=payload["root"],  # type: ignore[arg-type]
        classes=tuple(_parse_class(item) for item in classes),
        nodes=tuple(_parse_node(item) for item in nodes),
    )


def _parse_assignment(payload: object, context: str) -> tuple[tuple[str, int], ...]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{context} assignment must be an object")
    result = []
    for name, value in payload.items():
        if not isinstance(name, str) or not _is_int(value):
            raise ValueError(f"{context} assignment is invalid")
        result.append((name, value))
    return tuple(sorted(result))


def _parse_witness(payload: object) -> EdgeWitness:
    if not isinstance(payload, Mapping):
        raise ValueError("edge witness must be an object")
    _require_exact_keys(
        payload,
        {
            "source_layer",
            "source_class",
            "target_class",
            "input_state",
            "output_state",
            "local_state",
        },
        "edge witness",
    )
    source_layer = payload["source_layer"]
    if not _is_int(source_layer):
        raise ValueError("witness source layer must be an integer")
    return EdgeWitness(
        source_layer=source_layer,
        source_class=payload["source_class"],  # type: ignore[arg-type]
        target_class=payload["target_class"],  # type: ignore[arg-type]
        input_state=_parse_assignment(payload["input_state"], "witness input"),
        output_state=_parse_assignment(payload["output_state"], "witness output"),
        local_state=_parse_assignment(payload["local_state"], "witness local"),
    )


def parse_quotient_certificate(payload: object) -> QuotientCertificate:
    """Strictly parse one canonical T28 quotient certificate."""
    if not isinstance(payload, Mapping):
        raise ValueError("quotient certificate must be an object")
    _require_exact_keys(
        payload,
        {
            "schema",
            "base",
            "removed",
            "source_digests",
            "start_layer",
            "layers",
            "witnesses",
        },
        "quotient certificate",
    )
    digests = payload["source_digests"]
    layers = payload["layers"]
    witnesses = payload["witnesses"]
    if not isinstance(digests, Mapping):
        raise ValueError("certificate source_digests must be an object")
    if not isinstance(layers, list) or not isinstance(witnesses, list):
        raise ValueError("certificate layers and witnesses must be lists")
    base = payload["base"]
    start_layer = payload["start_layer"]
    if not _is_int(base) or not _is_int(start_layer):
        raise ValueError("certificate base and start_layer must be integers")
    digest_items = []
    for name, digest in digests.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError("certificate source digest entries must be strings")
        digest_items.append((name, digest))
    return QuotientCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        base=base,
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=tuple(sorted(digest_items)),
        start_layer=start_layer,
        layers=tuple(_parse_layer(item) for item in layers),
        witnesses=tuple(_parse_witness(item) for item in witnesses),
    )
