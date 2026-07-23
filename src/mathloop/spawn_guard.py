"""Synchronous child-process registration for local solver plugins.

Local Python methods may spawn helpers only through ``subprocess.Popen`` (including
``subprocess.run``). The registry records each child before Popen returns, cleans
live children before the execution root exits, and rejects spawn paths that cannot
be registered safely. Native helpers that daemonize must run in a container.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from threading import Condition, Event, Lock, RLock, local
from typing import Any, cast


class UnsupportedProcessSpawn(RuntimeError):
    """Raised when method code bypasses the supervised Popen boundary."""


_REAP_SLICE_SECONDS = 0.05


@dataclass
class _SpawnRecord:
    process: subprocess.Popen[Any]
    process_group_id: int
    owns_process_group: bool
    lifecycle_lock: AbstractContextManager[bool]
    cleanup_requested: Event
    cleanup_finished: Event
    activity_condition: Condition
    active_calls: int
    thread_state: local
    poll: Callable[[], int | None]
    wait: Callable[..., int]
    communicate: Callable[..., tuple[Any, Any]]


class SupervisedSpawnRegistry:
    """Interpose and synchronously register supported Python child processes."""

    def __init__(
        self,
        channel: Connection,
        supervisor_channel: Connection | None,
    ) -> None:
        self._channel = channel
        self._supervisor_channel = supervisor_channel
        self._records: dict[int, _SpawnRecord] = {}
        self._records_lock = Lock()
        self._spawn_state = local()
        self._original_popen = subprocess.Popen
        self._popen_signature = signature(self._original_popen)
        self._original_exit = os._exit
        self._original_process_start = BaseProcess.start
        self._original_fork = getattr(os, "fork", None)
        self._original_forkpty = getattr(os, "forkpty", None)
        self._original_posix_spawn = getattr(os, "posix_spawn", None)
        self._original_posix_spawnp = getattr(os, "posix_spawnp", None)
        self._original_system = os.system

    @contextmanager
    def installed(self) -> Iterator[None]:
        self._install()
        try:
            yield
        finally:
            try:
                self.cleanup()
            finally:
                self._restore()

    def cleanup(self) -> None:
        failures: list[str] = []
        with self._records_lock:
            records = tuple(reversed(self._records.values()))
        for record in records:
            record.cleanup_requested.set()
            try:
                with record.lifecycle_lock:
                    if not self._owns(record):
                        continue
                    try:
                        self._stop_record(record)
                    except (OSError, subprocess.SubprocessError) as error:
                        failures.append(f"pid {record.process.pid}: {error}")
                    finally:
                        self._retire(record)
            finally:
                record.cleanup_finished.set()
                self._wait_for_active_calls(record)
        if failures:
            raise RuntimeError("supervised child cleanup failed: " + "; ".join(failures))

    def _install(self) -> None:
        registry = self

        def supervised_popen(
            *popenargs: Any,
            **kwargs: Any,
        ) -> subprocess.Popen[Any]:
            bound_arguments = registry._popen_signature.bind(*popenargs, **kwargs)
            bound_arguments.apply_defaults()
            options = bound_arguments.arguments
            registry._validate_popen(options)
            previous_depth = getattr(registry._spawn_state, "depth", 0)
            registry._spawn_state.depth = previous_depth + 1
            try:
                process = registry._original_popen(*popenargs, **kwargs)
            finally:
                registry._spawn_state.depth = previous_depth
            registry._register(process, options)
            return process

        def supervised_exit(status: int) -> None:
            try:
                registry.cleanup()
            finally:
                registry._original_exit(status)

        def blocked_process_start(process: BaseProcess) -> None:
            del process
            raise UnsupportedProcessSpawn(
                "multiprocessing is unavailable inside local method execution; "
                "use supervised subprocess.Popen or DockerRunner"
            )

        subprocess.Popen = cast(Any, supervised_popen)  # type: ignore[misc]
        os._exit = supervised_exit  # type: ignore[assignment]
        BaseProcess.start = blocked_process_start  # type: ignore[method-assign, assignment]
        if self._original_fork is not None:
            os.fork = cast(Any, self._guarded_raw_spawn("os.fork", self._original_fork))
        if self._original_forkpty is not None:
            os.forkpty = cast(
                Any,
                self._guarded_raw_spawn("os.forkpty", self._original_forkpty),
            )
        if self._original_posix_spawn is not None:
            os.posix_spawn = cast(
                Any,
                self._guarded_raw_spawn("os.posix_spawn", self._original_posix_spawn),
            )
        if self._original_posix_spawnp is not None:
            os.posix_spawnp = cast(
                Any,
                self._guarded_raw_spawn("os.posix_spawnp", self._original_posix_spawnp),
            )
        os.system = cast(
            Any,
            self._guarded_raw_spawn("os.system", self._original_system),
        )
        sys.addaudithook(self._audit_spawn)

    def _restore(self) -> None:
        subprocess.Popen = self._original_popen  # type: ignore[misc]
        os._exit = self._original_exit
        BaseProcess.start = self._original_process_start  # type: ignore[method-assign]
        if self._original_fork is not None:
            os.fork = self._original_fork
        if self._original_forkpty is not None:
            os.forkpty = self._original_forkpty
        if self._original_posix_spawn is not None:
            os.posix_spawn = self._original_posix_spawn
        if self._original_posix_spawnp is not None:
            os.posix_spawnp = self._original_posix_spawnp
        os.system = self._original_system

    def _guarded_raw_spawn(self, name: str, function: Any) -> Any:
        def guarded(*args: Any, **kwargs: Any) -> Any:
            if getattr(self._spawn_state, "depth", 0) > 0:
                return function(*args, **kwargs)
            raise UnsupportedProcessSpawn(
                f"{name} is unavailable inside local method execution; "
                "use supervised subprocess.Popen or DockerRunner"
            )

        return guarded

    def _audit_spawn(self, event: str, args: tuple[object, ...]) -> None:
        del args
        if (
            event
            in {
                "subprocess.Popen",
                "os.exec",
                "os.fork",
                "os.forkpty",
                "os.posix_spawn",
                "os.spawn",
                "os.system",
            }
            and getattr(self._spawn_state, "depth", 0) == 0
        ):
            raise UnsupportedProcessSpawn(f"{event} bypassed the supervised local process boundary")

    @staticmethod
    def _validate_popen(options: Mapping[str, Any]) -> None:
        if options.get("shell"):
            raise UnsupportedProcessSpawn(
                "shell=True is unavailable inside local method execution; use an argument vector"
            )
        if options.get("preexec_fn") is not None:
            raise UnsupportedProcessSpawn("preexec_fn is unavailable inside local method execution")
        process_group = options.get("process_group")
        if process_group not in {None, -1, 0}:
            raise UnsupportedProcessSpawn(
                "joining an existing process group is unavailable inside local method execution"
            )

    def _register(
        self,
        process: subprocess.Popen[Any],
        options: Mapping[str, Any],
    ) -> None:
        try:
            process_group_id = os.getpgid(process.pid)
        except ProcessLookupError:
            process.poll()
            return
        owns_process_group = bool(options.get("start_new_session")) or (
            options.get("process_group") == 0
        )
        record = _SpawnRecord(
            process=process,
            process_group_id=process_group_id,
            owns_process_group=owns_process_group,
            lifecycle_lock=RLock(),
            cleanup_requested=Event(),
            cleanup_finished=Event(),
            activity_condition=Condition(),
            active_calls=0,
            thread_state=local(),
            poll=process.poll,
            wait=process.wait,
            communicate=process.communicate,
        )
        self._wrap_reap_methods(record)
        with self._records_lock:
            previous = self._records.pop(process.pid, None)
            if previous is not None and previous.process is not process:
                self._notify_stopped(process.pid, previous.process_group_id)
            self._records[process.pid] = record
        payload = {
            "pid": process.pid,
            "process_group_id": process_group_id,
        }
        try:
            self._channel.send(("descendant_started", payload))
            if self._supervisor_channel is not None:
                self._supervisor_channel.send(("execution_descendant_started", payload))
        except OSError:
            self.cleanup()
            raise

    def _wrap_reap_methods(self, record: _SpawnRecord) -> None:
        process = record.process
        process.wait = cast(  # type: ignore[method-assign]
            Any, self._sliced_wait(record)
        )
        process.communicate = cast(  # type: ignore[method-assign]
            Any,
            self._sliced_communicate(record),
        )
        process.poll = cast(  # type: ignore[method-assign]
            Any, self._retiring_call(record, process.poll)
        )

    def _sliced_wait(self, record: _SpawnRecord) -> Callable[..., int]:
        @wraps(record.wait)
        def wrapped(timeout: float | None = None) -> int:
            if getattr(record.thread_state, "inside_communicate", False):
                result = record.wait(timeout=timeout)
                if record.process.returncode is not None:
                    self._retire(record)
                return result
            self._begin_call(record)
            try:
                deadline = None if timeout is None else time.monotonic() + timeout
                last_timeout: subprocess.TimeoutExpired | None = None
                while True:
                    if not self._wait_for_cleanup(record, deadline):
                        assert timeout is not None
                        raise self._timeout_expired(record, timeout, last_timeout) from None
                    slice_timeout = self._slice_timeout(deadline)
                    try:
                        with record.lifecycle_lock:
                            result = record.wait(timeout=slice_timeout)
                            if record.process.returncode is not None:
                                self._retire(record)
                            return result
                    except subprocess.TimeoutExpired as error:
                        last_timeout = error
                        if deadline is not None and time.monotonic() >= deadline:
                            assert timeout is not None
                            raise self._timeout_expired(record, timeout, error) from None
            finally:
                self._end_call(record)

        return wrapped

    def _sliced_communicate(self, record: _SpawnRecord) -> Callable[..., tuple[Any, Any]]:
        @wraps(record.communicate)
        def wrapped(
            input: Any = None,
            timeout: float | None = None,
        ) -> tuple[Any, Any]:
            self._begin_call(record)
            try:
                deadline = None if timeout is None else time.monotonic() + timeout
                pending_input = input
                last_timeout: subprocess.TimeoutExpired | None = None
                while True:
                    if not self._wait_for_cleanup(record, deadline):
                        assert timeout is not None
                        raise self._timeout_expired(record, timeout, last_timeout) from None
                    slice_timeout = self._slice_timeout(deadline)
                    try:
                        with record.lifecycle_lock:
                            previous_state = getattr(
                                record.thread_state,
                                "inside_communicate",
                                False,
                            )
                            record.thread_state.inside_communicate = True
                            try:
                                result = record.communicate(
                                    input=pending_input,
                                    timeout=slice_timeout,
                                )
                            finally:
                                record.thread_state.inside_communicate = previous_state
                            if record.process.returncode is not None:
                                self._retire(record)
                            return result
                    except subprocess.TimeoutExpired as error:
                        last_timeout = error
                        pending_input = None
                        if deadline is not None and time.monotonic() >= deadline:
                            assert timeout is not None
                            raise self._timeout_expired(record, timeout, error) from None
            finally:
                self._end_call(record)

        return wrapped

    @staticmethod
    def _wait_for_cleanup(
        record: _SpawnRecord,
        deadline: float | None,
    ) -> bool:
        if not record.cleanup_requested.is_set():
            return True
        if deadline is None:
            record.cleanup_finished.wait()
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        return record.cleanup_finished.wait(timeout=remaining) and time.monotonic() < deadline

    @staticmethod
    def _begin_call(record: _SpawnRecord) -> None:
        with record.activity_condition:
            record.active_calls += 1

    @staticmethod
    def _end_call(record: _SpawnRecord) -> None:
        with record.activity_condition:
            record.active_calls -= 1
            record.activity_condition.notify_all()

    @staticmethod
    def _wait_for_active_calls(record: _SpawnRecord) -> None:
        deadline = time.monotonic() + 1
        with record.activity_condition:
            while record.active_calls:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        f"supervised child reap did not finish for pid {record.process.pid}"
                    )
                record.activity_condition.wait(timeout=remaining)

    @staticmethod
    def _slice_timeout(deadline: float | None) -> float:
        if deadline is None:
            return _REAP_SLICE_SECONDS
        return max(0.0, min(_REAP_SLICE_SECONDS, deadline - time.monotonic()))

    @staticmethod
    def _timeout_expired(
        record: _SpawnRecord,
        timeout: float,
        error: subprocess.TimeoutExpired | None,
    ) -> subprocess.TimeoutExpired:
        return subprocess.TimeoutExpired(
            record.process.args,
            timeout,
            output=None if error is None else error.output,
            stderr=None if error is None else error.stderr,
        )

    def _retiring_call(
        self,
        record: _SpawnRecord,
        operation: Callable[..., Any],
    ) -> Callable[..., Any]:
        @wraps(operation)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self._begin_call(record)
            try:
                with record.lifecycle_lock:
                    result = operation(*args, **kwargs)
                    if record.process.returncode is not None:
                        self._retire(record)
                    return result
            finally:
                self._end_call(record)

        return wrapped

    def _owns(self, record: _SpawnRecord) -> bool:
        with self._records_lock:
            return self._records.get(record.process.pid) is record

    def _retire(self, record: _SpawnRecord) -> None:
        process = record.process
        with self._records_lock:
            if self._records.get(process.pid) is not record:
                return
            self._records.pop(process.pid)
            self._notify_stopped(process.pid, record.process_group_id)

    def _stop_record(self, record: _SpawnRecord) -> None:
        process = record.process
        running = record.poll() is None
        if not running:
            return
        current_group = os.getpgid(process.pid)
        root_group = os.getpgrp()
        owns_group = record.owns_process_group or current_group != root_group
        if current_group != record.process_group_id:
            record.process_group_id = current_group
            self._notify_group_changed(process.pid, current_group)
        if owns_group:
            self._signal_group(current_group, signal.SIGTERM)
            time.sleep(0.05)
            self._signal_group(current_group, signal.SIGKILL)
        else:
            process.terminate()
        try:
            record.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            process.kill()
            record.wait(timeout=0.25)

    def _notify_group_changed(self, pid: int, process_group_id: int) -> None:
        payload = {"pid": pid, "process_group_id": process_group_id}
        self._channel.send(("descendant_started", payload))
        if self._supervisor_channel is not None:
            self._supervisor_channel.send(("execution_descendant_started", payload))

    def _notify_stopped(self, pid: int, process_group_id: int) -> None:
        payload = {"pid": pid, "process_group_id": process_group_id}
        try:
            self._channel.send(("descendant_stopped", payload))
            if self._supervisor_channel is not None:
                self._supervisor_channel.send(("execution_descendant_stopped", payload))
        except OSError:
            pass

    @staticmethod
    def _signal_group(process_group_id: int, signal_number: int) -> None:
        try:
            os.killpg(process_group_id, signal_number)
        except (PermissionError, ProcessLookupError):
            pass
