from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_invariant_certificate import LinearAtom, canonical_bytes  # noqa: E402
from lychrel_quotient_automaton import (  # noqa: E402
    ClassSpec,
    DecisionNode,
    EdgeWitness,
    LayerQuotient,
    QuotientCertificate,
    certificate_core_payload,
    classify_state,
    layer_path_depth,
    parse_quotient_certificate,
)


def test_decision_dag_classifies_two_classes_and_outside() -> None:
    """A wrong branch target must change an observable class result."""
    layer = LayerQuotient(
        layer=31,
        variables=("x",),
        root="node:0",
        classes=(
            ClassSpec("DEAD", "dead", ()),
            ClassSpec("P0", "live", ("T0",)),
        ),
        nodes=(
            DecisionNode(
                0,
                LinearAtom("le", (("x", 1),), 0),
                "class:DEAD",
                "node:1",
            ),
            DecisionNode(
                1,
                LinearAtom("le", (("x", 1),), 1),
                "class:P0",
                "outside",
            ),
        ),
    )

    assert classify_state(layer, {"x": 0}) == "DEAD"
    assert classify_state(layer, {"x": 1}) == "P0"
    assert classify_state(layer, {"x": 2}) == "outside"
    assert layer_path_depth(layer) == 2


def _unit_atom(variable: str = "x") -> LinearAtom:
    return LinearAtom("eq", ((variable, 1),), 0)


@pytest.mark.parametrize(
    "class_spec",
    (
        ClassSpec("lowercase", "dead", ()),
        ClassSpec("LIVE", "unknown", ("T0",)),
        ClassSpec("LIVE", "live", ()),
        ClassSpec("DEAD", "dead", ("T0",)),
        ClassSpec("TERMINAL", "terminal", ("T0",)),
    ),
)
def test_class_specs_reject_invalid_semantics(class_spec: ClassSpec) -> None:
    """Removing class validation must admit a malformed semantic claim."""
    with pytest.raises(ValueError):
        LayerQuotient(
            31,
            ("x",),
            "node:0",
            (class_spec,),
            (DecisionNode(0, _unit_atom(), "class:" + class_spec.label, "outside"),),
        )


@pytest.mark.parametrize(
    "nodes",
    (
        (DecisionNode(0, _unit_atom(), "node:0", "outside"),),
        (DecisionNode(0, _unit_atom(), "node:1", "outside"),),
        (DecisionNode(0, _unit_atom(), "class:MISSING", "outside"),),
        (DecisionNode(0, _unit_atom(), "class:DEAD", "class:DEAD"),),
        (
            DecisionNode(0, _unit_atom("x"), "class:DEAD", "outside"),
            DecisionNode(1, _unit_atom("y"), "class:DEAD", "outside"),
        ),
    ),
)
def test_layer_rejects_invalid_or_unreachable_decision_nodes(
    nodes: tuple[DecisionNode, ...],
) -> None:
    """Dropping graph checks must admit a cycle, dangling edge, or dead node."""
    with pytest.raises(ValueError):
        LayerQuotient(31, ("x", "y"), "node:0", (ClassSpec("DEAD", "dead", ()),), nodes)


def test_layer_rejects_an_unreduced_duplicate_subtree() -> None:
    """Dropping hash-cons validation must permit two identical subtrees."""
    nodes = (
        DecisionNode(0, _unit_atom("x"), "node:1", "node:2"),
        DecisionNode(1, _unit_atom("y"), "class:DEAD", "outside"),
        DecisionNode(2, _unit_atom("y"), "class:DEAD", "outside"),
    )
    with pytest.raises(ValueError, match="unreduced"):
        LayerQuotient(31, ("x", "y"), "node:0", (ClassSpec("DEAD", "dead", ()),), nodes)


def test_synthesized_layer_rejects_depth_above_ten() -> None:
    """Removing the path cap must admit an unreadable synthesized guard."""
    nodes = tuple(
        DecisionNode(
            index,
            _unit_atom(),
            f"node:{index + 1}" if index < 10 else "class:DEAD",
            "outside",
        )
        for index in range(11)
    )
    with pytest.raises(ValueError, match="depth"):
        LayerQuotient(31, ("x",), "node:0", (ClassSpec("DEAD", "dead", ()),), nodes)

    terminal_seed = LayerQuotient(
        32,
        ("x",),
        "node:0",
        (ClassSpec("TERMINAL", "terminal", ()),),
        (*nodes[:-1], DecisionNode(10, _unit_atom(), "class:TERMINAL", "outside")),
    )
    assert layer_path_depth(terminal_seed) == 11


def test_layer_rejects_class_and_node_count_overflows() -> None:
    """Removing either readability count must admit an oversized certificate."""
    classes = tuple(ClassSpec(f"Q{index}", "dead", ()) for index in range(9))
    with pytest.raises(ValueError, match="eight"):
        LayerQuotient(
            31,
            ("x",),
            "node:0",
            classes,
            (DecisionNode(0, _unit_atom(), "class:Q0", "outside"),),
        )

    nodes = tuple(
        DecisionNode(
            index,
            _unit_atom(),
            f"node:{index + 1}" if index < 64 else "class:DEAD",
            "outside",
        )
        for index in range(65)
    )
    with pytest.raises(ValueError, match="64"):
        LayerQuotient(32, ("x",), "node:0", (ClassSpec("DEAD", "dead", ()),), nodes)


@pytest.mark.parametrize("assignment", ({}, {"x": True}, {"x": 0, "extra": 1}))
def test_classifier_rejects_assignments_that_do_not_match_scope(
    assignment: dict[str, int],
) -> None:
    """Removing scope checks must allow missing, Boolean, or extra values."""
    layer = LayerQuotient(
        31,
        ("x",),
        "node:0",
        (ClassSpec("DEAD", "dead", ()),),
        (DecisionNode(0, _unit_atom(), "class:DEAD", "outside"),),
    )
    with pytest.raises(ValueError, match="assignment"):
        classify_state(layer, assignment)


def quotient_fixture_certificate() -> QuotientCertificate:
    source = LayerQuotient(
        31,
        ("x",),
        "node:0",
        (ClassSpec("DEAD", "dead", ()), ClassSpec("P0", "live", ("T0",))),
        (DecisionNode(0, _unit_atom(), "class:DEAD", "class:P0"),),
    )
    terminal = LayerQuotient(
        32,
        ("y",),
        "node:0",
        (ClassSpec("T0", "terminal", ()),),
        (DecisionNode(0, LinearAtom("le", (("y", 1),), 1), "class:T0", "outside"),),
    )
    return QuotientCertificate(
        schema="t28-tail-quotient-certificate-v1",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=(
            ("equations", "a" * 64),
            ("frontier", "b" * 64),
            ("provenances", "c" * 64),
            ("t27_evidence", "d" * 64),
        ),
        start_layer=31,
        layers=(source, terminal),
        witnesses=(
            EdgeWitness(
                source_layer=31,
                source_class="P0",
                target_class="T0",
                input_state=(("x", 1),),
                output_state=(("y", 1),),
                local_state=(),
            ),
        ),
    )


def test_certificate_round_trip_preserves_canonical_core() -> None:
    """A parser or serializer mutation must change the exported certificate."""
    certificate = quotient_fixture_certificate()

    parsed = parse_quotient_certificate(certificate.to_payload())

    assert canonical_bytes(parsed) == canonical_bytes(certificate)
    assert certificate_core_payload(parsed) == certificate_core_payload(certificate)
    assert set(certificate_core_payload(parsed)) == {"start_layer", "layers"}


def test_certificate_rejects_missing_or_spurious_edge_witnesses() -> None:
    """Dropping witness-edge binding must admit an unsupported quotient edge."""
    certificate = quotient_fixture_certificate()
    with pytest.raises(ValueError, match="witness"):
        replace(certificate, witnesses=())
    with pytest.raises(ValueError, match="witness"):
        replace(
            certificate,
            witnesses=(replace(certificate.witnesses[0], source_class="DEAD"),),
        )


@pytest.mark.parametrize(
    "witness",
    (
        EdgeWitness(31, "P0", "T0", (), (("y", 1),), ()),
        EdgeWitness(31, "P0", "T0", (("x", 1),), (), ()),
        EdgeWitness(31, "P0", "T0", (("x", 1),), (("y", 1),), (("x", 0),)),
    ),
)
def test_certificate_rejects_malformed_witness_assignments(
    witness: EdgeWitness,
) -> None:
    """Dropping witness scope checks must admit incomplete or overlapping data."""
    certificate = quotient_fixture_certificate()
    with pytest.raises(ValueError, match="witness"):
        replace(certificate, witnesses=(witness,))


def test_certificate_parser_rejects_extra_keys_and_bad_digests() -> None:
    """Dropping strict parsing must let altered evidence enter a certificate."""
    payload = quotient_fixture_certificate().to_payload()
    payload["extra"] = "not allowed"
    with pytest.raises(ValueError, match="keys"):
        parse_quotient_certificate(payload)

    payload = quotient_fixture_certificate().to_payload()
    payload["source_digests"]["equations"] = "not-a-digest"
    with pytest.raises(ValueError, match="digest"):
        parse_quotient_certificate(payload)
