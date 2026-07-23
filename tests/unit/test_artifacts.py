import os
import stat
from pathlib import Path

import pytest

import mathloop.artifacts as artifacts_module
from mathloop.artifacts import ArtifactStore


def test_identical_artifacts_share_one_digest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    first = store.put_bytes(b"exact witness", "text/plain")
    second = store.put_bytes(b"exact witness", "text/plain")

    assert first.digest == second.digest
    assert first.path.read_bytes() == b"exact witness"
    assert store.open(first.digest) == b"exact witness"
    assert len(list(tmp_path.rglob(first.digest))) == 1


def test_put_bytes_fsyncs_parent_directory_after_atomic_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, bool | None]] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def record_fsync(descriptor: int) -> None:
        calls.append(("fsync", stat.S_ISDIR(os.fstat(descriptor).st_mode)))
        original_fsync(descriptor)

    def record_replace(source: str | bytes, destination: str | bytes) -> None:
        calls.append(("replace", None))
        original_replace(source, destination)

    monkeypatch.setattr(artifacts_module.os, "fsync", record_fsync)
    monkeypatch.setattr(artifacts_module.os, "replace", record_replace)

    ArtifactStore(tmp_path).put_bytes(b"durable witness", "text/plain")

    assert calls == [
        ("fsync", False),
        ("replace", None),
        ("fsync", True),
        ("fsync", True),
        ("fsync", True),
    ]


def test_first_shard_write_fsyncs_leaf_and_each_new_ancestor_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []
    original = artifacts_module._fsync_directory

    def record(directory: Path) -> None:
        synced.append(directory)
        original(directory)

    monkeypatch.setattr(artifacts_module, "_fsync_directory", record)
    store = ArtifactStore(tmp_path)
    artifact = store.put_bytes(b"first shard artifact", "text/plain")

    assert synced == [
        artifact.path.parent,
        artifact.path.parent.parent,
        tmp_path,
    ]


def test_put_bytes_propagates_directory_fsync_failure_and_closes_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory_descriptor: int | None = None
    original_fsync = os.fsync

    def fail_directory_fsync(descriptor: int) -> None:
        nonlocal directory_descriptor
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directory_descriptor = descriptor
            raise OSError("directory fsync failed")
        original_fsync(descriptor)

    monkeypatch.setattr(artifacts_module.os, "fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="directory fsync failed"):
        ArtifactStore(tmp_path).put_bytes(b"durable witness", "text/plain")

    assert directory_descriptor is not None
    with pytest.raises(OSError):
        os.fstat(directory_descriptor)


def test_directory_fsync_is_skipped_when_platform_does_not_support_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifacts_module, "_DIRECTORY_FSYNC_SUPPORTED", False)

    def unexpected_open(path: Path, flags: int) -> int:
        del path, flags
        raise AssertionError("unsupported platforms must not open directories")

    monkeypatch.setattr(artifacts_module.os, "open", unexpected_open)

    artifacts_module._fsync_directory(Path("unused"))


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
