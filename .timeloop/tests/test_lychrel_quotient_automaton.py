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
from t27_base19_invariant_lift import EvidenceError, canonicalize_state  # noqa: E402
from t28_base19_tail_quotient import (  # noqa: E402
    ExplicitTransfer,
    build_terminal_seed,
    check_explicit_layer,
    check_layer_semantics,
    check_quotient_certificate,
    check_reachable_coverage,
    check_terminal_classes,
    discover_reachable_quotient,
    explicit_relation_payload,
    load_t28_inputs,
)

EQUATIONS_CONTENT_SHA256 = "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"
FRONTIER_CONTENT_SHA256 = "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"
PROVENANCES_SHA256 = "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"
T27_EVIDENCE_SHA256 = "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686"


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


def test_t28_inputs_bind_the_frozen_t27_tail() -> None:
    """Changing any frozen input must prevent a T28 research claim."""
    inputs = load_t28_inputs(ROOT)

    assert inputs.manifest.content_sha256 == EQUATIONS_CONTENT_SHA256
    assert inputs.frontier.content_sha256 == FRONTIER_CONTENT_SHA256
    assert inputs.frontier.provenances_sha256 == PROVENANCES_SHA256
    assert inputs.t27_evidence_sha256 == T27_EVIDENCE_SHA256


def test_terminal_seed_classifies_all_promoted_states_into_three_families() -> None:
    """Dropping a terminal branch must route a promoted state outside."""
    inputs = load_t28_inputs(ROOT)
    seed = build_terminal_seed(inputs)
    layer32 = inputs.frontier.layers_by_number[32]
    labels = [
        classify_state(seed, canonicalize_state(layer32, "output", state))
        for state in layer32.output_states
    ]

    assert seed.layer == 32
    assert {item.label for item in seed.classes} == {
        "T_HIGH_DIGIT",
        "T_PHASE_ZERO",
        "T_RESIDUE",
    }
    assert sorted(labels.count(label) for label in set(labels)) == [6, 8, 8]
    assert "outside" not in labels


def test_t28_inputs_reject_a_changed_t27_evidence_file(tmp_path: Path) -> None:
    """Removing the raw evidence hash check must admit altered T27 evidence."""
    original = ROOT / ".timeloop" / "runs" / "t27_base19_invariant_lift.json"
    changed = tmp_path / "changed-t27.json"
    changed.write_bytes(original.read_bytes() + b"\n")

    with pytest.raises(EvidenceError, match="T27 evidence digest"):
        load_t28_inputs(ROOT, t27_evidence_path=changed)


def test_reachable_successor_quotient_reproduces_candidate_counts() -> None:
    """Changing signature grouping must alter the hand-checked class counts."""
    partitions = discover_reachable_quotient(load_t28_inputs(ROOT), 25, 32)

    assert [
        (
            partition.layer,
            sum(len(item.members) for item in partition.classes),
            len(partition.classes),
        )
        for partition in partitions
    ] == [
        (25, 20, 5),
        (26, 12, 5),
        (27, 12, 7),
        (28, 17, 7),
        (29, 16, 6),
        (30, 18, 5),
        (31, 18, 4),
        (32, 22, 3),
    ]
    layer31 = next(partition for partition in partitions if partition.layer == 31)
    assert sorted(len(item.members) for item in layer31.classes) == [1, 2, 3, 12]
    assert sum(not item.allowed_next for item in layer31.classes) == 1
    assert all(
        len(item.allowed_next) == 1 for item in layer31.classes if item.allowed_next
    )


def test_explicit_relation_payload_contains_only_canonical_mathematics() -> None:
    """Adding metadata must inflate the comparison denominator illegitimately."""
    payload = explicit_relation_payload(load_t28_inputs(ROOT), 31, 32)

    assert set(payload) == {"layers"}
    assert [item["layer"] for item in payload["layers"]] == [31, 32]
    assert all(
        set(item) == {"layer", "variables", "next_variables", "states", "edges"}
        for item in payload["layers"]
    )
    assert all(
        set(edge) == {"input", "output"}
        for item in payload["layers"]
        for edge in item["edges"]
    )


def explicit_transfer_fixture() -> ExplicitTransfer:
    return ExplicitTransfer(
        source_layer=31,
        input_variables=("x",),
        output_variables=("y",),
        source_domain=((0,), (1,), (2,)),
        transitions=(
            ((0,), ()),
            ((1,), ((0,),)),
            ((2,), ((1,),)),
        ),
    )


def _edge_witness(source: int = 1, target: int = 0) -> EdgeWitness:
    return EdgeWitness(
        source_layer=31,
        source_class="LIVE",
        target_class="T0",
        input_state=(("x", source),),
        output_state=(("y", target),),
        local_state=(),
    )


def test_semantics_rejects_a_live_state_without_successor() -> None:
    """Removing live existence must accept a vacuous universal edge check."""
    check = check_explicit_layer(
        transfer=explicit_transfer_fixture(),
        source_labels={(0,): "LIVE", (1,): "LIVE", (2,): "outside"},
        target_labels={(0,): "T0", (1,): "T1"},
        classes=(ClassSpec("LIVE", "live", ("T0",)),),
        witnesses=(_edge_witness(),),
    )

    assert check.status == "FAIL"
    assert check.obligations[-1].kind == "live_has_successor"
    assert check.obligations[-1].counterexample == {"input": {"x": 0}}


def test_semantics_rejects_a_dead_state_with_a_successor() -> None:
    """Removing dead exclusion must accept a falsely dead class."""
    check = check_explicit_layer(
        transfer=explicit_transfer_fixture(),
        source_labels={(0,): "outside", (1,): "DEAD", (2,): "outside"},
        target_labels={(0,): "T0", (1,): "T1"},
        classes=(ClassSpec("DEAD", "dead", ()),),
        witnesses=(),
    )

    assert check.status == "FAIL"
    assert check.obligations[-1].kind == "dead_has_no_successor"
    assert check.obligations[-1].counterexample == {
        "input": {"x": 1},
        "output": {"y": 0},
    }


def test_semantics_rejects_a_forbidden_successor() -> None:
    """Removing target classification must accept an edge to the wrong family."""
    check = check_explicit_layer(
        transfer=explicit_transfer_fixture(),
        source_labels={(0,): "outside", (1,): "outside", (2,): "LIVE"},
        target_labels={(0,): "T0", (1,): "T1"},
        classes=(ClassSpec("LIVE", "live", ("T0",)),),
        witnesses=(_edge_witness(source=2, target=1),),
    )

    assert check.status == "FAIL"
    assert check.obligations[-1].kind == "forbidden_successor"
    assert check.obligations[-1].counterexample == {
        "input": {"x": 2},
        "output": {"y": 1},
    }


def test_semantics_rejects_a_missing_or_false_edge_witness() -> None:
    """Removing witness replay must report an edge that has no shown model."""
    arguments = {
        "transfer": explicit_transfer_fixture(),
        "source_labels": {(0,): "outside", (1,): "LIVE", (2,): "outside"},
        "target_labels": {(0,): "T0", (1,): "T1"},
        "classes": (ClassSpec("LIVE", "live", ("T0",)),),
    }
    missing = check_explicit_layer(**arguments, witnesses=())
    false = check_explicit_layer(**arguments, witnesses=(_edge_witness(target=1),))

    assert missing.status == "FAIL"
    assert missing.obligations[-1].kind == "edge_has_witness"
    assert false.status == "FAIL"
    assert false.obligations[-1].kind == "edge_has_witness"


def test_semantics_accepts_an_exact_dead_and_live_partition() -> None:
    """Changing any branch in the fixture must break the exact PASS result."""
    check = check_explicit_layer(
        transfer=explicit_transfer_fixture(),
        source_labels={(0,): "DEAD", (1,): "LIVE", (2,): "outside"},
        target_labels={(0,): "T0", (1,): "T1"},
        classes=(
            ClassSpec("DEAD", "dead", ()),
            ClassSpec("LIVE", "live", ("T0",)),
        ),
        witnesses=(_edge_witness(),),
    )

    assert check.status == "PASS"
    assert [item.kind for item in check.obligations] == [
        "dead_has_no_successor",
        "live_has_successor",
        "forbidden_successor",
        "edge_has_witness",
    ]
    assert all(item.status == "PASS" for item in check.obligations)


def test_exact_terminal_checker_excludes_each_effective_family() -> None:
    """Dropping one terminal equation must make at least one family satisfiable."""
    inputs = load_t28_inputs(ROOT)
    seed = build_terminal_seed(inputs)

    coverage = check_reachable_coverage(inputs, seed)
    exclusion = check_terminal_classes(inputs, seed)

    assert coverage.status == "PASS"
    assert coverage.obligations[0].checked_count == 22
    assert exclusion.status == "PASS"
    assert [item.class_label for item in exclusion.obligations] == [
        "T_HIGH_DIGIT",
        "T_PHASE_ZERO",
        "T_RESIDUE",
    ]
    assert all(item.kind == "terminal_exclusion" for item in exclusion.obligations)
    assert all(item.checked_count == 1_478_656 for item in exclusion.obligations)


def test_exact_layer_checker_rejects_a_false_all_dead_guard() -> None:
    """Ignoring local models must let a false dead classification pass."""
    inputs = load_t28_inputs(ROOT)
    partition = next(
        item for item in discover_reachable_quotient(inputs, 31, 32) if item.layer == 31
    )
    all_dead = LayerQuotient(
        layer=31,
        variables=partition.variables,
        root="node:0",
        classes=(ClassSpec("DEAD", "dead", ()),),
        nodes=(
            DecisionNode(
                0,
                LinearAtom("le", (("L0", 1),), 1),
                "class:DEAD",
                "outside",
            ),
        ),
    )

    check = check_layer_semantics(
        inputs,
        all_dead,
        build_terminal_seed(inputs),
        witnesses=(),
    )

    assert check.status == "FAIL"
    assert check.obligations[-1].kind == "dead_has_no_successor"
    assert check.obligations[-1].class_label == "DEAD"
    assert check.obligations[-1].counterexample is not None
    assert set(check.obligations[-1].counterexample) == {"input", "output"}


def test_certificate_checker_stops_at_a_false_layer_semantics() -> None:
    """Skipping a failed layer must let an invalid tail reach terminal PASS."""
    inputs = load_t28_inputs(ROOT)
    partition = next(
        item for item in discover_reachable_quotient(inputs, 31, 32) if item.layer == 31
    )
    all_dead = LayerQuotient(
        31,
        partition.variables,
        "node:0",
        (ClassSpec("DEAD", "dead", ()),),
        (
            DecisionNode(
                0,
                LinearAtom("le", (("L0", 1),), 1),
                "class:DEAD",
                "outside",
            ),
        ),
    )
    certificate = QuotientCertificate(
        "t28-tail-quotient-certificate-v1",
        19,
        "phase=0,n=0,column=82",
        (
            ("equations", EQUATIONS_CONTENT_SHA256),
            ("frontier", FRONTIER_CONTENT_SHA256),
            ("provenances", PROVENANCES_SHA256),
            ("t27_evidence", T27_EVIDENCE_SHA256),
        ),
        31,
        (all_dead, build_terminal_seed(inputs)),
        (),
    )

    check = check_quotient_certificate(inputs, certificate)

    assert check.status == "FAIL"
    assert [item.kind for item in check.obligations] == [
        "promoted_coverage",
        "promoted_coverage",
        "dead_has_no_successor",
    ]
    assert check.obligations[-1].counterexample is not None
