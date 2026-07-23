# Execution containment security contract

Mathloop has two execution boundaries with different trust assumptions.

## Local Python method boundary

Local method plugins run in a disposable forkserver process and may create child
processes only through `subprocess.Popen` or helpers built on it, such as
`subprocess.run`. Mathloop interposes this call inside the execution process and:

1. binds the complete Popen signature, including positional arguments, then
   rejects `shell=True`, `preexec_fn`, and joining an existing process group;
2. creates the child, then synchronously records its PID and actual process group
   with both the immediate boundary and the outer worker supervisor before Popen
   returns to method code;
3. retains the live Popen object so result/error and wrapped `os._exit` paths can
   terminate and reap the exact child without a PID-reuse lookup;
4. retains owned process-group IDs in the parent supervisors, allowing bounded
   TERM/KILL cleanup after the execution or worker root has exited and the child
   has been reparented; and
5. coordinates public reap calls and boundary cleanup per Popen object with
   bounded wait/communicate slices: cleanup requests interrupt blocking reaps,
   timed callers retain their original deadline and timeout payload while awaiting
   cleanup, cleanup rechecks exact record ownership, and the lifecycle lock remains
   held through its PID/PGID lookup, signaling, and reap window; and
6. removes the exact Popen object's registration immediately when `wait`,
   `communicate`, or a non-`None` `poll` confirms exit, or after boundary cleanup.

Direct `os.fork`/`os.forkpty`, `os.posix_spawn`, `os.system`, pre-bound Popen
aliases, and `multiprocessing.Process.start` are blocked inside method execution.
These paths cannot create an unregistered Python child. A separately sessioned
child created with `Popen(start_new_session=True)` is supported: its new process
group is registered before Popen returns and is killed on result, error, timeout,
or abrupt execution-root exit.

The outer supervisor signals only groups synchronously registered by its own
execution children (plus its worker's own session group). It does not kill a PID
found solely through a stale ancestry scan, avoiding unrelated-process cleanup.

## Native and daemonizing helpers

Darwin has no supported subreaper/job-object primitive for this use. The macOS SDK
explicitly marks kqueue `NOTE_TRACK`, `NOTE_TRACKERR`, and `NOTE_CHILD` unsupported
since macOS 10.5. A native helper can call `setsid` or fork internally after exec,
outside Python's spawn interposition; local process-group supervision cannot make
that case a hard containment boundary.

Therefore native, FFI, shell, or otherwise daemonizing/untrusted helper code is
not permitted in a local method plugin. It must run through `DockerRunner`, where
the container is the lifecycle boundary. Docker execution retains the existing
network, filesystem, capability, process, memory, CPU, no-new-privileges, and
wall-clock restrictions; this contract does not weaken those controls.
