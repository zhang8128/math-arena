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
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

_BASE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_DEFAULT_MAX_PATCH_BYTES = 4 * 1024 * 1024
_DEFAULT_CLEANUP_TIMEOUT_SECONDS = 60.0


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
        cleanup_timeout_seconds: float = _DEFAULT_CLEANUP_TIMEOUT_SECONDS,
    ) -> None:
        if max_patch_bytes < 1:
            raise ValueError("max_patch_bytes must be a positive integer")
        if cleanup_timeout_seconds <= 0:
            raise ValueError("cleanup_timeout_seconds must be positive")
        self.repo_root = repo_root.resolve()
        self.worktree_root = worktree_root.resolve()
        self.max_patch_bytes = max_patch_bytes
        self._cleanup_timeout_seconds = cleanup_timeout_seconds
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    def create(
        self, turn_id: UUID, base_sha: str, *, deadline: float | None = None
    ) -> CodexWorktree:
        if not isinstance(turn_id, UUID):
            raise CodexWorktreeError("turn_id must be a uuid.UUID instance")
        _validate_base_sha(base_sha)
        path = self._validate_managed_path(self.worktree_root / str(turn_id), turn_id)
        self._run(("git", "worktree", "add", "--detach", str(path), base_sha), deadline=deadline)
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
            initial_diff = self._capture_patch_bytes(path, base_sha, deadline=deadline)
            if initial_diff:
                raise CodexWorktreeError(
                    f"newly created worktree for turn {turn_id} is not clean relative to "
                    f"base_sha {base_sha}"
                )
            should_cleanup = False
            return worktree
        finally:
            if should_cleanup:
                # A fresh budget of its own, not `deadline` (the caller's
                # own budget for `create` itself): this runs only once
                # `create` has already decided to abandon the worktree it
                # just made, so it is reclamation, not a stage of `create`'s
                # own active work -- the same reasoning `CodexClient`'s own
                # post-turn `remove()` already applies. Reusing `deadline`
                # here would mean a caller whose budget happened to run out
                # during the dirty-checkout check gets every subsequent git
                # command here timed out instantly, leaking this worktree
                # and replacing whatever exception was already in flight
                # (raised from a `finally`) with a cleanup-timeout error.
                cleanup_deadline = time.monotonic() + self._cleanup_timeout_seconds
                self._force_remove(path, base_sha, deadline=cleanup_deadline)

    def diff(
        self, worktree: CodexWorktree, *, deadline: float | None = None
    ) -> CodexWorktreePatch:
        # Re-validate and re-resolve on every call: `worktree` may have
        # crossed a process or storage boundary since `create` returned it,
        # and every subsequent git call below must operate on exactly the
        # path and base_sha that were just validated -- never the raw,
        # possibly-relative or possibly-tampered fields on the input value.
        path = self._validate_managed_path(worktree.path, worktree.turn_id)
        _validate_base_sha(worktree.base_sha)
        content = self._capture_patch_bytes(path, worktree.base_sha, deadline=deadline)
        if len(content) > self.max_patch_bytes:
            raise CodexWorktreeError(
                f"worktree patch of {len(content)} bytes exceeds max_patch_bytes cap of "
                f"{self.max_patch_bytes}"
            )
        return CodexWorktreePatch(content=content, sha256=hashlib.sha256(content).hexdigest())

    def remove(self, worktree: CodexWorktree, *, deadline: float | None = None) -> None:
        path = self._validate_managed_path(worktree.path, worktree.turn_id)
        _validate_base_sha(worktree.base_sha)
        # Discard any turn-local edits so the plain `git worktree remove`
        # below (no `--force`) succeeds instead of refusing on a dirty tree.
        self._run(
            ("git", "-C", str(path), "reset", "--hard", worktree.base_sha), deadline=deadline
        )
        self._run(("git", "-C", str(path), "clean", "-fdx"), deadline=deadline)
        self._run(("git", "worktree", "remove", str(path)), deadline=deadline)
        if path.exists():
            raise CodexWorktreeError(f"worktree directory still exists after removal: {path}")
        self._run(("git", "worktree", "prune"), deadline=deadline)

    def _force_remove(self, path: Path, base_sha: str, *, deadline: float | None = None) -> None:
        # Best-effort cleanup for a worktree this manager is rejecting; unlike
        # `remove`, this may discard a checkout that reset/clean cannot make
        # byte-identical to base_sha (e.g. the dirty-initial-checkout case),
        # so it uses `--force` rather than the plain `remove` argv.
        self._run(("git", "-C", str(path), "reset", "--hard", base_sha), deadline=deadline)
        self._run(("git", "-C", str(path), "clean", "-fdx"), deadline=deadline)
        self._run(("git", "worktree", "remove", "--force", str(path)), deadline=deadline)
        self._run(("git", "worktree", "prune"), deadline=deadline)

    def _capture_patch_bytes(
        self, path: Path, base_sha: str, *, deadline: float | None = None
    ) -> bytes:
        # `git diff <base_sha>` only reports paths already tracked in the
        # index -- a file the agent newly created is invisible to it until
        # staged. Stage everything in the worktree's own index first so new
        # files appear in the patch alongside edits to existing ones. This
        # only touches the worktree's private index, never the source
        # checkout's.
        self._run(("git", "-C", str(path), "add", "-A"), deadline=deadline)
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
            deadline=deadline,
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
        self, argv: tuple[str, ...], *, deadline: float | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        # `deadline` is one absolute monotonic instant shared across every
        # `_run` call within a single `create`/`diff`/`remove` invocation
        # (including their `_capture_patch_bytes`/`_force_remove` helpers,
        # which each issue more than one git command) -- the remaining
        # budget is recomputed fresh immediately before *this* command, so a
        # multi-command call collectively spends at most `deadline`, not
        # `deadline` all over again per command.
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        try:
            completed = subprocess.run(
                argv,
                cwd=self.repo_root,
                capture_output=True,
                check=False,
                shell=False,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired as error:
            raise CodexWorktreeError(
                f"git command {' '.join(argv)!r} exceeded its remaining {remaining}s budget"
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
