from pathlib import Path

import pytest

from mathloop import provenance
from mathloop.codex.domain import CodexModelRole


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


# ---------------------------------------------------------------------------
# Codex method provenance: parameterized by model/role/CLI version as well
# as source, since one method family covers several models across three
# roles behind a single dispatch point.
# ---------------------------------------------------------------------------


def _codex_provenance(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "model": "gpt-5.6-terra",
        "role": CodexModelRole.TERRA,
        "min_cli_version": "0.145.0",
    }
    kwargs.update(overrides)
    return provenance.codex_method_provenance(**kwargs)  # type: ignore[arg-type]


def test_codex_provenance_is_accepted_unchanged_by_validate_provenance() -> None:
    """No new top-level payload keys: model/role/CLI version ride inside
    `component`, so `validate_provenance`'s existing required-key schema
    needs no changes and every other caller keeps working unchanged."""
    payload = _codex_provenance()

    assert provenance.validate_provenance(payload) == payload


def test_codex_provenance_changes_with_model() -> None:
    base = _codex_provenance()
    changed = _codex_provenance(model="gpt-5.6-luna")

    assert changed["identity_sha256"] != base["identity_sha256"]


def test_codex_provenance_changes_with_role() -> None:
    base = _codex_provenance()
    changed = _codex_provenance(role=CodexModelRole.SOL)

    assert changed["identity_sha256"] != base["identity_sha256"]


def test_codex_provenance_changes_with_min_cli_version() -> None:
    base = _codex_provenance()
    changed = _codex_provenance(min_cli_version="0.146.0")

    assert changed["identity_sha256"] != base["identity_sha256"]


def test_codex_provenance_changes_with_launch_policy_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _codex_provenance()
    launch_path = provenance.PROJECT_ROOT / "src/mathloop/codex/launch.py"
    original = provenance._file_sha256

    def changed_hash(path: Path) -> str:
        if path == launch_path:
            return "e" * 64
        return original(path)

    monkeypatch.setattr(provenance, "_file_sha256", changed_hash)

    after = _codex_provenance()
    assert after["identity_sha256"] != before["identity_sha256"]


def test_codex_provenance_changes_with_codex_client_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _codex_provenance()
    client_path = provenance.PROJECT_ROOT / "src/mathloop/codex/client.py"
    original = provenance._file_sha256

    def changed_hash(path: Path) -> str:
        if path == client_path:
            return "d" * 64
        return original(path)

    monkeypatch.setattr(provenance, "_file_sha256", changed_hash)

    after = _codex_provenance()
    assert after["identity_sha256"] != before["identity_sha256"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", ""),
        ("model", "   "),
        ("min_cli_version", ""),
        ("min_cli_version", "   "),
    ],
)
def test_codex_provenance_rejects_blank_strings(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        _codex_provenance(**{field: value})


def test_codex_provenance_rejects_non_role() -> None:
    with pytest.raises(TypeError):
        _codex_provenance(role="terra")
