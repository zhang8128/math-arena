"""Disposable, detached Git worktrees for supervised Codex agent turns.

Every worktree is a fresh, detached checkout of a recorded base commit,
scoped to a single turn, and destroyed when the turn is done. All Git
operations run as explicit argument vectors with `shell=False` -- never a
shell string -- and every `CodexWorktree` the manager is handed back (in
`diff` and `remove`) has its `path` and `base_sha` re-validated and
re-resolved before use, never trusted as-is, since the value may have
crossed a process or storage boundary since it was created. Every
subsequent Git call operates on that freshly resolved path, not on the
possibly-relative or possibly-tampered field the caller supplied.
"""

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

_BASE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_DEFAULT_MAX_PATCH_BYTES = 4 * 1024 * 1024


class CodexWorktreeError(RuntimeError):
    """A disposable Codex worktree operation violated its safety contract."""


@dataclass(frozen=True)
class CodexWorktree:
    """A single detached worktree checked out for one Codex turn."""

    turn_id: UUID
    path: Path
    base_sha: str


@dataclass(frozen=True)
class CodexWorktreePatch:
    """The captured diff of a worktree against its recorded base commit."""

    content: bytes
    sha256: str


class CodexWorktreeManager:
    """Creates, diffs, and removes disposable worktrees under one root."""

    def __init__(
        self,
        repo_root: Path,
        worktree_root: Path,
        *,
        max_patch_bytes: int = _DEFAULT_MAX_PATCH_BYTES,
    ) -> None:
        if max_patch_bytes < 1:
            raise ValueError("max_patch_bytes must be a positive integer")
        self.repo_root = repo_root.resolve()
        self.worktree_root = worktree_root.resolve()
        self.max_patch_bytes = max_patch_bytes
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    def create(
        self, turn_id: UUID, base_sha: str, *, timeout: float | None = None
    ) -> CodexWorktree:
        if not isinstance(turn_id, UUID):
            raise CodexWorktreeError("turn_id must be a uuid.UUID instance")
        _validate_base_sha(base_sha)
        path = self._validate_managed_path(self.worktree_root / str(turn_id), turn_id)
        self._run(("git", "worktree", "add", "--detach", str(path), base_sha), timeout=timeout)
        worktree = CodexWorktree(turn_id=turn_id, path=path, base_sha=base_sha)
        should_cleanup = True
        try:
            # A freshly checked-out worktree must be byte-identical to
            # base_sha. It never legitimately isn't, but a dirty initial
            # checkout (e.g. a content filter mutating files on checkout)
            # must never be handed back to a caller as though it were a
            # clean starting point. Cleanup also has to run if this check
            # itself fails transiently -- an orphaned worktree left behind
            # by a raised exception is exactly the kind of leak this class
            # exists to prevent.
            initial_diff = self._capture_patch_bytes(path, base_sha, timeout=timeout)
            if initial_diff:
                raise CodexWorktreeError(
                    f"newly created worktree for turn {turn_id} is not clean relative to "
                    f"base_sha {base_sha}"
                )
            should_cleanup = False
            return worktree
        finally:
            if should_cleanup:
                self._force_remove(path, base_sha, timeout=timeout)

    def diff(
        self, worktree: CodexWorktree, *, timeout: float | None = None
    ) -> CodexWorktreePatch:
        # Re-validate and re-resolve on every call: `worktree` may have
        # crossed a process or storage boundary since `create` returned it,
        # and every subsequent git call below must operate on exactly the
        # path and base_sha that were just validated -- never the raw,
        # possibly-relative or possibly-tampered fields on the input value.
        path = self._validate_managed_path(worktree.path, worktree.turn_id)
        _validate_base_sha(worktree.base_sha)
        content = self._capture_patch_bytes(path, worktree.base_sha, timeout=timeout)
        if len(content) > self.max_patch_bytes:
            raise CodexWorktreeError(
                f"worktree patch of {len(content)} bytes exceeds max_patch_bytes cap of "
                f"{self.max_patch_bytes}"
            )
        return CodexWorktreePatch(content=content, sha256=hashlib.sha256(content).hexdigest())

    def remove(self, worktree: CodexWorktree, *, timeout: float | None = None) -> None:
        path = self._validate_managed_path(worktree.path, worktree.turn_id)
        _validate_base_sha(worktree.base_sha)
        # Discard any turn-local edits so the plain `git worktree remove`
        # below (no `--force`) succeeds instead of refusing on a dirty tree.
        self._run(("git", "-C", str(path), "reset", "--hard", worktree.base_sha), timeout=timeout)
        self._run(("git", "-C", str(path), "clean", "-fdx"), timeout=timeout)
        self._run(("git", "worktree", "remove", str(path)), timeout=timeout)
        if path.exists():
            raise CodexWorktreeError(f"worktree directory still exists after removal: {path}")
        self._run(("git", "worktree", "prune"), timeout=timeout)

    def _force_remove(self, path: Path, base_sha: str, *, timeout: float | None = None) -> None:
        # Best-effort cleanup for a worktree this manager is rejecting; unlike
        # `remove`, this may discard a checkout that reset/clean cannot make
        # byte-identical to base_sha (e.g. the dirty-initial-checkout case),
        # so it uses `--force` rather than the plain `remove` argv.
        self._run(("git", "-C", str(path), "reset", "--hard", base_sha), timeout=timeout)
        self._run(("git", "-C", str(path), "clean", "-fdx"), timeout=timeout)
        self._run(("git", "worktree", "remove", "--force", str(path)), timeout=timeout)
        self._run(("git", "worktree", "prune"), timeout=timeout)

    def _capture_patch_bytes(
        self, path: Path, base_sha: str, *, timeout: float | None = None
    ) -> bytes:
        # `git diff <base_sha>` only reports paths already tracked in the
        # index -- a file the agent newly created is invisible to it until
        # staged. Stage everything in the worktree's own index first so new
        # files appear in the patch alongside edits to existing ones. This
        # only touches the worktree's private index, never the source
        # checkout's.
        self._run(("git", "-C", str(path), "add", "-A"), timeout=timeout)
        completed = self._run(
            (
                "git",
                "-C",
                str(path),
                "diff",
                "--binary",
                "--no-ext-diff",
                base_sha,
            ),
            timeout=timeout,
        )
        return completed.stdout

    def _validate_managed_path(self, path: Path, turn_id: UUID) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.worktree_root):
            raise CodexWorktreeError(
                f"worktree path {resolved} resolves outside the configured worktree root "
                f"{self.worktree_root}"
            )
        try:
            directory_uuid = UUID(resolved.name)
        except ValueError as error:
            raise CodexWorktreeError(
                f"worktree directory name {resolved.name!r} is not a UUID"
            ) from error
        if directory_uuid != turn_id:
            raise CodexWorktreeError(
                f"worktree directory name {resolved.name!r} does not match turn_id {turn_id}"
            )
        return resolved

    def _run(
        self, argv: tuple[str, ...], *, timeout: float | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            completed = subprocess.run(
                argv,
                cwd=self.repo_root,
                capture_output=True,
                check=False,
                shell=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise CodexWorktreeError(
                f"git command {' '.join(argv)!r} exceeded its {timeout}s timeout"
            ) from error
        if completed.returncode != 0:
            stderr = completed.stderr.decode(errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise CodexWorktreeError(
                f"git command {' '.join(argv)!r} exited with code {completed.returncode}{detail}"
            )
        return completed


def _validate_base_sha(base_sha: str) -> None:
    if not isinstance(base_sha, str) or _BASE_SHA_PATTERN.fullmatch(base_sha) is None:
        raise CodexWorktreeError("base_sha must be exactly 40 lowercase hexadecimal characters")
