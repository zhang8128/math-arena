"""Bounded cleanup for supervised process trees."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Iterable
from multiprocessing.process import BaseProcess


def terminate_process_tree(
    process: BaseProcess,
    *,
    known_process_groups: Iterable[int] = (),
    terminate_timeout: float = 0.5,
    kill_timeout: float = 0.5,
) -> None:
    """Terminate a process and every synchronously registered process group."""
    root_pid = process.pid
    if root_pid is None:
        process.join(timeout=terminate_timeout)
        return
    groups = set(known_process_groups)
    targets = (*_process_group_members(groups), root_pid)
    own_group = os.getpgrp() if hasattr(os, "getpgrp") else None
    if hasattr(os, "getpgid"):
        for pid in targets:
            try:
                group = os.getpgid(pid)
            except ProcessLookupError:
                continue
            if group > 1 and group != own_group:
                groups.add(group)

    _signal_groups(groups, signal.SIGTERM)
    _signal_processes(targets, signal.SIGTERM)
    process.join(timeout=terminate_timeout)
    if _any_running(targets):
        _signal_groups(groups, signal.SIGKILL)
        _signal_processes(targets, signal.SIGKILL)
        process.join(timeout=kill_timeout)
    deadline = time.monotonic() + kill_timeout
    while _any_running(targets) and time.monotonic() < deadline:
        time.sleep(0.01)
    if process.is_alive() or _any_running(targets):
        raise RuntimeError("supervised process tree could not be terminated")


def _process_group_members(groups: set[int]) -> tuple[int, ...]:
    if not groups:
        return ()
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,pgid="],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    members: list[int] = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            pid, group = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        if group in groups:
            members.append(pid)
    return tuple(members)


def _signal_groups(groups: Iterable[int], signal_number: int) -> None:
    if not hasattr(os, "killpg"):
        return
    for group in groups:
        try:
            os.killpg(group, signal_number)
        except (PermissionError, ProcessLookupError):
            pass


def _signal_processes(pids: Iterable[int], signal_number: int) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal_number)
        except ProcessLookupError:
            pass


def _any_running(pids: Iterable[int]) -> bool:
    return any(_pid_is_running(pid) for pid in pids)


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
