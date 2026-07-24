"""Real-Git tests for the disposable Codex worktree lifecycle.

No subprocess mocking: every test drives an actual `git` binary against a
throwaway repository under `tmp_path`.
"""

import hashlib
import subprocess
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
