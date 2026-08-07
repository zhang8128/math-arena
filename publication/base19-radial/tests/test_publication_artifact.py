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
LEAN_DATA_RENDERER = ARTIFACT / "scripts" / "render_lean_data.py"

sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("base19_build_manifest", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    for name in ("FrontierData.lean", "WitnessData.lean"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
