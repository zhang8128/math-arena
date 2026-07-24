"""Real-Git tests for the disposable Codex worktree lifecycle.

No subprocess mocking: every test drives an actual `git` binary against a
throwaway repository under `tmp_path`.
"""

import hashlib
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from mathloop.codex.worktrees import CodexWorktree, CodexWorktreeError, CodexWorktreeManager


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-worktrees-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Worktrees Test", cwd=repo)
    (repo / "problem.txt").write_text("seed content\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


def test_create_edit_diff_remove_and_prune_real_git_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    manager = CodexWorktreeManager(repo_root=repo, worktree_root=tmp_path / "worktrees")
    turn_id = uuid4()

    worktree = manager.create(turn_id, base_sha)

    assert worktree.path.is_dir()
    assert worktree.path.name == str(turn_id)
    assert worktree.base_sha == base_sha
    assert (worktree.path / "problem.txt").read_text() == "seed content\n"

    (worktree.path / "problem.txt").write_text("seed content\nsolved\n")
    (worktree.path / "new_evidence.txt").write_text("counterexample: 42\n")

    # Edits inside the disposable worktree must never leak into the source
    # checkout the worktree was created from.
    assert (repo / "problem.txt").read_text() == "seed content\n"
    assert not (repo / "new_evidence.txt").exists()

    patch = manager.diff(worktree)
    assert patch.content
    assert patch.sha256 == hashlib.sha256(patch.content).hexdigest()
    assert b"solved" in patch.content
    assert b"new_evidence.txt" in patch.content

    manager.remove(worktree)

    assert not worktree.path.exists()
    listing_after_remove = _git("worktree", "list", cwd=repo).stdout
    assert str(worktree.path) not in listing_after_remove

    # The brief's required flow ends with an explicit prune; this must be a
    # harmless no-op since `remove` already pruned internally.
    _git("worktree", "prune", cwd=repo)


def test_create_rejects_malformed_base_sha(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = CodexWorktreeManager(repo_root=repo, worktree_root=tmp_path / "worktrees")

    with pytest.raises(CodexWorktreeError, match="40"):
        manager.create(uuid4(), "not-a-valid-sha")


def test_create_rejects_dirty_initial_worktree_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-worktrees-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Worktrees Test", cwd=repo)
    (repo / ".gitattributes").write_text("dirty.txt filter=dirty\n")
    (repo / "dirty.txt").write_text("original\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)
    base_sha = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    # A smudge filter with no matching clean filter mutates the working-tree
    # copy on checkout without ever touching the committed blob, so a fresh
    # `git worktree add` genuinely disagrees with base_sha -- a real,
    # deterministic way to produce a dirty initial checkout without mocking
    # any subprocess call.
    _git("config", "filter.dirty.smudge", "sed -e s/original/mutated/", cwd=repo)

    manager = CodexWorktreeManager(repo_root=repo, worktree_root=tmp_path / "worktrees")
    turn_id = uuid4()

    with pytest.raises(CodexWorktreeError, match="not clean"):
        manager.create(turn_id, base_sha)

    # The manager must clean up its own rejected worktree.
    assert not (tmp_path / "worktrees" / str(turn_id)).exists()
    listing = _git("worktree", "list", cwd=repo).stdout
    assert str(turn_id) not in listing


def test_diff_rejects_patch_exceeding_max_patch_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    manager = CodexWorktreeManager(
        repo_root=repo,
        worktree_root=tmp_path / "worktrees",
        max_patch_bytes=64,
    )
    worktree = manager.create(uuid4(), base_sha)

    (worktree.path / "problem.txt").write_text("x" * 4096)

    with pytest.raises(CodexWorktreeError, match="max_patch_bytes"):
        manager.diff(worktree)


def test_remove_rejects_non_uuid_directory_name(tmp_path: Path) -> None:
    manager = CodexWorktreeManager(
        repo_root=tmp_path / "repo", worktree_root=tmp_path / "worktrees"
    )
    bogus = CodexWorktree(
        turn_id=uuid4(),
        path=manager.worktree_root / "not-a-uuid",
        base_sha="a" * 40,
    )

    with pytest.raises(CodexWorktreeError, match="UUID"):
        manager.remove(bogus)


def test_remove_rejects_path_escaping_the_worktree_root(tmp_path: Path) -> None:
    manager = CodexWorktreeManager(
        repo_root=tmp_path / "repo", worktree_root=tmp_path / "worktrees"
    )
    turn_id = uuid4()
    escaping = CodexWorktree(
        turn_id=turn_id,
        path=tmp_path / "elsewhere" / str(turn_id),
        base_sha="a" * 40,
    )

    with pytest.raises(CodexWorktreeError, match="outside"):
        manager.remove(escaping)


def test_remove_rejects_symlink_planted_inside_root_that_escapes_it(tmp_path: Path) -> None:
    # A path can be textually "inside" worktree_root and still point
    # somewhere else entirely once symlinks resolve. Validation and every
    # subsequent git call must agree on the *resolved* destination, not the
    # raw path text, or a symlink could smuggle a git command outside the
    # sandboxed root.
    manager = CodexWorktreeManager(
        repo_root=tmp_path / "repo", worktree_root=tmp_path / "worktrees"
    )
    turn_id = uuid4()
    outside_target = tmp_path / "outside-target"
    outside_target.mkdir()
    symlinked_path = manager.worktree_root / str(turn_id)
    symlinked_path.symlink_to(outside_target, target_is_directory=True)
    escaping = CodexWorktree(turn_id=turn_id, path=symlinked_path, base_sha="a" * 40)

    with pytest.raises(CodexWorktreeError, match="outside"):
        manager.remove(escaping)


def test_diff_resolves_a_relative_worktree_path_before_running_git(tmp_path: Path) -> None:
    # `_run` executes git with `cwd=repo_root`, so a *relative* path handed
    # to `-C` would be interpreted by git relative to repo_root -- a
    # different location than what `Path.resolve()` (relative to the
    # process cwd) validates. Using the manager on a worktree whose `path`
    # is relative proves validation and execution now agree on one
    # location regardless of representation.
    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    manager = CodexWorktreeManager(repo_root=repo, worktree_root=tmp_path / "worktrees")
    turn_id = uuid4()
    worktree = manager.create(turn_id, base_sha)

    relative_path = Path(os.path.relpath(worktree.path, Path.cwd()))
    assert not relative_path.is_absolute()
    relative_worktree = CodexWorktree(turn_id=turn_id, path=relative_path, base_sha=base_sha)

    patch = manager.diff(relative_worktree)

    assert patch.content == b""

    manager.remove(relative_worktree)
    assert not worktree.path.exists()


def test_diff_rejects_flag_shaped_base_sha_before_running_git(tmp_path: Path) -> None:
    manager = CodexWorktreeManager(
        repo_root=tmp_path / "repo", worktree_root=tmp_path / "worktrees"
    )
    turn_id = uuid4()
    tampered = CodexWorktree(
        turn_id=turn_id,
        path=manager.worktree_root / str(turn_id),
        base_sha="--exec=echo pwned",
    )

    with pytest.raises(CodexWorktreeError, match="40"):
        manager.diff(tampered)


def test_remove_rejects_flag_shaped_base_sha_before_running_git(tmp_path: Path) -> None:
    manager = CodexWorktreeManager(
        repo_root=tmp_path / "repo", worktree_root=tmp_path / "worktrees"
    )
    turn_id = uuid4()
    tampered = CodexWorktree(
        turn_id=turn_id,
        path=manager.worktree_root / str(turn_id),
        base_sha="--exec=echo pwned",
    )

    with pytest.raises(CodexWorktreeError, match="40"):
        manager.remove(tampered)


def test_run_converts_a_subprocess_timeout_into_a_worktree_error(tmp_path: Path) -> None:
    # `_run` is the single choke point `create`/`diff`/`remove` all funnel
    # through; exercising it directly (rather than contriving a genuinely
    # slow git invocation) proves the `timeout=` parameter is actually
    # enforced by `subprocess.run`, not merely accepted and ignored, without
    # depending on git's own timing.
    manager = CodexWorktreeManager(repo_root=tmp_path, worktree_root=tmp_path / "worktrees")

    started = time.monotonic()
    with pytest.raises(CodexWorktreeError, match="timeout"):
        manager._run(("sleep", "2"), timeout=0.2)
    elapsed = time.monotonic() - started

    assert elapsed < 1.5


def test_create_removes_worktree_when_the_clean_check_raises_transiently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    base_sha = _init_repo(repo)
    manager = CodexWorktreeManager(repo_root=repo, worktree_root=tmp_path / "worktrees")
    turn_id = uuid4()

    def _boom(
        self: CodexWorktreeManager, path: Path, base_sha: str, *, timeout: float | None = None
    ) -> bytes:
        del timeout
        raise RuntimeError("transient failure reading the diff")

    monkeypatch.setattr(CodexWorktreeManager, "_capture_patch_bytes", _boom)

    with pytest.raises(RuntimeError, match="transient failure"):
        manager.create(turn_id, base_sha)

    # The just-created worktree must not be left behind by a raised
    # exception -- only the caller-visible failure mode (dirty checkout)
    # was cleaning up before this fix.
    assert not (tmp_path / "worktrees" / str(turn_id)).exists()
    listing = _git("worktree", "list", cwd=repo).stdout
    assert str(turn_id) not in listing
