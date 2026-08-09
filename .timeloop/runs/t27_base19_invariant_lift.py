#!/usr/bin/env python3
"""Synthesize and audit compact invariants for the base-19 radial core."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_invariant_certificate import (  # noqa: E402
    InvariantCertificate,
    LayerPredicate,
    LinearAtom,
    evaluate_predicate,
)

_EQUATIONS_CONTENT_SHA256 = (
    "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"
)
_FRONTIER_CONTENT_SHA256 = (
    "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"
)
_PROVENANCES_SHA256 = (
    "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"
)
_REMOVED = "phase=0,n=0,column=82"
_PROVENANCE_RE = re.compile(r"phase=(?P<phase>\d+),n=0,column=(?P<column>\d+)\Z")
_DIGIT_RE = re.compile(r"(?:digit:)?p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z")
_CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n0:col(?P<column>\d+)\Z")


class EvidenceError(RuntimeError):
    """Frozen research evidence is malformed, changed, or inconsistent."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical_source_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot load {label}: {error}") from error
    if not isinstance(payload, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    return payload


def _verify_content_digest(
    payload: dict[str, object],
    expected_frozen: str,
    label: str,
) -> str:
    unsigned = dict(payload)
    claimed = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(_canonical_source_bytes(unsigned)).hexdigest()
    if claimed != actual:
        raise EvidenceError(f"{label} content digest mismatch")
    if actual != expected_frozen:
        raise EvidenceError(f"{label} frozen content digest changed")
    return actual


@dataclass(frozen=True)
class Atom:
    variable: str | None = None
    literal: int | None = None

    def __post_init__(self) -> None:
        if (self.variable is None) == (self.literal is None):
            raise EvidenceError("an equation atom must be exactly one of variable or literal")
        if self.variable is not None and not self.variable:
            raise EvidenceError("an equation variable must be nonempty")
        if self.literal is not None and not _is_int(self.literal):
            raise EvidenceError("an equation literal must be an integer")

    @property
    def key(self) -> str | None:
        return None if self.variable is None else f"digit:{self.variable}"

    def value(self, assignment: dict[str, int], base: int) -> int:
        if self.variable is not None:
            key = f"digit:{self.variable}"
            if key not in assignment:
                raise EvidenceError(f"assignment is missing {key}")
            return assignment[key]
        assert self.literal is not None
        return base - 1 if self.literal == 18 else self.literal

    def grouping_key(self) -> tuple[str, str | int]:
        if self.variable is not None:
            return ("variable", self.variable)
        assert self.literal is not None
        return ("literal", self.literal)


@dataclass(frozen=True)
class Equation:
    provenance: str
    left: Atom
    right: Atom
    target: Atom
    carry_in: str | None
    carry_out: str | None

    @cached_property
    def phase_column(self) -> tuple[int, int]:
        match = _PROVENANCE_RE.fullmatch(self.provenance)
        if match is None:
            raise EvidenceError(f"malformed equation provenance: {self.provenance}")
        return int(match["phase"]), int(match["column"])

    @cached_property
    def variables(self) -> tuple[str, ...]:
        result = []
        for atom in (self.left, self.right, self.target):
            if atom.key is not None:
                result.append(atom.key)
        for carry in (self.carry_in, self.carry_out):
            if carry is not None:
                result.append(carry)
        return tuple(dict.fromkeys(result))

    def residual(self, assignment: dict[str, int], base: int) -> int:
        carry_in = 0 if self.carry_in is None else assignment[self.carry_in]
        carry_out = 0 if self.carry_out is None else assignment[self.carry_out]
        return (
            self.left.value(assignment, base)
            + self.right.value(assignment, base)
            + carry_in
            - self.target.value(assignment, base)
            - base * carry_out
        )


@dataclass(frozen=True)
class EquationManifest:
    content_sha256: str
    file_sha256: str
    topology_sha256: str
    base: int
    equations: tuple[Equation, ...]
    fragment_lengths: tuple[tuple[int, ...], ...]

    @cached_property
    def by_provenance(self) -> dict[str, Equation]:
        return {equation.provenance: equation for equation in self.equations}


@dataclass(frozen=True)
class FrontierTransition:
    input_state: tuple[int, ...]
    output_states: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class FrontierLayer:
    number: int
    equation_provenances: tuple[str, ...]
    input_variables: tuple[str, ...]
    output_variables: tuple[str, ...]
    input_state_count: int
    output_state_count: int
    local_model_count: int
    output_states_sha256: str
    output_states: tuple[tuple[int, ...], ...]
    transitions: tuple[FrontierTransition, ...]

    @property
    def input_states(self) -> tuple[tuple[int, ...], ...]:
        return tuple(transition.input_state for transition in self.transitions)


@dataclass(frozen=True)
class FrontierCertificate:
    content_sha256: str
    equations_sha256: str
    provenances_sha256: str
    removed: str
    base: int
    layers: tuple[FrontierLayer, ...]

    @cached_property
    def layers_by_number(self) -> dict[int, FrontierLayer]:
        return {layer.number: layer for layer in self.layers}


@dataclass(frozen=True)
class ObligationResult:
    kind: str
    layer: int
    status: str
    checked_count: int
    counterexample: dict[str, dict[str, int]] | None = None


@dataclass(frozen=True)
class CertificateCheckResult:
    status: str
    obligations: tuple[ObligationResult, ...]


def _parse_atom(payload: object) -> Atom:
    if not isinstance(payload, dict):
        raise EvidenceError("equation atom must be an object")
    if set(payload) == {"variable"} and isinstance(payload["variable"], str):
        return Atom(variable=payload["variable"])
    if set(payload) == {"literal"} and _is_int(payload["literal"]):
        return Atom(literal=payload["literal"])
    raise EvidenceError("equation atom has invalid union shape")


def _parse_equation(payload: object) -> Equation:
    if not isinstance(payload, dict):
        raise EvidenceError("equation must be an object")
    expected = {"provenance", "left", "right", "target", "carry_in", "carry_out"}
    if set(payload) != expected:
        raise EvidenceError("equation keys do not match schema")
    provenance = payload["provenance"]
    if not isinstance(provenance, str):
        raise EvidenceError("equation provenance must be a string")
    if _PROVENANCE_RE.fullmatch(provenance) is None:
        raise EvidenceError(f"malformed equation provenance: {provenance}")
    carries = (payload["carry_in"], payload["carry_out"])
    if any(carry is not None and not isinstance(carry, str) for carry in carries):
        raise EvidenceError("equation carries must be strings or null")
    equation = Equation(
        provenance=provenance,
        left=_parse_atom(payload["left"]),
        right=_parse_atom(payload["right"]),
        target=_parse_atom(payload["target"]),
        carry_in=payload["carry_in"],  # type: ignore[arg-type]
        carry_out=payload["carry_out"],  # type: ignore[arg-type]
    )
    for carry in carries:
        if carry is not None and _CARRY_RE.fullmatch(carry) is None:
            raise EvidenceError(f"malformed carry variable: {carry}")
    return equation


def _derive_fragment_lengths(equations: tuple[Equation, ...]) -> tuple[tuple[int, ...], ...]:
    maxima: dict[tuple[int, int], int] = {}
    for equation in equations:
        for atom in (equation.left, equation.right, equation.target):
            if atom.variable is None:
                continue
            match = _DIGIT_RE.fullmatch(atom.variable)
            if match is None:
                raise EvidenceError(f"malformed fixed-digit variable: {atom.variable}")
            key = (int(match["phase"]), int(match["fragment"]))
            maxima[key] = max(maxima.get(key, -1), int(match["offset"]))
    result = []
    for phase in range(6):
        fragments = []
        for fragment in range(3):
            key = (phase, fragment)
            if key not in maxima:
                raise EvidenceError(f"manifest omits phase {phase} fragment {fragment}")
            fragments.append(maxima[key] + 1)
        result.append(tuple(fragments))
    lengths = tuple(result)
    expected = ((26, 25, 31),) + ((29, 23, 31),) * 5
    if lengths != expected:
        raise EvidenceError(f"manifest fragment lengths changed: {lengths}")
    return lengths


def _load_equations(path: Path) -> EquationManifest:
    payload = _load_object(path, "equation manifest")
    content_sha256 = _verify_content_digest(
        payload,
        _EQUATIONS_CONTENT_SHA256,
        "equation manifest",
    )
    if payload.get("schema") != "base19-radial-equations-v1":
        raise EvidenceError("equation manifest schema changed")
    if payload.get("base") != 19 or payload.get("equation_count") != 409:
        raise EvidenceError("equation manifest size or base changed")
    rows = payload.get("equations")
    if not isinstance(rows, list):
        raise EvidenceError("equation manifest rows must be a list")
    equations = tuple(_parse_equation(row) for row in rows)
    provenances = tuple(equation.provenance for equation in equations)
    if len(equations) != 409 or len(set(provenances)) != 409:
        raise EvidenceError("equation provenances must be 409 unique rows")
    topology_sha256 = payload.get("topology_sha256")
    if not isinstance(topology_sha256, str):
        raise EvidenceError("equation manifest topology digest is missing")
    return EquationManifest(
        content_sha256=content_sha256,
        file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        topology_sha256=topology_sha256,
        base=19,
        equations=equations,
        fragment_lengths=_derive_fragment_lengths(equations),
    )


def _parse_state(
    payload: object,
    variables: tuple[str, ...],
    context: str,
) -> tuple[int, ...]:
    if not isinstance(payload, list) or len(payload) != len(variables):
        raise EvidenceError(f"{context} state width is invalid")
    if any(not _is_int(value) for value in payload):
        raise EvidenceError(f"{context} state contains a non-integer")
    values = tuple(payload)
    for variable, value in zip(variables, values, strict=True):
        if variable.startswith("c:"):
            if value not in (0, 1):
                raise EvidenceError(f"{context} carry is outside {{0,1}}")
        elif variable.startswith("digit:"):
            if not 0 <= value < 19:
                raise EvidenceError(f"{context} digit is outside 0..18")
            match = _DIGIT_RE.fullmatch(variable)
            if match is None:
                raise EvidenceError(f"{context} digit name is malformed")
            if match["fragment"] == "0" and match["offset"] == "0" and value == 0:
                raise EvidenceError(f"{context} canonical leading digit is zero")
        else:
            raise EvidenceError(f"{context} variable kind is unknown: {variable}")
    return values


def _parse_layer(payload: object, expected_number: int) -> FrontierLayer:
    if not isinstance(payload, dict):
        raise EvidenceError("frontier layer must be an object")
    if payload.get("layer") != expected_number:
        raise EvidenceError("frontier layer numbering changed")
    input_variables_raw = payload.get("input_variables")
    output_variables_raw = payload.get("output_variables")
    provenances_raw = payload.get("equation_provenances")
    if not all(
        isinstance(value, list)
        for value in (input_variables_raw, output_variables_raw, provenances_raw)
    ):
        raise EvidenceError("frontier layer lists are malformed")
    input_variables = tuple(input_variables_raw)  # type: ignore[arg-type]
    output_variables = tuple(output_variables_raw)  # type: ignore[arg-type]
    provenances = tuple(provenances_raw)  # type: ignore[arg-type]
    all_names = (*input_variables, *output_variables, *provenances)
    if any(not isinstance(item, str) for item in all_names):
        raise EvidenceError("frontier layer names must be strings")
    if (
        len(set(input_variables)) != len(input_variables)
        or len(set(output_variables)) != len(output_variables)
    ):
        raise EvidenceError("frontier variables must be unique")
    equation_count = payload.get("equation_count")
    if not _is_int(equation_count) or equation_count != len(provenances):
        raise EvidenceError("frontier layer equation count is invalid")
    states_raw = payload.get("output_states")
    if not isinstance(states_raw, list):
        raise EvidenceError("frontier output states must be a list")
    states = tuple(
        _parse_state(state, output_variables, f"layer {expected_number} output")
        for state in states_raw
    )
    if states != tuple(sorted(set(states))):
        raise EvidenceError("frontier output states are not sorted and unique")
    state_digest = hashlib.sha256(
        json.dumps(states_raw, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    if payload.get("output_states_sha256") != state_digest:
        raise EvidenceError("frontier output state digest mismatch")
    transitions_raw = payload.get("transitions")
    if not isinstance(transitions_raw, list):
        raise EvidenceError("frontier transitions must be a list")
    transitions = []
    for transition in transitions_raw:
        if not isinstance(transition, dict) or set(transition) != {
            "input_state",
            "output_states",
        }:
            raise EvidenceError("frontier transition shape is invalid")
        local_raw = transition["output_states"]
        if not isinstance(local_raw, list):
            raise EvidenceError("frontier transition outputs must be a list")
        local = tuple(
            _parse_state(state, output_variables, f"layer {expected_number} transition")
            for state in local_raw
        )
        if local != tuple(sorted(set(local))):
            raise EvidenceError("frontier transition outputs are not sorted and unique")
        transitions.append(
            FrontierTransition(
                input_state=_parse_state(
                    transition["input_state"],
                    input_variables,
                    f"layer {expected_number} input",
                ),
                output_states=local,
            )
        )
    counts = {
        "input_state_count": len(transitions),
        "output_state_count": len(states),
        "local_model_count": sum(len(item.output_states) for item in transitions),
    }
    for key, actual in counts.items():
        if payload.get(key) != actual:
            raise EvidenceError(f"frontier {key} is invalid at layer {expected_number}")
    return FrontierLayer(
        number=expected_number,
        equation_provenances=provenances,
        input_variables=input_variables,
        output_variables=output_variables,
        input_state_count=counts["input_state_count"],
        output_state_count=counts["output_state_count"],
        local_model_count=counts["local_model_count"],
        output_states_sha256=state_digest,
        output_states=states,
        transitions=tuple(transitions),
    )


def _provenance_digest(provenances: Iterable[str]) -> str:
    return hashlib.sha256(
        "".join(f"{provenance}\n" for provenance in provenances).encode("utf-8")
    ).hexdigest()


def _load_frontier(path: Path, manifest: EquationManifest) -> FrontierCertificate:
    payload = _load_object(path, "minimal-core frontier")
    content_sha256 = _verify_content_digest(
        payload,
        _FRONTIER_CONTENT_SHA256,
        "minimal-core frontier",
    )
    if payload.get("schema") != "base19-radial-minimal-core-frontier-v1":
        raise EvidenceError("minimal-core frontier schema changed")
    if payload.get("status") != "UNSAT" or payload.get("base") != 19:
        raise EvidenceError("minimal-core frontier status or base changed")
    if payload.get("equation_count") != 408 or payload.get("removed") != _REMOVED:
        raise EvidenceError("minimal-core frontier selection changed")
    if payload.get("equations_sha256") != manifest.file_sha256:
        raise EvidenceError("minimal-core frontier equation-file digest mismatch")
    layers_raw = payload.get("layers")
    if not isinstance(layers_raw, list) or len(layers_raw) != 35:
        raise EvidenceError("minimal-core frontier must contain 35 layers")
    layers = tuple(
        _parse_layer(layer, number)
        for number, layer in zip(range(-1, 34), layers_raw, strict=True)
    )
    expected_inputs: tuple[tuple[int, ...], ...] = ((),)
    expected_variables: tuple[str, ...] = ()
    covered = []
    for layer in layers:
        if layer.input_variables != expected_variables:
            raise EvidenceError("frontier layer variable interfaces are disconnected")
        if layer.input_states != expected_inputs:
            raise EvidenceError("frontier transitions do not match prior states")
        transition_outputs = {
            output
            for transition in layer.transitions
            for output in transition.output_states
        }
        if transition_outputs != set(layer.output_states):
            raise EvidenceError("frontier transitions miss an output state")
        expected_inputs = layer.output_states
        expected_variables = layer.output_variables
        covered.extend(layer.equation_provenances)
    if layers[-1].output_states:
        raise EvidenceError("minimal-core terminal frontier is not empty")
    selected = tuple(
        equation.provenance
        for equation in manifest.equations
        if equation.provenance != _REMOVED
    )
    if len(covered) != 408 or set(covered) != set(selected):
        raise EvidenceError("frontier layers do not cover the selected equations")
    provenances_sha256 = payload.get("provenances_sha256")
    if provenances_sha256 != _PROVENANCES_SHA256:
        raise EvidenceError("frontier frozen provenance digest changed")
    if provenances_sha256 != _provenance_digest(selected):
        raise EvidenceError("frontier provenance digest is inconsistent")
    return FrontierCertificate(
        content_sha256=content_sha256,
        equations_sha256=manifest.file_sha256,
        provenances_sha256=provenances_sha256,
        removed=_REMOVED,
        base=19,
        layers=layers,
    )


def load_promoted_inputs(
    root: Path,
) -> tuple[EquationManifest, FrontierCertificate]:
    """Load and strictly validate the two frozen promoted T27 inputs."""
    artifact = Path(root) / "publication" / "base19-radial"
    manifest = _load_equations(artifact / "instance" / "equations.json")
    frontier = _load_frontier(
        artifact / "certificates" / "minimal-core-frontier.json",
        manifest,
    )
    return manifest, frontier


def _canonical_map(layer: FrontierLayer, side: str) -> dict[str, str]:
    if side == "input":
        variables = layer.input_variables
    elif side == "output":
        variables = layer.output_variables
    else:
        raise ValueError("frontier side must be input or output")
    carries: dict[int, list[tuple[int, str]]] = defaultdict(list)
    digits = []
    for variable in variables:
        carry_match = _CARRY_RE.fullmatch(variable)
        if carry_match is not None:
            carries[int(carry_match["phase"])].append(
                (int(carry_match["column"]), variable)
            )
            continue
        digit_match = _DIGIT_RE.fullmatch(variable)
        if digit_match is None:
            raise EvidenceError(f"cannot canonicalize frontier variable: {variable}")
        digits.append(
            (
                int(digit_match["phase"]),
                int(digit_match["fragment"]),
                int(digit_match["offset"]),
                variable,
            )
        )
    mapping: dict[str, str] = {}
    for phase in sorted(carries):
        phase_carries = sorted(carries[phase])
        if len(phase_carries) > 2:
            raise EvidenceError(f"phase {phase} has more than two frontier carries")
        labels = (f"L{phase}", f"R{phase}")
        for label, (_, variable) in zip(labels, phase_carries, strict=False):
            mapping[variable] = label
    for index, (*_, variable) in enumerate(sorted(digits)):
        if index >= 2:
            raise EvidenceError("frontier has more than two live digits")
        mapping[variable] = f"D{index}"
    ordered = {variable: mapping[variable] for variable in variables}
    if len(set(ordered.values())) != len(ordered):
        raise EvidenceError("canonical frontier names are not unique")
    return ordered


def canonical_variable(name: str, layer: FrontierLayer, side: str) -> str:
    try:
        return _canonical_map(layer, side)[name]
    except KeyError as error:
        raise EvidenceError(f"variable is not on the {side} frontier: {name}") from error


def canonicalize_state(
    layer: FrontierLayer,
    side: str,
    state: tuple[int, ...],
) -> dict[str, int]:
    variables = layer.input_variables if side == "input" else layer.output_variables
    if side not in {"input", "output"}:
        raise ValueError("frontier side must be input or output")
    if len(state) != len(variables):
        raise EvidenceError("cannot canonicalize a state with the wrong width")
    mapping = _canonical_map(layer, side)
    return {
        mapping[variable]: value
        for variable, value in zip(variables, state, strict=True)
    }


def state_table_payload(layers: tuple[FrontierLayer, ...]) -> dict[str, object]:
    """Return only canonical mathematical state-table content."""
    return {
        "layers": [
            {
                "layer": layer.number,
                "variables": list(_canonical_map(layer, "output").values()),
                "states": [
                    list(canonicalize_state(layer, "output", state).values())
                    for state in layer.output_states
                ],
            }
            for layer in layers
        ]
    }


def _predicate_mapping(
    layer: FrontierLayer,
    side: str,
    predicate: LayerPredicate,
) -> dict[str, str]:
    original_to_canonical = _canonical_map(layer, side)
    canonical_variables = tuple(original_to_canonical.values())
    if predicate.variables != canonical_variables:
        raise EvidenceError(
            f"predicate scope differs from layer {layer.number} {side} frontier: "
            f"expected={canonical_variables}, actual={predicate.variables}"
        )
    return {
        canonical: original
        for original, canonical in original_to_canonical.items()
    }


def check_initiation(
    layer: FrontierLayer,
    predicate: LayerPredicate,
) -> ObligationResult:
    """Check that every reachable state at the first cut satisfies a predicate."""
    _predicate_mapping(layer, "output", predicate)
    for state in layer.output_states:
        assignment = canonicalize_state(layer, "output", state)
        if not evaluate_predicate(predicate, assignment):
            return ObligationResult(
                kind="initiation",
                layer=layer.number,
                status="FAIL",
                checked_count=layer.output_state_count,
                counterexample={"output": assignment},
            )
    return ObligationResult(
        kind="initiation",
        layer=layer.number,
        status="PASS",
        checked_count=layer.output_state_count,
    )


def _local_z3_problem(
    manifest: EquationManifest,
    layer: FrontierLayer,
) -> tuple[object, object, dict[str, object]]:
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("certificate obligations require z3-solver") from error
    try:
        equations = tuple(
            manifest.by_provenance[provenance]
            for provenance in layer.equation_provenances
        )
    except KeyError as error:
        raise EvidenceError(f"layer references an unknown equation: {error.args[0]}") from error
    names = sorted(
        set(layer.input_variables)
        | set(layer.output_variables)
        | {variable for equation in equations for variable in equation.variables}
    )
    variables = {
        name: z3.Int(
            "t27_obligation_"
            + str(layer.number).replace("-", "neg")
            + "_"
            + re.sub(r"[^A-Za-z0-9_]", "_", name)
        )
        for name in names
    }
    solver = z3.Solver()
    for name, variable in variables.items():
        if name.startswith("c:"):
            solver.add(variable >= 0, variable <= 1)
        else:
            lower = 1 if re.fullmatch(r"digit:p\d+:f0:d0", name) else 0
            solver.add(variable >= lower, variable < manifest.base)
    for equation in equations:
        solver.add(_z3_residual(z3, equation, variables, manifest.base) == 0)
    return z3, solver, variables


def _z3_atom(
    z3: object,
    atom: LinearAtom,
    canonical_to_original: dict[str, str],
    variables: dict[str, object],
) -> object:
    try:
        total = sum(
            coefficient * variables[canonical_to_original[name]]
            for name, coefficient in atom.terms
        )
    except KeyError as error:
        raise EvidenceError(
            f"predicate atom references unknown variable: {error.args[0]}"
        ) from error
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    if atom.relation == "congruent":
        assert atom.modulus is not None
        return (total - atom.constant) % atom.modulus == 0
    raise EvidenceError(f"unsupported predicate relation: {atom.relation}")


def _z3_predicate(
    z3: object,
    predicate: LayerPredicate,
    canonical_to_original: dict[str, str],
    variables: dict[str, object],
) -> object:
    return z3.Or(
        *(
            z3.And(
                *(
                    _z3_atom(z3, atom, canonical_to_original, variables)
                    for atom in clause.atoms
                )
            )
            for clause in predicate.clauses
        )
    )


def _domain_size(names: Iterable[str], base: int) -> int:
    result = 1
    for name in names:
        result *= 2 if name.startswith("c:") else base
    return result


def _lexicographic_model(
    z3: object,
    solver: object,
    variables: dict[str, object],
    ordered_names: tuple[str, ...],
    base: int,
) -> object:
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(f"obligation solver returned UNKNOWN: {solver.reason_unknown()}")
    if status == z3.unsat:
        raise EvidenceError("cannot canonicalize an UNSAT obligation")
    for name in ordered_names:
        domain = range(2) if name.startswith("c:") else range(base)
        for value in domain:
            solver.push()
            solver.add(variables[name] == value)
            trial = solver.check()
            solver.pop()
            if trial == z3.unknown:
                raise EvidenceError(
                    f"obligation minimization returned UNKNOWN: {solver.reason_unknown()}"
                )
            if trial == z3.sat:
                solver.add(variables[name] == value)
                break
        else:
            raise EvidenceError(f"obligation model has no value for {name}")
    final = solver.check()
    if final != z3.sat:
        raise EvidenceError("canonical obligation assignments became inconsistent")
    return solver.model()


def _model_assignment(
    model: object,
    variables: dict[str, object],
    canonical_to_original: dict[str, str],
) -> dict[str, int]:
    return {
        canonical: model.eval(variables[original], model_completion=True).as_long()
        for canonical, original in canonical_to_original.items()
    }


def check_consecution(
    manifest: EquationManifest,
    frontier: FrontierCertificate,
    current: LayerPredicate,
    following: LayerPredicate,
) -> ObligationResult:
    """Check every bounded local transfer, not only the reachable-state table."""
    if following.layer != current.layer + 1:
        raise EvidenceError("consecution predicates must name consecutive layers")
    try:
        transfer = frontier.layers_by_number[following.layer]
    except KeyError as error:
        raise EvidenceError(f"frontier omits transfer layer {following.layer}") from error
    input_mapping = _predicate_mapping(transfer, "input", current)
    output_mapping = _predicate_mapping(transfer, "output", following)
    z3, solver, variables = _local_z3_problem(manifest, transfer)
    solver.add(_z3_predicate(z3, current, input_mapping, variables))
    solver.add(z3.Not(_z3_predicate(z3, following, output_mapping, variables)))
    status = solver.check()
    checked_count = _domain_size(transfer.input_variables, manifest.base)
    if status == z3.unknown:
        raise EvidenceError(f"consecution returned UNKNOWN: {solver.reason_unknown()}")
    if status == z3.unsat:
        return ObligationResult(
            kind="consecution",
            layer=following.layer,
            status="PASS",
            checked_count=checked_count,
        )
    ordered = tuple(dict.fromkeys((*transfer.input_variables, *transfer.output_variables)))
    model = _lexicographic_model(z3, solver, variables, ordered, manifest.base)
    return ObligationResult(
        kind="consecution",
        layer=following.layer,
        status="FAIL",
        checked_count=checked_count,
        counterexample={
            "input": _model_assignment(model, variables, input_mapping),
            "output": _model_assignment(model, variables, output_mapping),
        },
    )


def check_exclusion(
    manifest: EquationManifest,
    frontier: FrontierCertificate,
    predicate: LayerPredicate,
) -> ObligationResult:
    """Check that the final predicate has no exact terminal local model."""
    terminal_number = predicate.layer + 1
    try:
        terminal = frontier.layers_by_number[terminal_number]
    except KeyError as error:
        raise EvidenceError(f"frontier omits terminal layer {terminal_number}") from error
    if terminal.output_variables:
        raise EvidenceError("exclusion layer must have an empty output frontier")
    input_mapping = _predicate_mapping(terminal, "input", predicate)
    z3, solver, variables = _local_z3_problem(manifest, terminal)
    solver.add(_z3_predicate(z3, predicate, input_mapping, variables))
    status = solver.check()
    checked_count = _domain_size(terminal.input_variables, manifest.base)
    if status == z3.unknown:
        raise EvidenceError(f"exclusion returned UNKNOWN: {solver.reason_unknown()}")
    if status == z3.unsat:
        return ObligationResult(
            kind="exclusion",
            layer=terminal.number,
            status="PASS",
            checked_count=checked_count,
        )
    model = _lexicographic_model(
        z3,
        solver,
        variables,
        terminal.input_variables,
        manifest.base,
    )
    return ObligationResult(
        kind="exclusion",
        layer=terminal.number,
        status="FAIL",
        checked_count=checked_count,
        counterexample={
            "input": _model_assignment(model, variables, input_mapping),
        },
    )


def check_certificate(
    inputs: tuple[EquationManifest, FrontierCertificate],
    certificate: InvariantCertificate,
) -> CertificateCheckResult:
    """Check initiation, universal local consecution, and terminal exclusion."""
    manifest, frontier = inputs
    if certificate.base != manifest.base or certificate.base != frontier.base:
        raise EvidenceError("certificate base differs from frozen inputs")
    if certificate.removed != frontier.removed:
        raise EvidenceError("certificate removed coordinate differs from frozen input")
    source_digests = dict(certificate.source_digests)
    if source_digests != {
        "equations": manifest.content_sha256,
        "frontier": frontier.content_sha256,
    }:
        raise EvidenceError("certificate source digests differ from frozen inputs")
    if not certificate.predicates:
        raise EvidenceError("certificate contains no layer predicates")
    obligations = []
    first = certificate.predicates[0]
    try:
        first_layer = frontier.layers_by_number[first.layer]
    except KeyError as error:
        raise EvidenceError(f"frontier omits initiation layer {first.layer}") from error
    initiation = check_initiation(first_layer, first)
    obligations.append(initiation)
    if initiation.status != "PASS":
        return CertificateCheckResult("FAIL", tuple(obligations))
    for current, following in zip(
        certificate.predicates,
        certificate.predicates[1:],
        strict=False,
    ):
        consecution = check_consecution(manifest, frontier, current, following)
        obligations.append(consecution)
        if consecution.status != "PASS":
            return CertificateCheckResult("FAIL", tuple(obligations))
    exclusion = check_exclusion(manifest, frontier, certificate.predicates[-1])
    obligations.append(exclusion)
    return CertificateCheckResult(
        "PASS" if exclusion.status == "PASS" else "FAIL",
        tuple(obligations),
    )


def _same_addend_key(equation: Equation) -> tuple[tuple[str, str | int], ...]:
    return tuple(sorted((equation.left.grouping_key(), equation.right.grouping_key())))


def _z3_value(z3: object, atom: Atom, variables: dict[str, object], base: int) -> object:
    if atom.variable is not None:
        return variables[f"digit:{atom.variable}"]
    assert atom.literal is not None
    return base - 1 if atom.literal == 18 else atom.literal


def _z3_residual(
    z3: object,
    equation: Equation,
    variables: dict[str, object],
    base: int,
) -> object:
    carry_in = 0 if equation.carry_in is None else variables[equation.carry_in]
    carry_out = 0 if equation.carry_out is None else variables[equation.carry_out]
    return (
        _z3_value(z3, equation.left, variables, base)
        + _z3_value(z3, equation.right, variables, base)
        + carry_in
        - _z3_value(z3, equation.target, variables, base)
        - base * carry_out
    )


def _solve_difference_relaxation(
    pairs: tuple[tuple[Equation, Equation], ...],
    boundaries: tuple[Equation, ...],
    base: int,
) -> dict[str, object]:
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("difference relaxation requires z3-solver") from error
    names = sorted(
        {
            variable
            for equation in (*boundaries, *(item for pair in pairs for item in pair))
            for variable in equation.variables
        }
    )
    variables = {
        name: z3.Int("t27_" + re.sub(r"[^A-Za-z0-9_]", "_", name))
        for name in names
    }
    solver = z3.Solver()
    for name, variable in variables.items():
        if name.startswith("c:"):
            solver.add(variable >= 0, variable <= 1)
        else:
            lower = 1 if re.fullmatch(r"digit:p\d+:f0:d0", name) else 0
            solver.add(variable >= lower, variable < base)
    for left, right in pairs:
        solver.add(
            _z3_residual(z3, left, variables, base)
            - _z3_residual(z3, right, variables, base)
            == 0
        )
    for equation in boundaries:
        solver.add(_z3_residual(z3, equation, variables, base) == 0)
    status = solver.check()
    if status == z3.unknown:
        raise EvidenceError(f"difference relaxation returned UNKNOWN: {solver.reason_unknown()}")
    if status == z3.unsat:
        return {"base": base, "status": "UNSAT"}
    model = solver.model()
    assignment = {
        name: model.eval(variable, model_completion=True).as_long()
        for name, variable in variables.items()
    }
    replayed = all(
        left.residual(assignment, base) - right.residual(assignment, base) == 0
        for left, right in pairs
    ) and all(equation.residual(assignment, base) == 0 for equation in boundaries)
    if not replayed:
        raise EvidenceError("difference-relaxation model failed integer replay")
    return {
        "base": base,
        "status": "SAT",
        "assignment": {
            "carries": {
                name: value for name, value in assignment.items() if name.startswith("c:")
            },
            "digits": {
                name.removeprefix("digit:"): value
                for name, value in assignment.items()
                if name.startswith("digit:")
            },
        },
        "replay_status": "valid",
    }


def _terminal_deletion_records(
    manifest: EquationManifest,
    frontier: FrontierCertificate,
) -> list[dict[str, object]]:
    try:
        import z3  # type: ignore[import-not-found]
    except ImportError as error:
        raise EvidenceError("terminal deletion audit requires z3-solver") from error
    terminal = frontier.layers_by_number[33]
    equations = tuple(
        manifest.by_provenance[provenance]
        for provenance in terminal.equation_provenances
    )
    variable_names = sorted(
        {variable for equation in equations for variable in equation.variables}
    )
    records = []
    for removed in equations:
        survivors = []
        retained = tuple(equation for equation in equations if equation != removed)
        for state in terminal.input_states:
            variables = {
                name: z3.Int("t27_terminal_" + re.sub(r"[^A-Za-z0-9_]", "_", name))
                for name in variable_names
            }
            solver = z3.Solver()
            for name, variable in variables.items():
                if name.startswith("c:"):
                    solver.add(variable >= 0, variable <= 1)
                else:
                    lower = 1 if re.fullmatch(r"digit:p\d+:f0:d0", name) else 0
                    solver.add(variable >= lower, variable < 19)
            for name, value in zip(terminal.input_variables, state, strict=True):
                solver.add(variables[name] == value)
            for equation in retained:
                solver.add(_z3_residual(z3, equation, variables, 19) == 0)
            status = solver.check()
            if status == z3.unknown:
                raise EvidenceError(
                    f"terminal deletion returned UNKNOWN: {solver.reason_unknown()}"
                )
            if status == z3.sat:
                survivors.append(list(state))
        records.append(
            {
                "removed": removed.provenance,
                "surviving_state_count": len(survivors),
                "surviving_states": survivors,
            }
        )
    return records


def reproduce_structural_baseline(
    inputs: tuple[EquationManifest, FrontierCertificate],
) -> dict[str, object]:
    """Reproduce the pair, relaxation, and terminal-essentiality facts."""
    manifest, frontier = inputs
    selected = tuple(
        equation for equation in manifest.equations if equation.provenance != frontier.removed
    )
    grouped: dict[
        tuple[tuple[str, str | int], ...],
        list[Equation],
    ] = defaultdict(list)
    for equation in selected:
        grouped[_same_addend_key(equation)].append(equation)
    pairs = []
    boundaries = []
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda equation: equation.provenance)
        if len(group) == 1:
            boundaries.extend(group)
        elif len(group) == 2:
            left, right = group
            if (
                left.provenance == right.provenance
                or (left.target, left.carry_in, left.carry_out)
                == (right.target, right.carry_in, right.carry_out)
            ):
                raise EvidenceError("same-addend pair does not have two distinct rows")
            pairs.append((left, right))
        else:
            raise EvidenceError("same-addend group is not a pair or boundary")
    boundary_provenances = sorted(equation.provenance for equation in boundaries)
    expected_boundaries = [
        "phase=5,n=0,column=0",
        "phase=5,n=0,column=83",
    ]
    if len(pairs) != 203 or boundary_provenances != expected_boundaries:
        raise EvidenceError("408-equation pair decomposition changed")
    pair_tuple = tuple(pairs)
    boundary_tuple = tuple(sorted(boundaries, key=lambda equation: equation.provenance))
    difference_relaxation = [
        _solve_difference_relaxation(pair_tuple, boundary_tuple, base)
        for base in range(17, 41)
    ]
    if any(item["status"] != "SAT" for item in difference_relaxation):
        raise EvidenceError("difference-only relaxation is not SAT throughout 17..40")
    terminal_deletions = _terminal_deletion_records(manifest, frontier)
    if len(terminal_deletions) != 12 or any(
        item["surviving_state_count"] < 2 for item in terminal_deletions
    ):
        raise EvidenceError("terminal 12-equation essentiality changed")
    return {
        "pair_count": len(pairs),
        "pairs": [
            [left.provenance, right.provenance]
            for left, right in pair_tuple
        ],
        "boundary_provenances": boundary_provenances,
        "difference_relaxation": difference_relaxation,
        "terminal_deletions": terminal_deletions,
    }
