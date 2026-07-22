from pathlib import Path

import pytest

from mathloop.artifacts import ArtifactStore


def test_identical_artifacts_share_one_digest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    first = store.put_bytes(b"exact witness", "text/plain")
    second = store.put_bytes(b"exact witness", "text/plain")

    assert first.digest == second.digest
    assert first.path.read_bytes() == b"exact witness"
    assert store.open(first.digest) == b"exact witness"
    assert len(list(tmp_path.rglob(first.digest))) == 1


@pytest.mark.parametrize(
    "digest",
    [
        "../" + "a" * 61,
        "/" + "a" * 64,
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
    ],
)
def test_open_rejects_invalid_artifact_digests(tmp_path: Path, digest: str) -> None:
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        store.open(digest)


def test_open_rejects_a_valid_digest_path_that_resolves_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.write_bytes(b"not an artifact")
    digest = "a" * 64
    destination = root / digest[:2] / digest[2:4] / digest
    destination.parent.mkdir(parents=True)
    destination.symlink_to(outside)
    store = ArtifactStore(root)

    with pytest.raises(ValueError, match="outside artifact root"):
        store.open(digest)
