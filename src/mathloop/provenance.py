"""Immutable implementation, dependency, and execution-environment identities."""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAGE_IMAGE_DIGEST = (
    "sha256:6d0efd1d82d33eb5f6450af740d080a550c2b52948c0c5a34849c6d3c5004251"
)

_METHOD_FILES: dict[str, tuple[str, ...]] = {
    "integer_counterexample": (
        "src/mathloop/methods/integer_search.py",
        "src/mathloop/predicates/calibration.py",
    ),
    "symbolic_induction": ("src/mathloop/methods/symbolic.py",),
    "sage_polynomial": (
        "src/mathloop/methods/sage.py",
        "docker/sage/Dockerfile",
        "docker/sage/runner.py",
    ),
    "proof_sketch": (
        "src/mathloop/methods/proof_sketch.py",
        "src/mathloop/providers/openai.py",
    ),
}


def component_provenance(
    component: str,
    *relative_paths: str,
    container_digest: str | None = None,
) -> dict[str, object]:
    python_sources = tuple(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "src" / "mathloop").rglob("*.py")
    )
    all_paths = (*python_sources, *relative_paths)
    files = {
        relative_path: _file_sha256(PROJECT_ROOT / relative_path)
        for relative_path in sorted(set(all_paths))
    }
    environment = {
        "python": platform.python_version(),
        "platform": platform.system().lower(),
        "machine": platform.machine().lower(),
    }
    payload: dict[str, object] = {
        "schema_version": 1,
        "component": component,
        "implementation_files": files,
        "dependency_lock_sha256": _file_sha256(PROJECT_ROOT / "uv.lock"),
        "environment": environment,
    }
    if container_digest is not None:
        payload["container_image_digest"] = container_digest
    payload["identity_sha256"] = provenance_digest(payload)
    return payload


def provenance_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def method_provenance(family: str) -> dict[str, object]:
    try:
        paths = _METHOD_FILES[family]
    except KeyError as error:
        raise ValueError(f"unsupported method provenance family: {family}") from error
    return component_provenance(
        f"method:{family}",
        *paths,
        container_digest=(SAGE_IMAGE_DIGEST if family == "sage_polynomial" else None),
    )


def verifier_provenance(verifier: str) -> dict[str, object]:
    if verifier == "integer-predicate":
        return component_provenance(
            "verifier:integer-predicate",
            "src/mathloop/verification.py",
            "src/mathloop/verifiers/calibration.py",
        )
    if verifier == "sage-symbolic-induction":
        return component_provenance(
            "verifier:sage-symbolic-induction",
            "src/mathloop/verification.py",
            "docker/sage/Dockerfile",
            "docker/sage/runner.py",
            container_digest=SAGE_IMAGE_DIGEST,
        )
    raise ValueError(f"unsupported verifier provenance identity: {verifier}")


def validate_provenance(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("provenance must be a mapping")
    payload = dict(value)
    required = {
        "schema_version",
        "component",
        "implementation_files",
        "dependency_lock_sha256",
        "environment",
        "identity_sha256",
    }
    if set(payload) not in (required, required | {"container_image_digest"}):
        raise ValueError("provenance has an unsupported schema")
    identity = payload.pop("identity_sha256")
    if type(identity) is not str or identity != provenance_digest(payload):
        raise ValueError("provenance identity digest does not match its payload")
    payload["identity_sha256"] = identity
    return payload


def require_current_method_provenance(
    family: str,
    executable: object,
    registered: object,
    scheduled: object,
) -> dict[str, object]:
    executable_payload = validate_provenance(executable)
    registered_payload = validate_provenance(registered)
    if type(scheduled) is not str:
        raise ValueError("scheduled provenance must be an immutable identity digest")
    if family in _METHOD_FILES and executable_payload != method_provenance(family):
        raise ValueError("executable provenance differs from the current implementation")
    if registered_payload != executable_payload:
        raise ValueError("registered method provenance differs from the executable")
    if scheduled != registered_payload["identity_sha256"]:
        raise ValueError("scheduled method provenance differs from the registered method")
    return executable_payload


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
