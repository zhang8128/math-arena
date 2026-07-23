import multiprocessing
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from threading import Event, Thread
from typing import cast
from uuid import uuid4

import pytest

from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext, MethodResult, SolverMethod
from mathloop.processes import terminate_process_tree
from mathloop.spawn_guard import UnsupportedProcessSpawn
from mathloop.worker import ExecutionFailed, ExecutionTimedOut, ProcessExecutionBoundary

FORKSERVER_TEST_TIMEOUT_SECONDS = 3


def _problem() -> Problem:
    return Problem(
        id=uuid4(),
        source_id="test/process-boundary",
        source_uri="local://test/process-boundary",
        source_hash="f" * 64,
        statement="test",
        normalized_statement="test",
        domain="testing",
        features={},
        checker={"kind": "integer_predicate", "predicate_id": "sum_odds", "start": 0},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


class HangingMethod:
    family = "hanging"

    def run(self, context: MethodContext) -> MethodResult:
        while True:
            time.sleep(0.01)


class StartsThenFailsMethod:
    family = "external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        raise RuntimeError("provider transport failed")


class GatedExternalMethod:
    family = "gated-external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        committed = Path(str(context.config["committed_path"]))
        if not committed.exists():
            raise AssertionError("provider boundary crossed before durable dispatch commit")
        Path(str(context.config["provider_path"])).write_text("provider-called")
        return MethodResult(status="lead", summary="provider completed")


class InterruptMethod:
    family = "interrupt"

    def run(self, context: MethodContext) -> MethodResult:
        raise KeyboardInterrupt


class DescendantHangingMethod:
    family = "descendant-hanging"

    def run(self, context: MethodContext) -> MethodResult:
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
        )
        Path(str(context.config["pid_path"])).write_text(str(descendant.pid))
        while True:
            time.sleep(0.01)


class RootExitWithDescendantMethod:
    family = "root-exit-with-descendant"

    def run(self, context: MethodContext) -> MethodResult:
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
        )
        Path(str(context.config["pid_path"])).write_text(str(descendant.pid))
        os._exit(17)


class RootExitWithSeparateSessionDescendantMethod:
    family = "root-exit-with-separate-session-descendant"

    def run(self, context: MethodContext) -> MethodResult:
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        Path(str(context.config["pid_path"])).write_text(str(descendant.pid))
        os._exit(17)


class ReturnsWithSeparateSessionDescendantMethod:
    family = "returns-with-separate-session-descendant"

    def run(self, context: MethodContext) -> MethodResult:
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        Path(str(context.config["pid_path"])).write_text(str(descendant.pid))
        return MethodResult(status="lead", summary="spawned detached work")


class HangsWithSeparateSessionDescendantMethod:
    family = "hangs-with-separate-session-descendant"

    def run(self, context: MethodContext) -> MethodResult:
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        Path(str(context.config["pid_path"])).write_text(str(descendant.pid))
        while True:
            time.sleep(0.01)


class DirectForkMethod:
    family = "direct-fork"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child_pid = os.fork()
        if child_pid == 0:
            os._exit(0)
        os.waitpid(child_pid, 0)
        return MethodResult(status="lead", summary="raw fork escaped")


class DirectPosixSpawnMethod:
    family = "direct-posix-spawn"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child_pid = os.posix_spawn(
            sys.executable,
            [sys.executable, "-c", "pass"],
            os.environ,
        )
        os.waitpid(child_pid, 0)
        return MethodResult(status="lead", summary="raw posix_spawn escaped")


def _multiprocessing_child() -> None:
    return None


class DirectMultiprocessingMethod:
    family = "direct-multiprocessing"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = multiprocessing.get_context("spawn").Process(target=_multiprocessing_child)
        child.start()
        child.join()
        return MethodResult(status="lead", summary="multiprocessing escaped")


class DirectSystemMethod:
    family = "direct-system"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        os.system("true")
        return MethodResult(status="lead", summary="os.system escaped")


class CrossThreadSpawnBypassMethod:
    family = "cross-thread-spawn-bypass"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        popen_entered = Event()
        release_popen = Event()
        original_execute_child = UNSUPERVISED_POPEN_ALIAS._execute_child

        def coordinated_execute_child(*args: object, **kwargs: object) -> object:
            popen_entered.set()
            assert release_popen.wait(timeout=1)
            return original_execute_child(*args, **kwargs)

        UNSUPERVISED_POPEN_ALIAS._execute_child = coordinated_execute_child  # type: ignore[method-assign]
        child_holder: list[subprocess.Popen[bytes]] = []

        def legitimate_popen() -> None:
            child_holder.append(
                subprocess.Popen(
                    [sys.executable, "-c", "pass"],
                    stdout=subprocess.PIPE,
                )
            )

        thread = Thread(target=legitimate_popen)
        thread.start()
        assert popen_entered.wait(timeout=1)
        try:
            try:
                os.system("true")
            except UnsupportedProcessSpawn:
                pass
            else:
                raise AssertionError("another thread inherited Popen spawn authorization")
        finally:
            release_popen.set()
            thread.join(timeout=1)
            UNSUPERVISED_POPEN_ALIAS._execute_child = original_execute_child
        assert len(child_holder) == 1
        assert child_holder[0].wait(timeout=1) == 0
        return MethodResult(status="lead", summary="cross-thread spawn blocked")


UNSUPERVISED_POPEN_ALIAS = subprocess.Popen


class AliasedPopenMethod:
    family = "aliased-popen"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = UNSUPERVISED_POPEN_ALIAS([sys.executable, "-c", "pass"])
        child.wait()
        return MethodResult(status="lead", summary="Popen alias escaped")


class UnsafePopenModeMethod:
    family = "unsafe-popen-mode"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            preexec_fn=lambda: None,
        )
        child.wait()
        return MethodResult(status="lead", summary="preexec_fn escaped")


class PositionalPreexecPopenMethod:
    family = "positional-preexec-popen"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            -1,
            None,
            None,
            None,
            None,
            lambda: None,
        )
        child.wait()
        return MethodResult(status="lead", summary="positional preexec_fn escaped")


class PositionalShellPopenMethod:
    family = "positional-shell-popen"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = subprocess.Popen(
            "true",
            -1,
            None,
            None,
            None,
            None,
            None,
            True,
            True,
        )
        child.wait()
        return MethodResult(status="lead", summary="positional shell escaped")


class ReapsAndContinuesMethod:
    family = "reaps-and-continues"

    def __init__(self, reap_operation: str) -> None:
        self.reap_operation = reap_operation

    def run(self, context: MethodContext) -> MethodResult:
        child = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        if self.reap_operation == "wait":
            assert child.wait() == 0
        elif self.reap_operation == "communicate":
            stdout, stderr = child.communicate()
            assert (stdout, stderr) == (b"", None)
        else:
            while child.poll() is None:
                time.sleep(0.001)
            assert child.returncode == 0
        event_channel = cast(Connection, context.config["event_channel"])
        event_channel.send(("method_continued", {"pid": child.pid}))
        return MethodResult(status="lead", summary=f"reaped with {self.reap_operation}")


class ConcurrentCleanupReapMethod:
    family = "concurrent-cleanup-reap"

    def run(self, context: MethodContext) -> MethodResult:
        event_channel = cast(Connection, context.config["event_channel"])
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        cleanup_polled = Event()
        wait_started = Event()
        wait_reaped = Event()
        original_internal_poll = child._internal_poll
        original_getpgid = os.getpgid

        def coordinated_internal_poll(*args: object, **kwargs: object) -> int | None:
            returncode = original_internal_poll(*args, **kwargs)
            if returncode is None:
                cleanup_polled.set()
            return returncode

        def guarded_getpgid(pid: int) -> int:
            if pid == child.pid:
                assert wait_started.wait(timeout=1), (
                    f"reaper did not start after cleanup poll; "
                    f"cleanup_polled={cleanup_polled.is_set()}"
                )
                if wait_reaped.wait(timeout=0.5):
                    event_channel.send(("lookup_after_reap", {"pid": pid}))
            return original_getpgid(pid)

        def reap_after_cleanup_poll() -> None:
            assert cleanup_polled.wait(timeout=1), "cleanup did not poll child"
            wait_started.set()
            child.terminate()
            try:
                child.wait()
            finally:
                wait_reaped.set()

        child._internal_poll = coordinated_internal_poll  # type: ignore[method-assign]
        os.getpgid = guarded_getpgid
        Thread(target=reap_after_cleanup_poll, daemon=True).start()
        return MethodResult(status="lead", summary="coordinated cleanup race")


class BlockingReapThreadMethod:
    family = "blocking-reap-thread"

    def __init__(self, reap_operation: str) -> None:
        self.reap_operation = reap_operation

    def run(self, context: MethodContext) -> MethodResult:
        event_channel = cast(Connection, context.config["event_channel"])
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        operation_entered = Event()
        if self.reap_operation == "wait":
            original_operation = child._wait

            def coordinated_operation(*args: object, **kwargs: object) -> int:
                operation_entered.set()
                return original_operation(*args, **kwargs)

            child._wait = coordinated_operation  # type: ignore[method-assign]
        else:
            original_communicate = child._communicate

            def coordinated_communicate(
                *args: object, **kwargs: object
            ) -> tuple[bytes | None, bytes | None]:
                operation_entered.set()
                return original_communicate(*args, **kwargs)

            child._communicate = coordinated_communicate  # type: ignore[method-assign]

        def reap_in_thread() -> None:
            if self.reap_operation == "wait":
                child.wait()
            else:
                child.communicate()
            event_channel.send(("waiter_finished", {"operation": self.reap_operation}))

        Thread(target=reap_in_thread, daemon=True).start()
        assert operation_entered.wait(timeout=1)
        return MethodResult(status="lead", summary=f"blocking {self.reap_operation}")


class TimedWaitSemanticsMethod:
    family = "timed-wait-semantics"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            child.wait(timeout=0.1)
        except subprocess.TimeoutExpired as error:
            assert error.timeout == 0.1
            assert child.poll() is None
        else:
            raise AssertionError("wait unexpectedly completed")
        return MethodResult(status="lead", summary="wait timeout preserved")


class TimedCommunicateSemanticsMethod:
    family = "timed-communicate-semantics"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys, time; "
                    "data = sys.stdin.buffer.read(); "
                    "time.sleep(0.15); "
                    "sys.stdout.buffer.write(data)"
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            child.communicate(input=b"payload", timeout=0.02)
        except subprocess.TimeoutExpired as error:
            assert error.timeout == 0.02
        else:
            raise AssertionError("communicate unexpectedly completed")
        stdout, stderr = child.communicate(timeout=1)
        assert (stdout, stderr) == (b"payload", None)
        return MethodResult(status="lead", summary="communicate timeout preserved")


class CallerDeadlineDuringCleanupMethod:
    family = "caller-deadline-during-cleanup"

    def __init__(self, reap_operation: str) -> None:
        self.reap_operation = reap_operation

    def run(self, context: MethodContext) -> MethodResult:
        event_channel = cast(Connection, context.config["event_channel"])
        partial_stdout = b"partial stdout"
        partial_stderr = b"partial stderr"
        if self.reap_operation == "communicate":
            ready_reader, ready_writer = os.pipe()
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "import os, sys, time; "
                        f"sys.stdout.buffer.write({partial_stdout!r}); "
                        "sys.stdout.buffer.flush(); "
                        f"sys.stderr.buffer.write({partial_stderr!r}); "
                        "sys.stderr.buffer.flush(); "
                        "os.write(int(sys.argv[1]), b'ready'); "
                        "time.sleep(60)"
                    ),
                    str(ready_writer),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(ready_writer,),
                start_new_session=True,
            )
            os.close(ready_writer)
            try:
                assert os.read(ready_reader, 5) == b"ready"
            finally:
                os.close(ready_reader)
        else:
            child = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )

        cleanup_started = Event()
        operation_entered = Event()
        first_call_finished = Event()
        original_internal_poll = child._internal_poll
        if self.reap_operation == "wait":
            original_operation = child._wait

            def coordinated_wait(*args: object, **kwargs: object) -> int:
                operation_entered.set()
                return original_operation(*args, **kwargs)

            child._wait = coordinated_wait  # type: ignore[method-assign]
        else:
            original_communicate = child._communicate

            def coordinated_communicate(
                *args: object, **kwargs: object
            ) -> tuple[bytes | None, bytes | None]:
                operation_entered.set()
                return original_communicate(*args, **kwargs)

            child._communicate = coordinated_communicate  # type: ignore[method-assign]

        def coordinated_internal_poll(*args: object, **kwargs: object) -> int | None:
            returncode = original_internal_poll(*args, **kwargs)
            if returncode is None:
                cleanup_started.set()
                if not first_call_finished.wait(timeout=0.5):
                    event_channel.send(
                        (
                            "cleanup_outlasted_caller_deadline",
                            {"operation": self.reap_operation},
                        )
                    )
            return returncode

        child._internal_poll = coordinated_internal_poll  # type: ignore[method-assign]

        def timed_reap() -> None:
            timeout_seconds = 0.01 if self.reap_operation == "wait" else 0.08
            if self.reap_operation == "wait":
                assert cleanup_started.wait(timeout=1)
            started_at = time.monotonic()
            try:
                if self.reap_operation == "wait":
                    result = child.wait(timeout=timeout_seconds)
                else:
                    result = child.communicate(input=b"payload", timeout=timeout_seconds)
            except subprocess.TimeoutExpired as error:
                event_channel.send(
                    (
                        "caller_timed_out",
                        {
                            "operation": self.reap_operation,
                            "cmd": error.cmd,
                            "timeout": error.timeout,
                            "output": error.output,
                            "stderr": error.stderr,
                            "elapsed": time.monotonic() - started_at,
                        },
                    )
                )
            else:
                event_channel.send(
                    (
                        "caller_completed_late",
                        {"operation": self.reap_operation, "result": result},
                    )
                )
            finally:
                first_call_finished.set()

            if self.reap_operation == "wait":
                retry_result: object = child.wait(timeout=1)
            else:
                retry_result = child.communicate(timeout=1)
            event_channel.send(
                (
                    "deadline_retry_finished",
                    {"operation": self.reap_operation, "result": retry_result},
                )
            )

        Thread(target=timed_reap, daemon=True).start()
        if self.reap_operation == "communicate":
            assert operation_entered.wait(timeout=1)
        return MethodResult(
            status="lead",
            summary=f"timed {self.reap_operation} during cleanup",
        )


def _nested_process_tree(pid_path: str) -> None:
    os.setsid()
    descendant = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    Path(pid_path).write_text(f"{os.getpid()}\n{descendant.pid}\n")
    while True:
        time.sleep(0.01)


def test_process_boundary_terminates_and_joins_timed_out_execution() -> None:
    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_problem(), seed=1, config={})

    with pytest.raises(ExecutionTimedOut) as raised:
        boundary.run(HangingMethod(), context, timeout_seconds=0.05)

    assert raised.value.external_execution_started is False
    assert boundary.has_live_child is False


def test_process_boundary_cleans_up_descendant_process_tree(tmp_path: Path) -> None:
    boundary = ProcessExecutionBoundary()
    pid_path = tmp_path / "descendant.pid"
    context = MethodContext(problem=_problem(), seed=1, config={"pid_path": str(pid_path)})

    with pytest.raises(ExecutionTimedOut):
        boundary.run(
            DescendantHangingMethod(),
            context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    descendant_pid = int(pid_path.read_text())
    try:
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        try:
            os.kill(descendant_pid, 9)
        except ProcessLookupError:
            pass


def test_outer_supervisor_cleans_up_registered_nested_process_groups(
    tmp_path: Path,
) -> None:
    pid_path = tmp_path / "tree.pids"
    context = multiprocessing.get_context("forkserver")
    process = context.Process(target=_nested_process_tree, args=(str(pid_path),))
    process.start()
    deadline = time.monotonic() + 2
    while not pid_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert pid_path.exists()
    pids = [int(line) for line in pid_path.read_text().splitlines()]

    terminate_process_tree(process, known_process_groups=pids)

    assert process.is_alive() is False
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_execution_group_is_registered_before_root_can_exit(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    pid_path = tmp_path / "root-exit-descendant.pid"
    method_context = MethodContext(problem=_problem(), seed=1, config={"pid_path": str(pid_path)})

    try:
        with pytest.raises(ExecutionFailed):
            boundary.run(
                RootExitWithDescendantMethod(),
                method_context,
                timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
            )
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
    finally:
        supervisor_reader.close()
        supervisor_writer.close()

    assert [message[0] for message in messages] == [
        "execution_group_started",
        "execution_descendant_started",
        "execution_descendant_stopped",
        "execution_group_stopped",
    ]
    descendant_pid = int(pid_path.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(descendant_pid, 0)


def test_separate_session_descendant_is_registered_and_cleaned_when_root_exits(
    tmp_path: Path,
) -> None:
    process_context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = process_context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    pid_path = tmp_path / "separate-session-descendant.pid"
    method_context = MethodContext(problem=_problem(), seed=1, config={"pid_path": str(pid_path)})

    try:
        with pytest.raises(ExecutionFailed):
            boundary.run(
                RootExitWithSeparateSessionDescendantMethod(),
                method_context,
                timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
            )
        descendant_pid = int(pid_path.read_text())
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
        assert any(
            kind == "execution_descendant_started"
            and payload
            == {
                "pid": descendant_pid,
                "process_group_id": descendant_pid,
            }
            for kind, payload in messages
        )
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        supervisor_reader.close()
        supervisor_writer.close()
        if pid_path.exists():
            descendant_pid = int(pid_path.read_text())
            try:
                os.killpg(descendant_pid, 9)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize(
    ("method", "expected_error"),
    [
        (ReturnsWithSeparateSessionDescendantMethod(), None),
        (HangsWithSeparateSessionDescendantMethod(), ExecutionTimedOut),
    ],
)
def test_separate_session_descendant_is_cleaned_on_result_and_timeout(
    tmp_path: Path,
    method: SolverMethod,
    expected_error: type[BaseException] | None,
) -> None:
    boundary = ProcessExecutionBoundary()
    pid_path = tmp_path / f"{method.family}.pid"
    method_context = MethodContext(problem=_problem(), seed=1, config={"pid_path": str(pid_path)})

    try:
        if expected_error is None:
            outcome = boundary.run(
                method,
                method_context,
                timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
            )
            assert outcome.result.status == "lead"
        else:
            with pytest.raises(expected_error):
                boundary.run(
                    method,
                    method_context,
                    timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
                )
        descendant_pid = int(pid_path.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        if pid_path.exists():
            descendant_pid = int(pid_path.read_text())
            try:
                os.killpg(descendant_pid, 9)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize(
    "method",
    [
        DirectForkMethod(),
        DirectPosixSpawnMethod(),
        DirectMultiprocessingMethod(),
        DirectSystemMethod(),
        AliasedPopenMethod(),
        UnsafePopenModeMethod(),
    ],
)
def test_unsupervised_python_spawn_paths_are_blocked(method: SolverMethod) -> None:
    boundary = ProcessExecutionBoundary()
    method_context = MethodContext(problem=_problem(), seed=1, config={})

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            method,
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    assert type(raised.value.cause).__name__ == "UnsupportedProcessSpawn"


def test_spawn_authorization_is_scoped_to_constructing_thread() -> None:
    boundary = ProcessExecutionBoundary()
    method_context = MethodContext(problem=_problem(), seed=1, config={})

    outcome = boundary.run(
        CrossThreadSpawnBypassMethod(),
        method_context,
        timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
    )

    assert outcome.result.status == "lead"


@pytest.mark.parametrize(
    "method",
    [
        pytest.param(PositionalPreexecPopenMethod(), id="positional-preexec"),
        pytest.param(PositionalShellPopenMethod(), id="positional-shell"),
    ],
)
def test_positional_unsafe_popen_options_are_blocked(method: SolverMethod) -> None:
    boundary = ProcessExecutionBoundary()
    method_context = MethodContext(problem=_problem(), seed=1, config={})

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            method,
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    assert type(raised.value.cause).__name__ == "UnsupportedProcessSpawn"


@pytest.mark.parametrize("reap_operation", ["wait", "communicate", "poll"])
def test_reaped_descendant_is_unregistered_before_method_continues(
    reap_operation: str,
) -> None:
    process_context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = process_context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    method_context = MethodContext(
        problem=_problem(),
        seed=1,
        config={"event_channel": supervisor_writer},
    )

    try:
        outcome = boundary.run(
            ReapsAndContinuesMethod(reap_operation),
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )
        assert outcome.result.status == "lead"
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
    finally:
        supervisor_reader.close()
        supervisor_writer.close()

    kinds = [kind for kind, _ in messages]
    assert kinds == [
        "execution_group_started",
        "execution_descendant_started",
        "execution_descendant_stopped",
        "method_continued",
        "execution_group_stopped",
    ]
    started_payload = messages[1][1]
    stopped_payload = messages[2][1]
    assert stopped_payload == started_payload
    assert messages[3][1] == {"pid": started_payload["pid"]}


def test_cleanup_serializes_against_concurrent_reap() -> None:
    process_context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = process_context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    method_context = MethodContext(
        problem=_problem(),
        seed=1,
        config={"event_channel": supervisor_writer},
    )

    try:
        outcome = boundary.run(
            ConcurrentCleanupReapMethod(),
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )
        assert outcome.result.status == "lead"
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
    finally:
        supervisor_reader.close()
        supervisor_writer.close()

    kinds = [kind for kind, _ in messages]
    assert "lookup_after_reap" not in kinds
    assert kinds.count("execution_descendant_stopped") == 1


@pytest.mark.parametrize("reap_operation", ["wait", "communicate"])
def test_cleanup_interrupts_blocking_reap_thread(reap_operation: str) -> None:
    process_context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = process_context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    method_context = MethodContext(
        problem=_problem(),
        seed=1,
        config={"event_channel": supervisor_writer},
    )

    try:
        outcome = boundary.run(
            BlockingReapThreadMethod(reap_operation),
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )
        assert outcome.result.status == "lead"
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
    finally:
        supervisor_reader.close()
        supervisor_writer.close()

    kinds = [kind for kind, _ in messages]
    assert kinds.count("execution_descendant_stopped") == 1
    assert ("waiter_finished", {"operation": reap_operation}) in messages


@pytest.mark.parametrize(
    "method",
    [TimedWaitSemanticsMethod(), TimedCommunicateSemanticsMethod()],
)
def test_reap_timeout_and_communicate_semantics_are_preserved(
    method: SolverMethod,
) -> None:
    boundary = ProcessExecutionBoundary()
    method_context = MethodContext(problem=_problem(), seed=1, config={})

    outcome = boundary.run(
        method,
        method_context,
        timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
    )

    assert outcome.result.status == "lead"


@pytest.mark.parametrize(
    ("reap_operation", "expected_output", "expected_stderr"),
    [
        pytest.param("wait", None, None, id="wait"),
        pytest.param(
            "communicate",
            b"partial stdout",
            b"partial stderr",
            id="communicate",
        ),
    ],
)
def test_caller_deadline_expires_during_cleanup(
    reap_operation: str,
    expected_output: bytes | None,
    expected_stderr: bytes | None,
) -> None:
    process_context = multiprocessing.get_context("forkserver")
    supervisor_reader, supervisor_writer = process_context.Pipe(duplex=False)
    boundary = ProcessExecutionBoundary(supervisor_channel=supervisor_writer)
    method_context = MethodContext(
        problem=_problem(),
        seed=1,
        config={"event_channel": supervisor_writer},
    )

    try:
        outcome = boundary.run(
            CallerDeadlineDuringCleanupMethod(reap_operation),
            method_context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )
        assert outcome.result.status == "lead"
        messages = []
        while supervisor_reader.poll(0.02):
            messages.append(supervisor_reader.recv())
    finally:
        supervisor_reader.close()
        supervisor_writer.close()

    kinds = [kind for kind, _ in messages]
    assert "cleanup_outlasted_caller_deadline" not in kinds
    assert "caller_completed_late" not in kinds
    timeout_payloads = [payload for kind, payload in messages if kind == "caller_timed_out"]
    assert len(timeout_payloads) == 1
    timeout_payload = timeout_payloads[0]
    expected_timeout = 0.01 if reap_operation == "wait" else 0.08
    assert timeout_payload["operation"] == reap_operation
    assert timeout_payload["cmd"][0] == sys.executable
    assert timeout_payload["timeout"] == expected_timeout
    assert timeout_payload["output"] == expected_output
    assert timeout_payload["stderr"] == expected_stderr
    assert timeout_payload["elapsed"] < 0.25
    retry_payloads = [payload for kind, payload in messages if kind == "deadline_retry_finished"]
    assert len(retry_payloads) == 1
    retry_payload = retry_payloads[0]
    assert retry_payload["operation"] == reap_operation
    if reap_operation == "wait":
        assert retry_payload["result"] < 0
    else:
        assert retry_payload["result"] == (expected_output, expected_stderr)


def test_process_boundary_reports_external_start_on_failure() -> None:
    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_problem(), seed=1, config={})

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            StartsThenFailsMethod(),
            context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    assert raised.value.external_execution_started is True
    assert isinstance(raised.value.cause, RuntimeError)
    assert boundary.has_live_child is False


def test_external_child_waits_for_durable_dispatch_acknowledgement(
    tmp_path: Path,
) -> None:
    boundary = ProcessExecutionBoundary()
    committed = tmp_path / "dispatch-committed"
    provider = tmp_path / "provider-called"
    context = MethodContext(
        problem=_problem(),
        seed=1,
        config={
            "committed_path": str(committed),
            "provider_path": str(provider),
        },
    )

    def commit_dispatch() -> None:
        assert not provider.exists()
        time.sleep(0.05)
        assert not provider.exists()
        committed.write_text("committed")

    outcome = boundary.run(
        GatedExternalMethod(),
        context,
        timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        external_started_callback=commit_dispatch,
    )

    assert outcome.external_execution_started is True
    assert provider.read_text() == "provider-called"


def test_dispatch_callback_failure_never_releases_provider_boundary(
    tmp_path: Path,
) -> None:
    boundary = ProcessExecutionBoundary()
    committed = tmp_path / "dispatch-committed"
    provider = tmp_path / "provider-called"
    context = MethodContext(
        problem=_problem(),
        seed=1,
        config={
            "committed_path": str(committed),
            "provider_path": str(provider),
        },
    )

    def fail_dispatch_commit() -> None:
        raise OSError("dispatch transaction failed before commit")

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            GatedExternalMethod(),
            context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
            external_started_callback=fail_dispatch_commit,
        )

    assert raised.value.external_execution_started is False
    assert isinstance(raised.value.cause, OSError)
    assert not committed.exists()
    assert not provider.exists()
    assert boundary.has_live_child is False


def test_process_boundary_propagates_operator_interrupts() -> None:
    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_problem(), seed=1, config={})

    with pytest.raises(KeyboardInterrupt):
        boundary.run(
            InterruptMethod(),
            context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    assert boundary.has_live_child is False


def test_process_boundary_wraps_process_start_failure_as_prestart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_problem(), seed=1, config={})

    def fail_start(_process: BaseProcess) -> None:
        raise OSError("forkserver unavailable")

    monkeypatch.setattr(BaseProcess, "start", fail_start)

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            HangingMethod(),
            context,
            timeout_seconds=FORKSERVER_TEST_TIMEOUT_SECONDS,
        )

    assert raised.value.external_execution_started is False
    assert isinstance(raised.value.cause, OSError)
    assert boundary.has_live_child is False
