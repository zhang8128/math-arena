import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

_DIRECTORY_FSYNC_SUPPORTED = os.name != "nt"


@dataclass(frozen=True)
class StoredArtifact:
    digest: str
    media_type: str
    size_bytes: int
    path: Path


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, content: bytes, media_type: str) -> StoredArtifact:
        digest = hashlib.sha256(content).hexdigest()
        destination = self._path_for_digest(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            descriptor, temporary = tempfile.mkstemp(dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
                _fsync_directory_chain(destination.parent, self.root.resolve())
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return StoredArtifact(digest, media_type, len(content), destination)

    def open(self, digest: str) -> bytes:
        return self._path_for_digest(digest).read_bytes()

    def _path_for_digest(self, digest: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("artifact digest must be exactly 64 lowercase hexadecimal characters")
        root = self.root.resolve()
        destination = (root / digest[:2] / digest[2:4] / digest).resolve()
        if not destination.is_relative_to(root):
            raise ValueError("artifact path resolves outside artifact root")
        return destination


def _fsync_directory(directory: Path) -> None:
    if not _DIRECTORY_FSYNC_SUPPORTED:
        return
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory_chain(directory: Path, root: Path) -> None:
    current = directory.resolve()
    boundary = root.resolve()
    if not current.is_relative_to(boundary):
        raise ValueError("artifact directory resolves outside artifact root")
    while True:
        _fsync_directory(current)
        if current == boundary:
            return
        current = current.parent
