from pathlib import Path

from mathloop.artifacts import ArtifactStore


def test_identical_artifacts_share_one_digest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    first = store.put_bytes(b"exact witness", "text/plain")
    second = store.put_bytes(b"exact witness", "text/plain")

    assert first.digest == second.digest
    assert first.path.read_bytes() == b"exact witness"
    assert store.open(first.digest) == b"exact witness"
    assert len(list(tmp_path.rglob(first.digest))) == 1
