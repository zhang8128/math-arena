from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_invariant_certificate import (  # noqa: E402
    Conjunction,
    LayerPredicate,
    LinearAtom,
)
from lychrel_reachability_separator import (  # noqa: E402
    CounterexampleTrace,
    SemanticWitness,
    SeparatorCertificate,
    SeparatorDataset,
    TraceStep,
    finite_separation_failures,
    parse_counterexample_trace,
    parse_separator_certificate,
)
from t28_base19_tail_quotient import (  # noqa: E402
    replay_layer31_counterexample_trace,
)


def test_trace_distinguishes_terminal_iteration_from_counterexample_count() -> None:
    """Counting the failed candidate as a model would recreate the T29 off-by-one."""
    trace = CounterexampleTrace(
        schema="t29-base19-counterexample-trace-v1",
        variables=("x",),
        steps=(
            TraceStep(
                iteration=1,
                input_state=(("x", 0),),
                rejected_class="DEAD",
                obligation="dead_has_no_successor",
                candidate_atom_count=3,
                node_count=1,
                path_depth=1,
            ),
        ),
        terminal_iteration=2,
        stop_reason="decision_depth_exceeded",
    )

    assert len(trace.steps) == 1
    assert trace.terminal_iteration == 2


def test_finite_failures_reject_live_control_absorption() -> None:
    """Ignoring live controls would turn a reachability separator into a dead guard."""
    predicate = LayerPredicate(
        layer=31,
        variables=("x",),
        clauses=(Conjunction((LinearAtom("le", (("x", 1),), 1),)),),
    )
    dataset = SeparatorDataset(
        variables=("x",),
        positives=((0,),),
        trace_negatives=((2,),),
        live_controls=((1,),),
    )

    assert finite_separation_failures(predicate, dataset) == (
        ("live_control", (1,)),
    )


def trace_fixture() -> CounterexampleTrace:
    return CounterexampleTrace(
        schema="t29-base19-counterexample-trace-v1",
        variables=("x",),
        steps=(
            TraceStep(1, (("x", 2),), "DEAD", "dead_has_no_successor", 4, 2, 2),
        ),
        terminal_iteration=2,
        stop_reason="decision_depth_exceeded",
    )


def test_trace_parser_round_trips_strict_canonical_payload() -> None:
    """A permissive parser could silently reorder or discard trace evidence."""
    trace = trace_fixture()

    assert parse_counterexample_trace(trace.to_payload()) == trace

    mutated = trace.to_payload()
    mutated["unexpected"] = True
    with pytest.raises(ValueError, match="trace keys differ"):
        parse_counterexample_trace(mutated)


def certificate_fixture(*, semantic_status: str = "SAT") -> SeparatorCertificate:
    witness = SemanticWitness(
        input_state=(("x", 2),),
        output_state=(("y", 3),),
        local_state=(("z", 1),),
    )
    return SeparatorCertificate(
        schema="t29-base19-reachability-separator-certificate-v1",
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=(
            ("equations", "a" * 64),
            ("frontier", "b" * 64),
            ("provenances", "c" * 64),
            ("t27_evidence", "d" * 64),
            ("t28_evidence", "e" * 64),
            ("t28_independent", "f" * 64),
        ),
        trace_sha256="1" * 64,
        dataset_sha256="2" * 64,
        predicate=LayerPredicate(
            layer=31,
            variables=("x",),
            clauses=(Conjunction((LinearAtom("eq", (("x", 1),), 0),)),),
        ),
        finite_status="PASS",
        semantic_status=semantic_status,
        semantic_witness=witness if semantic_status == "SAT" else None,
    )


def test_certificate_parser_round_trips_sat_witness() -> None:
    """Dropping a SAT witness would turn a semantic STOP into an unsupported claim."""
    certificate = certificate_fixture()

    assert parse_separator_certificate(certificate.to_payload()) == certificate


def test_certificate_requires_witness_exactly_for_semantic_sat() -> None:
    """Witness presence must agree with the semantic status in both directions."""
    with pytest.raises(ValueError, match="SAT certificate requires a witness"):
        SeparatorCertificate(
            **{
                **certificate_fixture().to_payload(),
                "source_digests": tuple(certificate_fixture().source_digests),
                "predicate": certificate_fixture().predicate,
                "semantic_witness": None,
            }
        )

    with pytest.raises(ValueError, match="only SAT certificates carry a witness"):
        SeparatorCertificate(
            **{
                **certificate_fixture().to_payload(),
                "source_digests": tuple(certificate_fixture().source_digests),
                "predicate": certificate_fixture().predicate,
                "semantic_status": "UNSAT",
                "semantic_witness": certificate_fixture().semantic_witness,
            }
        )


def test_semantic_witness_rejects_overlapping_sections() -> None:
    """Overlapping local/frontier names would make equation replay ambiguous."""
    with pytest.raises(ValueError, match="witness sections must be disjoint"):
        SemanticWitness(
            input_state=(("x", 1),),
            output_state=(("y", 2),),
            local_state=(("x", 0),),
        )


def test_trace_rejects_empty_counterexample_history() -> None:
    """An empty trace cannot substantiate the claimed candidate-222 boundary."""
    with pytest.raises(ValueError, match="trace must contain a counterexample"):
        CounterexampleTrace(
            schema="t29-base19-counterexample-trace-v1",
            variables=("x",),
            steps=(),
            terminal_iteration=1,
            stop_reason="decision_depth_exceeded",
        )


def test_dataset_rejects_non_string_variable_scope() -> None:
    """Accepting an integer variable would make JSON and assignment scopes diverge."""
    with pytest.raises(ValueError, match="dataset variables must be nonempty strings"):
        SeparatorDataset(
            variables=(1,),  # type: ignore[arg-type]
            positives=((0,),),
            trace_negatives=((1,),),
            live_controls=((2,),),
        )


def test_trace_step_rejects_non_string_labels() -> None:
    """Truthy non-string labels must not survive into canonical research evidence."""
    with pytest.raises(ValueError, match="trace class and obligation must be strings"):
        TraceStep(
            iteration=1,
            input_state=(("x", 0),),
            rejected_class=1,  # type: ignore[arg-type]
            obligation="dead_has_no_successor",
            candidate_atom_count=1,
            node_count=1,
            path_depth=1,
        )


def test_certificate_rejects_duplicate_source_digest_name() -> None:
    """Set equality alone would allow two conflicting identities for one source."""
    certificate = certificate_fixture()
    duplicated = tuple(
        sorted((*certificate.source_digests, ("equations", "9" * 64)))
    )

    with pytest.raises(ValueError, match="source digest names differ"):
        SeparatorCertificate(
            schema=certificate.schema,
            base=certificate.base,
            removed=certificate.removed,
            source_digests=duplicated,
            trace_sha256=certificate.trace_sha256,
            dataset_sha256=certificate.dataset_sha256,
            predicate=certificate.predicate,
            finite_status=certificate.finite_status,
            semantic_status=certificate.semantic_status,
            semantic_witness=certificate.semantic_witness,
        )


def test_trace_rejects_non_string_stop_reason() -> None:
    """The terminal claim must remain a typed reason, not a truthy JSON value."""
    with pytest.raises(ValueError, match="trace stop reason must be a string"):
        CounterexampleTrace(
            schema="t29-base19-counterexample-trace-v1",
            variables=("x",),
            steps=trace_fixture().steps,
            terminal_iteration=2,
            stop_reason=1,  # type: ignore[arg-type]
        )


def test_real_t28_trace_replay_stops_after_221_exact_counterexamples() -> None:
    """Candidate 222 is a depth failure, not a 222nd semantic model."""
    result, trace = replay_layer31_counterexample_trace(ROOT)

    assert result.status == "STOP"
    assert result.iterations == 222
    assert result.stop_reason == "decision_depth_exceeded"
    assert len(trace.steps) == 221
    assert tuple(step.iteration for step in trace.steps) == tuple(range(1, 222))
    assert len({step.input_state for step in trace.steps}) == 221
    assert {step.rejected_class for step in trace.steps} == {"DEAD"}
    assert {step.obligation for step in trace.steps} == {
        "dead_has_no_successor"
    }
    assert trace.terminal_iteration == 222
    assert trace.stop_reason == "decision_depth_exceeded"
    assert dict(trace.steps[-1].input_state) == {
        "D0": 18,
        "D1": 6,
        "L0": 0,
        "L1": 1,
        "L2": 1,
        "L3": 0,
        "L4": 0,
        "L5": 0,
        "R0": 0,
        "R1": 0,
        "R2": 1,
        "R3": 0,
        "R4": 0,
        "R5": 1,
    }
