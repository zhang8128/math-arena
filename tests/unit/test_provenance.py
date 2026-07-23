from pathlib import Path

import pytest

from mathloop import provenance


def test_shared_semantic_dependency_changes_method_and_verifier_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method_before = provenance.method_provenance("integer_counterexample")
    verifier_before = provenance.verifier_provenance("integer-predicate")
    shared = provenance.PROJECT_ROOT / "src/mathloop/methods/base.py"
    original = provenance._file_sha256

    def changed_hash(path: Path) -> str:
        if path == shared:
            return "f" * 64
        return original(path)

    monkeypatch.setattr(provenance, "_file_sha256", changed_hash)

    method_after = provenance.method_provenance("integer_counterexample")
    verifier_after = provenance.verifier_provenance("integer-predicate")
    assert method_after["identity_sha256"] != method_before["identity_sha256"]
    assert verifier_after["identity_sha256"] != verifier_before["identity_sha256"]


def test_provenance_payload_rejects_digest_tampering() -> None:
    payload = provenance.method_provenance("symbolic_induction")
    payload["identity_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="identity digest"):
        provenance.validate_provenance(payload)
