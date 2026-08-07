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
