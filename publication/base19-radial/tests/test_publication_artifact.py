from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "publication" / "base19-radial"
TOPOLOGY = ARTIFACT / "instance" / "topology.json"
BUILDER = ARTIFACT / "scripts" / "build_manifest.py"
COMPARATOR = ARTIFACT / "scripts" / "compare_manifests.py"
INSTANCE_RENDERER = ARTIFACT / "scripts" / "render_lean_instance.py"
LEAN = ARTIFACT / "lean"
FRONTIER = ARTIFACT / "certificates" / "frontier.json"
KNOWN_WITNESS = ARTIFACT / "certificates" / "delete-p0-c0.json"
DELETIONS = ARTIFACT / "certificates" / "deletions.jsonl"
LEAN_DATA_RENDERER = ARTIFACT / "scripts" / "render_lean_data.py"
CERTIFICATE_EXPORTER = ARTIFACT / "scripts" / "export_certificates.py"
DELETION_AUDITOR = ARTIFACT / "scripts" / "audit_deletions.py"

sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("base19_build_manifest", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_exporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "base19_export_certificates", CERTIFICATE_EXPORTER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_deletion_auditor() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "base19_audit_deletions", DELETION_AUDITOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _redigest(payload: dict[str, object]) -> None:
    payload.pop("content_sha256", None)
    canonical = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()


def _production_rows() -> list[dict[str, object]]:
    from lychrel_arbitrary_topology import build_column_constraints
    from lychrel_interface_perturbations import InterfaceMove, move_interface
    from t22_lychrel_affine_lift import base17_reference_cycle
    from t26_radial_frontier import base19_candidate_provenances

    moved = move_interface(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
    )
    selected = set(base19_candidate_provenances())

    def atom_row(atom: object) -> dict[str, object]:
        variable = atom.variable
        if variable is not None:
            return {"variable": variable}
        return {"literal": atom.value}

    return [
        {
            "provenance": column.provenance,
            "left": atom_row(column.left),
            "right": atom_row(column.right),
            "target": atom_row(column.target),
            "carry_in": column.carry_in,
            "carry_out": column.carry_out,
        }
        for column in build_column_constraints(moved, 19, parameters=(0,))
        if column.provenance in selected
    ]


def test_topology_has_frozen_canonical_digest() -> None:
    payload = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    canonical = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    assert hashlib.sha256(canonical).hexdigest() == (
        "a0d84abc99ecd225fd80dbe6ce4ece1e230f39f89353a48695f1b85401b693c6"
    )


def test_standalone_manifest_matches_production_builder() -> None:
    builder = _load_builder()

    independent = builder.build_equations(builder.load_topology(TOPOLOGY))
    production = _production_rows()

    assert independent == production
    assert len(independent) == 409
    assert len({row["provenance"] for row in independent}) == 409
    assert independent[0]["provenance"] == "phase=0,n=0,column=0"
    assert independent[-1]["provenance"] == "phase=5,n=0,column=83"


def test_standalone_builder_imports_only_standard_library() -> None:
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "argparse",
        "dataclasses",
        "hashlib",
        "json",
        "pathlib",
        "sys",
        "typing",
    }
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert imported <= allowed


def test_manifest_cli_is_deterministic_and_self_digested(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    for output in (first, second):
        subprocess.run(
            (sys.executable, str(BUILDER), str(TOPOLOGY), str(output)),
            check=True,
            text=True,
            capture_output=True,
        )

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    digest = payload.pop("content_sha256")
    assert payload["schema"] == "base19-radial-equations-v1"
    assert payload["base"] == 19
    assert payload["equation_count"] == len(payload["equations"]) == 409
    assert hashlib.sha256(
        (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    ).hexdigest() == digest


def test_manifest_comparator_reports_first_mutated_field(tmp_path: Path) -> None:
    original = ARTIFACT / "instance" / "equations.json"
    mutated = tmp_path / "mutated.json"
    payload = json.loads(original.read_text(encoding="utf-8"))
    payload["equations"][0]["target"] = {"literal": 7}
    mutated.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        (sys.executable, str(COMPARATOR), str(original), str(mutated)),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "equations[0].target" in completed.stderr


def test_lean_instance_renderer_is_deterministic_and_transparent(tmp_path: Path) -> None:
    manifest = ARTIFACT / "instance" / "equations.json"
    outputs = (tmp_path / "first.lean", tmp_path / "second.lean")

    for output in outputs:
        subprocess.run(
            (sys.executable, str(INSTANCE_RENDERER), str(manifest), str(output)),
            check=True,
            text=True,
            capture_output=True,
        )

    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    source = outputs[0].read_text(encoding="utf-8")
    assert "def generatedVariableNames : List String" in source
    assert "def generatedCandidate : Problem" in source
    assert "List.replicate 409 .digit" in source
    assert "List.replicate 410 .carry" in source
    assert all(token not in source for token in ("sorry", "native_decide", "axiom"))


def test_lean_builder_exports_the_canonical_manifest() -> None:
    completed = subprocess.run(
        ("lake", "exe", "export_manifest"),
        cwd=LEAN,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.encode("utf-8") == (
        ARTIFACT / "instance" / "equations.json"
    ).read_bytes()


def test_promoted_frontier_and_witness_have_exact_checked_schema() -> None:
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    witness = json.loads(KNOWN_WITNESS.read_text(encoding="utf-8"))

    assert frontier["schema"] == "base19-radial-frontier-v1"
    assert frontier["status"] == "UNSAT"
    assert frontier["base"] == 19
    assert frontier["equation_count"] == 409
    assert len(frontier["layers"]) == 35
    assert frontier["max_reachable_state_count"] == 314
    assert frontier["layers"][0]["layer"] == -1
    assert frontier["layers"][-1]["layer"] == 33
    assert frontier["layers"][-1]["output_states"] == []
    for layer in frontier["layers"]:
        payload = json.dumps(
            layer["output_states"],
            separators=(",", ":"),
        ).encode("ascii")
        assert hashlib.sha256(payload).hexdigest() == layer["output_states_sha256"]
        assert len(layer["equation_provenances"]) == layer["equation_count"]
        assert len(layer["transitions"]) == layer["input_state_count"]
        assert {
            tuple(output)
            for transition in layer["transitions"]
            for output in transition["output_states"]
        } == {tuple(output) for output in layer["output_states"]}

    assert witness["schema"] == "base19-radial-witness-v1"
    assert witness["status"] == "SAT"
    assert witness["removed"] == "phase=0,n=0,column=0"
    assert witness["witness_replay"] == {
        "status": "valid",
        "equation_count": 408,
        "digit_count": 409,
        "carry_count": 410,
    }


def test_lean_data_renderer_rejects_an_out_of_range_state(tmp_path: Path) -> None:
    corrupted = tmp_path / "corrupted-frontier.json"
    payload = json.loads(FRONTIER.read_text(encoding="utf-8"))
    layer = next(item for item in payload["layers"] if item["output_states"])
    layer["output_states"][0][0] = 19
    corrupted.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        (
            sys.executable,
            str(LEAN_DATA_RENDERER),
            "--frontier",
            str(corrupted),
            "--witness",
            str(KNOWN_WITNESS),
            "--output-dir",
            str(tmp_path / "generated"),
        ),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "outside its declared domain" in completed.stderr


def test_lean_data_renderer_rejects_a_disconnected_transition(tmp_path: Path) -> None:
    corrupted = tmp_path / "disconnected-frontier.json"
    payload = json.loads(FRONTIER.read_text(encoding="utf-8"))
    layer = next(
        item
        for item in payload["layers"]
        if item["transitions"] and item["transitions"][0]["input_state"]
    )
    input_state = layer["transitions"][0]["input_state"]
    input_state[0] = 1 - input_state[0]
    corrupted.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        (
            sys.executable,
            str(LEAN_DATA_RENDERER),
            "--frontier",
            str(corrupted),
            "--witness",
            str(KNOWN_WITNESS),
            "--output-dir",
            str(tmp_path / "generated"),
        ),
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "do not match the input frontier" in completed.stderr


def test_lean_data_renderer_replays_witness_and_rejects_corruption(
    tmp_path: Path,
) -> None:
    original = json.loads(KNOWN_WITNESS.read_text(encoding="utf-8"))
    corruptions = []

    missing = json.loads(json.dumps(original))
    missing["witness"]["digits"].pop(next(iter(missing["witness"]["digits"])))
    _redigest(missing)
    corruptions.append(("missing", missing))

    out_of_range = json.loads(json.dumps(original))
    first_digit = next(iter(out_of_range["witness"]["digits"]))
    out_of_range["witness"]["digits"][first_digit] = 19
    _redigest(out_of_range)
    corruptions.append(("out-of-range", out_of_range))

    changed_carry = json.loads(json.dumps(original))
    first_carry = next(iter(changed_carry["witness"]["carries"]))
    changed_carry["witness"]["carries"][first_carry] = (
        1 - changed_carry["witness"]["carries"][first_carry]
    )
    _redigest(changed_carry)
    corruptions.append(("changed-carry", changed_carry))

    for name, payload in corruptions:
        corrupted = tmp_path / f"{name}.json"
        corrupted.write_text(json.dumps(payload), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                str(LEAN_DATA_RENDERER),
                "--frontier",
                str(FRONTIER),
                "--witness",
                str(corrupted),
                "--output-dir",
                str(tmp_path / f"generated-{name}"),
            ),
            check=False,
            text=True,
            capture_output=True,
        )
        assert completed.returncode != 0, name


def test_certificate_exporter_replays_witness_on_readback() -> None:
    exporter = _load_exporter()
    corrupted = json.loads(KNOWN_WITNESS.read_text(encoding="utf-8"))
    first_carry = next(iter(corrupted["witness"]["carries"]))
    corrupted["witness"]["carries"][first_carry] = (
        1 - corrupted["witness"]["carries"][first_carry]
    )

    try:
        exporter._validate_witness(corrupted)
    except ValueError as error:
        assert "witness violates" in str(error)
    else:
        raise AssertionError("corrupted witness passed exporter replay")


def test_deletion_audit_writes_completion_order_as_canonical_candidate_order(
    tmp_path: Path,
) -> None:
    auditor = _load_deletion_auditor()
    candidates = ("equation-0", "equation-1", "equation-2")
    records = {
        index: auditor.make_record(index, removed, "UNSAT", None, None)
        for index, removed in enumerate(candidates)
    }
    output = tmp_path / "deletions.jsonl"

    next_index = auditor.append_ready_records(
        output,
        candidates,
        {2: records[2], 0: records[0], 1: records[1]},
        0,
    )

    assert next_index == 3
    assert auditor.load_prefix(output, candidates, replay_sat=False) == records
    assert [
        json.loads(line)["removed"] for line in output.read_text().splitlines()
    ] == list(candidates)


def test_deletion_audit_resume_and_promotion_are_fail_closed(tmp_path: Path) -> None:
    auditor = _load_deletion_auditor()
    candidates = ("equation-0", "equation-1", "equation-2")
    output = tmp_path / "deletions.jsonl"
    first = auditor.make_record(0, candidates[0], "UNSAT", None, None)
    auditor.append_ready_records(output, candidates, {0: first}, 0)
    loaded = auditor.load_prefix(output, candidates, replay_sat=False)

    assert set(loaded) == {0}
    assert not auditor.minimality_promotable(loaded, candidates)

    sat_records = {
        index: auditor.make_record(
            index,
            removed,
            "SAT",
            {"digits": {}, "carries": {}},
            {"status": "valid"},
        )
        for index, removed in enumerate(candidates)
    }
    assert not auditor.minimality_promotable(
        {index: sat_records[index] for index in range(2)}, candidates
    )
    assert auditor.minimality_promotable(sat_records, candidates)


def test_deletion_audit_completes_inactive_variables() -> None:
    auditor = _load_deletion_auditor()
    certificate = json.loads(KNOWN_WITNESS.read_text(encoding="utf-8"))
    projected = json.loads(json.dumps(certificate["witness"]))
    projected["carries"].pop("c:p0:n0:col33")

    completed = auditor.complete_witness(projected)

    assert completed["carries"]["c:p0:n0:col33"] == 0
    assert len(completed["digits"]) == 409
    assert len(completed["carries"]) == 410
    auditor.validate_projected_replay(
        {
            "status": "valid",
            "equation_count": 408,
            "digit_count": 409,
            "carry_count": 409,
        },
        projected,
    )


def test_complete_deletion_audit_identifies_the_unique_minimal_core() -> None:
    auditor = _load_deletion_auditor()
    candidates = auditor.base19_candidate_provenances()
    records = auditor.load_prefix(DELETIONS, candidates)

    assert len(records) == len(candidates) == 409
    assert hashlib.sha256(DELETIONS.read_bytes()).hexdigest() == (
        "0566f6e2025aec28fe0d2f824f1f6b343cf912e9191a9036629a2a1d4ef03325"
    )
    unsat = [record for record in records.values() if record["status"] == "UNSAT"]
    sat = [record for record in records.values() if record["status"] == "SAT"]
    assert len(sat) == 408
    assert [(record["candidate_index"], record["removed"]) for record in unsat] == [
        (68, "phase=0,n=0,column=82")
    ]
    assert not auditor.minimality_promotable(records, candidates)

    minimal_core = tuple(
        provenance
        for provenance in candidates
        if provenance != "phase=0,n=0,column=82"
    )
    assert len(minimal_core) == 408
    assert {record["removed"] for record in sat} == set(minimal_core)


def test_lean_data_renderer_is_deterministic(tmp_path: Path) -> None:
    outputs = (tmp_path / "first", tmp_path / "second")
    for output in outputs:
        subprocess.run(
            (
                sys.executable,
                str(LEAN_DATA_RENDERER),
                "--frontier",
                str(FRONTIER),
                "--witness",
                str(KNOWN_WITNESS),
                "--output-dir",
                str(output),
            ),
            check=True,
            text=True,
            capture_output=True,
        )

    for name in ("FrontierData.lean", "WitnessData.lean", "Witness.lean"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
        assert (outputs[0] / name).read_bytes() == (
            LEAN / "Base19Radial" / "Generated" / name
        ).read_bytes()
    assert not (outputs[0] / "FrontiersExperimental.lean").exists()


def test_experimental_frontier_proof_render_is_explicit_and_deterministic(
    tmp_path: Path,
) -> None:
    outputs = (tmp_path / "first-experimental", tmp_path / "second-experimental")
    for output in outputs:
        subprocess.run(
            (
                sys.executable,
                str(LEAN_DATA_RENDERER),
                "--frontier",
                str(FRONTIER),
                "--witness",
                str(KNOWN_WITNESS),
                "--output-dir",
                str(output),
                "--experimental-frontier-proofs",
            ),
            check=True,
            text=True,
            capture_output=True,
        )

    name = "FrontiersExperimental.lean"
    assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    source = (outputs[0] / name).read_text(encoding="utf-8")
    assert "generatedLayerNeg1Closed" in source
    assert "generatedLayer22Closed" in source
    assert "generatedLayer33Closed" in source
    assert all(token not in source for token in ("sorry", "native_decide", "axiom"))
