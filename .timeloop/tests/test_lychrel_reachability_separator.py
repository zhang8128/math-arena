from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEPENDENT = (
    ROOT
    / ".timeloop"
    / "runs"
    / "t29_base19_reachability_separator_independent.py"
)
T29_EVIDENCE = ROOT / ".timeloop" / "runs" / "t29_base19_reachability_separator.json"
T29_TRACE = (
    ROOT / ".timeloop" / "runs" / "t29_base19_reachability_separator_trace.json"
)
T29_DATASET = (
    ROOT / ".timeloop" / "runs" / "t29_base19_reachability_separator_dataset.json"
)
T29_CERTIFICATE = (
    ROOT
    / ".timeloop"
    / "runs"
    / "t29_base19_reachability_separator_certificate.json"
)
T29_INDEPENDENT_AUDIT = (
    ROOT
    / ".timeloop"
    / "runs"
    / "t29_base19_reachability_separator_independent.json"
)
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

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
    TraceStep,
    finite_separation_failures,
    parse_counterexample_trace,
    parse_separator_certificate,
)
from t28_base19_tail_quotient import (  # noqa: E402
    replay_layer31_counterexample_trace,
)
from t29_base19_reachability_separator import (  # noqa: E402
    AtomPool,
    SemanticCheck,
    SeparatorLimits,
    build_candidate_atom_pool,
    build_separator_dataset,
    check_finite_separator,
    check_semantic_dead_region,
    dataset_payload,
    decide_t29_gate,
    load_t29_inputs,
    render_t29_report,
    synthesize_finite_separator,
    trace_payload,
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


def test_real_t29_adapter_builds_the_frozen_disjoint_dataset() -> None:
    """The finite question has 12 positives and 227 distinct controls."""
    inputs = load_t29_inputs(ROOT)
    _, trace = replay_layer31_counterexample_trace(ROOT)
    dataset = build_separator_dataset(inputs, trace)

    assert len(dataset.positives) == 12
    assert len(dataset.trace_negatives) == 221
    assert len(dataset.live_controls) == 6
    assert not set(dataset.positives) & set(dataset.trace_negatives)
    assert not set(dataset.positives) & set(dataset.live_controls)
    assert not set(dataset.trace_negatives) & set(dataset.live_controls)
    assert SeparatorLimits().coefficients == tuple(range(-3, 4))
    assert SeparatorLimits().moduli == tuple(range(2, 21))
    assert trace_payload(trace)["counts"] == {"counterexamples": 221}
    assert dataset_payload(dataset)["counts"] == {
        "positives": 12,
        "trace_negatives": 221,
        "live_controls": 6,
    }


def test_finite_separator_finds_one_clause_toy_optimum() -> None:
    """A single equality is the exact cheapest separator for this dataset."""
    dataset = SeparatorDataset(
        variables=("x",),
        positives=((0,),),
        trace_negatives=((1,),),
        live_controls=((2,),),
    )
    atom = LinearAtom("eq", (("x", 1),), 0)

    result = synthesize_finite_separator(
        dataset,
        AtomPool((atom,)),
        SeparatorLimits(),
    )

    assert result.status == "PASS"
    assert result.predicate == LayerPredicate(
        layer=31,
        variables=("x",),
        clauses=(Conjunction((atom,)),),
    )
    assert result.objective[:3] == (1, 1, 1)


@pytest.mark.parametrize(
    ("positives", "trace_negatives", "live_controls", "clause_count"),
    (
        (((0,), (2,)), ((1,),), ((3,),), 2),
        (((0,), (2,), (4,)), ((1,), (3,)), ((5,),), 3),
    ),
)
def test_finite_separator_requires_each_disconnected_positive_clause(
    positives: tuple[tuple[int, ...], ...],
    trace_negatives: tuple[tuple[int, ...], ...],
    live_controls: tuple[tuple[int, ...], ...],
    clause_count: int,
) -> None:
    """Singleton equalities expose whether two- and three-clause DNF works."""
    dataset = SeparatorDataset(
        variables=("x",),
        positives=positives,
        trace_negatives=trace_negatives,
        live_controls=live_controls,
    )
    atoms = tuple(
        sorted(
            (
                LinearAtom("eq", (("x", 1),), state[0])
                for state in positives
            ),
            key=canonical_bytes,
        )
    )

    result = synthesize_finite_separator(
        dataset,
        AtomPool(atoms),
        SeparatorLimits(),
    )

    assert result.status == "PASS"
    assert result.objective is not None
    assert result.objective[:3] == (clause_count, clause_count, 1)


def test_finite_separator_stop_names_first_uncovered_positive() -> None:
    """A bounded failure needs a checkable state, not an opaque solver result."""
    dataset = SeparatorDataset(
        variables=("x",),
        positives=((0,), (2,)),
        trace_negatives=((1,),),
        live_controls=((3,),),
    )
    pool = AtomPool((LinearAtom("eq", (("x", 1),), 0),))

    result = synthesize_finite_separator(dataset, pool, SeparatorLimits())

    assert result.status == "STOP"
    assert result.stop_reason == "finite_separator_not_found"
    assert result.failures == (("positive", (2,)),)


def test_real_atom_pool_reconstructs_the_bounded_t28_seed() -> None:
    """The enriched pool must retain the 37-atom T28 refinement boundary."""
    inputs = load_t29_inputs(ROOT)
    _, trace = replay_layer31_counterexample_trace(ROOT)
    dataset = build_separator_dataset(inputs, trace)

    pool = build_candidate_atom_pool(inputs, dataset, SeparatorLimits())
    result = synthesize_finite_separator(dataset, pool, SeparatorLimits())

    assert len(pool.atoms) == 83
    assert pool.atoms == tuple(sorted(set(pool.atoms), key=canonical_bytes))
    assert all(
        coefficient in range(-3, 4)
        for atom in pool.atoms
        for _, coefficient in atom.terms
    )
    assert all(
        atom.modulus is None or atom.modulus in range(2, 21)
        for atom in pool.atoms
    )
    assert result.status == "PASS"
    assert result.predicate is not None
    assert result.objective is not None
    assert result.objective[:7] == (1, 10, 10, 22, 25, 9, 0)
    assert len(result.predicate.clauses[0].atoms) == 10
    assert check_finite_separator(dataset, result.predicate) == ()


def test_semantic_dead_region_control_finds_a_complete_successor_witness() -> None:
    """A predicate true over the digit domain must not be promoted to dead."""
    inputs = load_t29_inputs(ROOT)
    predicate = LayerPredicate(
        layer=31,
        variables=tuple(sorted(inputs.partition.variables)),
        clauses=(
            Conjunction((LinearAtom("le", (("D0", -1),), 0),)),
        ),
    )

    result = check_semantic_dead_region(inputs, predicate)

    assert isinstance(result, SemanticCheck)
    assert result.status == "SAT"
    assert result.witness is not None
    assert len(result.witness.input_state) == 14
    assert len(result.witness.output_state) == 14
    assert result.equation_count == 12


def test_semantic_dead_region_control_proves_an_empty_predicate_unsat() -> None:
    """D0 is a base-19 digit, so D0 <= -1 has no transition model."""
    inputs = load_t29_inputs(ROOT)
    predicate = LayerPredicate(
        layer=31,
        variables=tuple(sorted(inputs.partition.variables)),
        clauses=(
            Conjunction((LinearAtom("le", (("D0", 1),), -1),)),
        ),
    )

    result = check_semantic_dead_region(inputs, predicate)

    assert result.status == "UNSAT"
    assert result.witness is None
    assert result.equation_count == 12


def test_primary_gate_preserves_finite_pass_with_semantic_counterexample() -> None:
    """Semantic SAT stops promotion but must not erase finite separation."""
    dataset = SeparatorDataset(
        variables=("x",),
        positives=((0,),),
        trace_negatives=((1,),),
        live_controls=((2,),),
    )
    atom = LinearAtom("eq", (("x", 1),), 0)
    finite = synthesize_finite_separator(
        dataset,
        AtomPool((atom,)),
        SeparatorLimits(),
    )
    witness = SemanticWitness(
        input_state=(("input:x", 0),),
        output_state=(("output:y", 1),),
        local_state=(("local:z", 0),),
    )
    semantic = SemanticCheck("SAT", witness, 12)
    frozen = load_t29_inputs(ROOT)
    baseline = {
        "source_digests": frozen.source_digests,
        "trace_sha256": "1" * 64,
        "dataset_sha256": "2" * 64,
        "pool_size": 1,
        "counts": {
            "positives": 1,
            "trace_negatives": 1,
            "live_controls": 1,
        },
    }

    evidence, certificate = decide_t29_gate(baseline, finite, semantic)

    assert evidence["status"] == "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
    assert evidence["semantic_counterexample"] == witness.to_payload()
    assert certificate is not None
    assert certificate.finite_status == "PASS"
    assert certificate.semantic_status == "SAT"
    assert certificate.semantic_witness == witness
    report = render_t29_report(evidence)
    assert "FINITE_SEPARATOR_PASS_SEMANTIC_STOP" in report
    assert "finite-only" in report
    assert "semantic successor" in report


def test_independent_checker_starts_under_isolated_python() -> None:
    """Assurance must not rely on repository imports or site packages."""
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert all(
        name in completed.stdout
        for name in (
            "EQUATIONS",
            "FRONTIER",
            "T28_EVIDENCE",
            "TRACE",
            "DATASET",
            "T29_EVIDENCE",
        )
    )


def independent_command(
    *,
    trace: Path = T29_TRACE,
    dataset: Path = T29_DATASET,
    evidence: Path = T29_EVIDENCE,
    certificate: Path = T29_CERTIFICATE,
) -> list[str]:
    return [
        sys.executable,
        "-I",
        str(INDEPENDENT),
        str(ROOT / "publication" / "base19-radial" / "instance" / "equations.json"),
        str(
            ROOT
            / "publication"
            / "base19-radial"
            / "certificates"
            / "minimal-core-frontier.json"
        ),
        str(ROOT / ".timeloop" / "runs" / "t28_base19_tail_quotient.json"),
        str(trace),
        str(dataset),
        str(evidence),
        str(certificate),
    ]


def test_independent_checker_accepts_durable_t29_artifacts() -> None:
    """The isolated checker must reproduce the primary achieved boundary."""
    completed = subprocess.run(
        independent_command(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    audit = json.loads(completed.stdout)
    assert audit["status"] == "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
    assert audit["repository_imports"] == []
    assert audit["finite_replay_counts"] == {
        "positives": 12,
        "trace_negatives": 221,
        "live_controls": 6,
    }
    assert audit["semantic_successor_replayed"] is True
    assert completed.stdout == T29_INDEPENDENT_AUDIT.read_text(encoding="utf-8")


def test_independent_checker_rejects_a_mutated_predicate(
    tmp_path: Path,
) -> None:
    """A finite atom mutation must never survive isolated assurance."""
    payload = json.loads(T29_CERTIFICATE.read_text(encoding="utf-8"))
    payload["predicate"]["clauses"][0]["atoms"][0]["constant"] += 1
    mutated = tmp_path / "mutated-certificate.json"
    mutated.write_bytes(canonical_bytes(payload) + b"\n")

    completed = subprocess.run(
        independent_command(certificate=mutated),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.startswith("REJECT:")


@pytest.mark.parametrize(
    "target",
    ("trace_iteration", "live_control", "source_digest", "semantic_witness"),
)
def test_independent_checker_rejects_mutated_assurance_inputs(
    target: str,
    tmp_path: Path,
) -> None:
    """Trace, dataset, identity, and equation-witness mutations all fail closed."""
    paths = {
        "trace": T29_TRACE,
        "dataset": T29_DATASET,
        "evidence": T29_EVIDENCE,
        "certificate": T29_CERTIFICATE,
    }
    selected = {
        "trace_iteration": "trace",
        "live_control": "dataset",
        "source_digest": "evidence",
        "semantic_witness": "certificate",
    }[target]
    payload = json.loads(paths[selected].read_text(encoding="utf-8"))
    if target == "trace_iteration":
        payload["steps"][0]["iteration"] = 2
    elif target == "live_control":
        payload["live_controls"][0][0] += 1
    elif target == "source_digest":
        payload["source_digests"]["equations"] = "0" * 64
    else:
        local = payload["semantic_witness"]["local_state"]
        local[next(iter(sorted(local)))] += 1
    mutated = tmp_path / f"mutated-{selected}.json"
    mutated.write_bytes(canonical_bytes(payload) + b"\n")
    paths[selected] = mutated

    completed = subprocess.run(
        independent_command(**paths),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.startswith("REJECT:")
