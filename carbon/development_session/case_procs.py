"""Per-case worker processes inside ONE graded pass (Lead's order, Mon 16 Nov 2026).

A graph route v2 version in `direct_graph_construction_worker.CASE_PROCS_INFERENCE_VERSIONS` runs its graded per-case
loop in worker processes: one per core of the inference container's cpuset (the round's lane), each pinned to its one
core, at most as many as the version's registered worker memory and the container's pids room hold. The rows are split
into contiguous slices and the answers reassembled in row order. Every row is still its own per-case call of the SAME
compiled forward over the SAME padded block, so no answer can depend on another row or on the split.

Same executable, by construction: a worker makes its first call (which compiles every executable the loop uses) and
only then pins its threads to its core, so its XLA CPU thread pool and its compiled code are sized for the parent's
cpuset exactly as the one-process program's are; every later row has the same shapes and reuses them. Pinning only
stops the pool's threads from spreading over the other cores.

Self-check, every pass (a check on top of the construction, not a proof of it): before any worker's answers are used,
the first and the last row of every slice are computed in the parent process, alone, and each worker's answers for
those rows must equal them bit for bit (dtype, shape and bytes). Any difference stops every worker and the whole pass
runs as one process's per-case calls; a worker that fails, cannot start or passes its deadline has its slice computed by
the parent.

Never the candidate's: Carbon's workers must not turn into a wall or memory stop the candidate is charged for
(`research_carrier._candidate_resource_stop`). Every worker deadline ends a margin before the version's inference wall;
when the parent's own calls for the rows left cannot finish before that margin, the parent stops at once with a
nonzero exit (never the wall), and every fallback leaves a ``case_procs:`` line on stderr, which the host reads as
Carbon's (a worker killed for memory, the parent's late failure): never a candidate resource stop.

Timing is untouched: the speed gate's single-call program and the practice timed program are derived from the
version's program after `serial_program` removes these edits, so they are byte for byte today's programs (and the speed
workload digest is unchanged).

Everything here is resource containment and speed. No value of science is decided: the process count is the cpuset's
core count, cut by operational memory and pids bounds.
"""

from __future__ import annotations

import inspect
import re

#: RESOURCE CONTAINMENT, not science: the share of the version's registered worker memory (`memory_bytes_max`) the
#: worker processes and the parent may plan to hold together.
CASE_PROCS_MEMORY_SHARE = 0.5
#: RESOURCE CONTAINMENT, not science: what one more Python + JAX process is planned to hold beyond its model, its state
#: bytes and one per-case call (runtime, compiled executable, buffers).
CASE_PROCS_PROCESS_BYTES = 1024**3
#: OPERATIONAL, not science: a worker's deadline is this many times its planned time (the parent's first call, then its
#: rows at the parent's per-row time times the cpuset's cores), and never later than the wall margin below; past it the
#: worker is stopped and its slice computed in the parent.
CASE_PROCS_DEADLINE_SLACK = 4.0
#: OPERATIONAL, not science: the seconds before the version's inference wall (counted from the program's start) by
#: which the parent's own calls must be done; a fallback that cannot make it stops the pass as Carbon's instead.
CASE_PROCS_WALL_MARGIN_SECONDS = 30
#: OPERATIONAL, not science: the parent's estimate of its own remaining calls is multiplied by this before it is
#: compared with the time left.
CASE_PROCS_FALLBACK_SLACK = 1.25

#: Marks a per-case processes program (the parent's environment name for its workers' control).
CONTROL_NAME = "CARBON_CASE_PROC"
#: The stderr prefix of every fallback line; the host reads a failure that carries it as Carbon's.
FALLBACK_MARK = b"case_procs: "


def case_procs_count(
    doc, members, state_bytes, memory_bytes, share, process_bytes, cores, rows
):
    """The worker process count of one pass: min(cores, rows, share * memory_bytes // per_process - 1), at least 1
    (1 = no workers: the parent's own per-case calls). per_process = 3 x every member's parameters (loaded, the member
    arrays, the call's) + the state's bytes + one per-case call's over-estimated activations (the declared input block
    and the declared output of every node of every graph, at the declared batch) + ``process_bytes``; the parent holds
    one too. Self-contained: the program carries its source.
    """
    from carbon.level4.graph import nbytes

    graphs = doc["graphs"]
    declared = graphs[doc["entry"]]["inputs"]
    parameter_bytes = members * sum(nbytes(entry) for entry in declared[:-1])
    per_case_bytes = nbytes(declared[-1]) + sum(
        nbytes(out)
        for graph in graphs.values()
        for node in graph["nodes"]
        for out in node["out"]
    )
    each = 3 * parameter_bytes + state_bytes + per_case_bytes + process_bytes
    held = int(memory_bytes * share) // max(1, each) - 1
    return max(1, min(cores, rows, held))


#: The one-process per-case loop of `PHYSICAL_V2_COMPILED_INFER_PROGRAM` (= `direct_graph_construction_worker.
#: _PER_CASE_CALLS`, held equal by a test).
SERIAL_CALLS = (
    "    # public constant (zeros), so no output can depend on another case.\n"
    "    for index in range(len(input_array)):\n"
    "        part = jnp.pad(input_array[index:index + 1],\n"
    "                       [(0, batch - 1)] + [(0, 0)] * (input_array.ndim - 1))\n"
    "        outputs = forward(*parameter_arrays, part)\n"
    "        if len(outputs) != 1:\n"
    "            raise ValueError(arity)\n"
    "        blocks.append(outputs[0][:1])\n"
)

_PIN_OLD = "from pathlib import Path\nimport numpy as np\n"
_PIN_NEW = (
    "from pathlib import Path\n"
    "# A per-case worker process (case_procs) reads its control here; it pins itself to its core only after its first\n"
    "# call (backend, thread pool and compiled code made for the parent's cpuset: the same executable, the same rounding).\n"
    "case_start = time.monotonic()\n"
    "case_env = dict(os.environ)\n"
    'case_proc = os.environ.get("' + CONTROL_NAME + '")\n'
    "if case_proc is not None:\n"
    '    case_proc = [int(value) for value in case_proc.split(",")]\n'
    "    if len(case_proc) != 4 or not 0 <= case_proc[1] < case_proc[2] or case_proc[3] < 0:\n"
    '        raise ValueError("per-case worker control differs")\n'
    "    try:\n"
    "        # out of memory, the kernel stops a worker first; its slice is then computed in the parent\n"
    '        Path("/proc/self/oom_score_adj").write_text("1000")\n'
    "    except OSError:\n"
    "        pass\n"
    "import numpy as np\n"
)
# a worker never re-stages the modules the parent staged (and imports): no file is rewritten while another reads it
_INIT_OLD = '    (folder / "__init__.py").write_text("")\n'
_INIT_NEW = (
    '    if case_proc is None:\n        (folder / "__init__.py").write_text("")\n'
)
_COPY_OLD = '    shutil.copyfile(work / (name + ".py"), destination)\n'
_COPY_NEW = (
    "    if case_proc is None:\n"
    '        shutil.copyfile(work / (name + ".py"), destination)\n'
)
_LAST_LINE = (
    "            blocks.extend(sample.get(index) if index in sample else case_block(index)\n"
    "                          for index in range(low, high))\n"
)

_PROCS_CALLS = """    # public constant (zeros), so no output can depend on another case.
    # PER-CASE PROCESSES (Lead's order, Mon 16 Nov 2026; carbon.development_session.case_procs): the SAME per-case
    # calls, the rows split into contiguous slices, one worker process per core of this container's cpuset (pinned to
    # it after its first call), answers reassembled in row order. The first and last row of every slice are computed
    # here first, in one process; a worker's answers for them must equal those bit for bit, or every worker stops and
    # this process makes every call. A worker that fails, cannot start or runs past its deadline has its slice computed
    # here; a fallback that cannot finish before the wall margin stops the pass as Carbon's. No value is decided here.
    def case_block(index):
        part = jnp.pad(input_array[index:index + 1],
                       [(0, batch - 1)] + [(0, 0)] * (input_array.ndim - 1))
        outputs = forward(*parameter_arrays, part)
        if len(outputs) != 1:
            raise ValueError(arity)
        return np.asarray(outputs[0][:1])
__COUNT_SOURCE__
    rows = len(input_array)
    procs_dir = work / "case-procs"
    case_wall_end = case_start + __WALL_SECONDS__ - __WALL_MARGIN__
    if case_proc is not None:
        _, low, high, core = case_proc
        if high > rows:
            raise ValueError("per-case worker control differs")
        blocks.append(case_block(low))
        np.save(procs_dir / f"head-{low}.tmp.npy", blocks[0])
        os.replace(procs_dir / f"head-{low}.tmp.npy", procs_dir / f"head-{low}.npy")
        # every executable exists now, made for the parent's cpuset: only now every thread goes to one core
        pinned = set()
        while True:  # until no thread appears that is not pinned yet
            tasks = set(os.listdir("/proc/self/task")) - pinned
            if not tasks:
                break
            for task in tasks:
                try:
                    os.sched_setaffinity(int(task), {core})
                except OSError:
                    pass
            pinned |= tasks
        for index in range(low + 1, high):
            blocks.append(case_block(index))
        np.save(procs_dir / f"part-{low}.tmp.npy", np.concatenate(blocks))
        os.replace(procs_dir / f"part-{low}.tmp.npy", procs_dir / f"part-{low}.npy")
        sys.stdout.flush()
        os._exit(0)
    cores = sorted(os.sched_getaffinity(0))
    try:
        procs = case_procs_count(doc, len(member_arrays), len(state), __MEMORY_BYTES__, __SHARE__, __PROCESS_BYTES__,
                                 len(cores), rows)
    except Exception:
        procs = 1
    try:
        # the container's pids room (threads count): at most half of it, at this process's own thread count each
        pids = Path("/sys/fs/cgroup/pids.max").read_text().strip()
        if pids != "max":
            room = int(pids) - int(Path("/sys/fs/cgroup/pids.current").read_text())
            procs = min(procs, max(1, room // (2 * len(os.listdir("/proc/self/task")))))
    except (OSError, ValueError):
        pass  # no cgroup v2 pids files: the memory and core bounds stand
    # a worker runs this same program file (the carrier's /input/program.py) on the CPU; else one process
    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] not in ("", "-c") else None
    if script is None or not os.path.isfile(script) or jax.default_backend() != "cpu":
        procs = 1
    slices = [(k * rows // procs, (k + 1) * rows // procs) for k in range(procs)] if procs > 1 else []
    done, sample = {}, {}
    if slices:
        import subprocess
        same = lambda a, b: a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
        # a worker repeats this process's start (interpreter, imports, state load and checks) before its first call
        startup = time.monotonic() - case_start
        clock = time.perf_counter()
        sample = {0: case_block(0)}
        first = time.perf_counter() - clock
        clock = time.perf_counter()
        for low, high in slices:
            for index in (low, high - 1):
                if index not in sample:
                    sample[index] = case_block(index)
        per_row = (time.perf_counter() - clock) / max(1, len(sample) - 1)
        # Workers only when they can help and the candidate's OWN one-process time fits the wall: a candidate too slow
        # for the wall in one process runs in one process and meets the wall exactly as before (its stop is its own).
        if len(sample) >= rows or time.monotonic() + per_row * (rows - len(sample)) > case_wall_end:
            slices = []
    if slices:
        # operational, not science: a worker repeats this process's start and first call, then runs on one core, so a
        # row may take up to the cores' count times longer
        allowance = __SLACK__ * (
            startup + first + per_row * len(cores) * max(high - low for low, high in slices))
        workers, agreed, started, late = [], True, True, set()
        try:
            shutil.rmtree(procs_dir, ignore_errors=True)
            procs_dir.mkdir()
            for k, (low, high) in enumerate(slices):
                workers.append(subprocess.Popen(
                    [sys.executable, "-I", script],
                    env=dict(case_env, __CONTROL_NAME__=f"{k},{low},{high},{cores[k]}"),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        except OSError as error:
            started = agreed = False
            print(f"case_procs: workers not started ({type(error).__name__}); every call in one process",
                  file=sys.stderr)
        try:
            deadline = min(time.monotonic() + allowance, case_wall_end)
            waiting = dict(enumerate(slices))
            while waiting and agreed:
                for k, (low, high) in list(waiting.items()):
                    head = procs_dir / f"head-{low}.npy"
                    if head.exists():
                        agreed = agreed and same(np.load(head, allow_pickle=False), sample[low])
                        del waiting[k]
                    elif workers[k].poll() is not None and not head.exists():
                        del waiting[k]  # failed before its first row: its slice is computed here
                if waiting and agreed:
                    if time.monotonic() > deadline:
                        for k in waiting:
                            workers[k].kill()  # past its deadline: its slice is computed here
                            late.add(k)
                        break
                    time.sleep(0.05)
            for k, worker in enumerate(workers):
                if not agreed:
                    break
                low, high = slices[k]
                try:
                    code = worker.wait(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    worker.kill()
                    late.add(k)
                    code = worker.wait()
                part = procs_dir / f"part-{low}.npy"
                if code == 0 and part.exists():
                    answer = np.load(part, allow_pickle=False)
                    if (answer.shape[0] == high - low and same(answer[:1], sample[low])
                            and same(answer[-1:], sample[high - 1])):
                        done[low] = answer
                    else:
                        agreed = False
                if agreed and low not in done:
                    why = "past its deadline" if k in late else f"exit {code}, {'a' if part.exists() else 'no'} part"
                    print(f"case_procs: worker {k} {why}; its rows in one process", file=sys.stderr)
        except OSError as error:
            agreed = False
            print(f"case_procs: worker results unreadable ({type(error).__name__}); every call in one process",
                  file=sys.stderr)
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                worker.wait()
            shutil.rmtree(procs_dir, ignore_errors=True)
        if not agreed:
            done = {}
            if started:
                print("case_procs: a worker's answer differs from one process; every call in one process",
                      file=sys.stderr)
        left = sum(high - low for low, high in slices if low not in done)
        if left and time.monotonic() + __FALLBACK_SLACK__ * per_row * left > case_wall_end:
            # Carbon's workers failed too late for this process to make their calls inside the wall: stop now, as
            # Carbon's (nonzero exit with this line on stderr), never as the candidate's wall stop
            print(f"case_procs: CARBON: {left} rows left cannot finish inside the inference wall", file=sys.stderr)
            sys.exit(3)
    for low, high in slices or [(0, rows)]:
        if low in done:
            blocks.append(done[low])
        else:
            # the rows this process already computed (the sample) are its own answers: reused, not recomputed
            blocks.extend(sample.get(index) if index in sample else case_block(index)
                          for index in range(low, high))
"""


def _count_source() -> str:
    """`case_procs_count`'s own source, indented into the per-case branch."""
    return "".join(
        ("    " + line) if line.strip() else line
        for line in inspect.getsource(case_procs_count).splitlines(keepends=True)
    ).rstrip("\n")


def _edits(memory_bytes: int, wall_seconds: int):
    for value in (memory_bytes, wall_seconds):
        if type(value) is not int or value <= 0:
            raise RuntimeError("per-case processes version worker limits unregistered")
    calls = (
        _PROCS_CALLS.replace("__COUNT_SOURCE__", _count_source())
        .replace("__MEMORY_BYTES__", str(memory_bytes))
        .replace("__WALL_SECONDS__", str(wall_seconds))
        .replace("__WALL_MARGIN__", str(CASE_PROCS_WALL_MARGIN_SECONDS))
        .replace("__SHARE__", repr(CASE_PROCS_MEMORY_SHARE))
        .replace("__PROCESS_BYTES__", str(CASE_PROCS_PROCESS_BYTES))
        .replace("__SLACK__", repr(CASE_PROCS_DEADLINE_SLACK))
        .replace("__FALLBACK_SLACK__", repr(CASE_PROCS_FALLBACK_SLACK))
        .replace("__CONTROL_NAME__", CONTROL_NAME)
    )
    return (
        (_PIN_OLD, _PIN_NEW),
        (_INIT_OLD, _INIT_NEW),
        (_COPY_OLD, _COPY_NEW),
        (SERIAL_CALLS, calls),
    )


def procs_program(base: str, memory_bytes: int, wall_seconds: int) -> str:
    """``base`` (the compiled v2 inference program) with four anchored edits and nothing else: the worker's control,
    the two staging writes a worker skips, and the per-case loop run over worker processes. ``memory_bytes`` and
    ``wall_seconds`` are the version's registered worker memory and inference wall.
    """
    program = base
    for old, new in _edits(memory_bytes, wall_seconds):
        if program.count(old) != 1:
            raise RuntimeError("graph route v2 inference program anchor moved")
        program = program.replace(old, new)
    return program


_MEMORY_PATTERN = re.compile(
    r"case_procs_count\(doc, len\(member_arrays\), len\(state\), ([0-9]+), "
)
_WALL_PATTERN = re.compile(r"case_wall_end = case_start \+ ([0-9]+) - ")


def serial_program(program: str) -> str:
    """The one-process program a per-case processes program was made from (`procs_program`'s edits removed); any
    other program unchanged. Strict: the result, edited again, must give back ``program`` exactly. The timed programs
    derive from this, so timing never meets a worker.
    """
    if CONTROL_NAME not in program:
        return program
    memory = _MEMORY_PATTERN.findall(program)
    wall = _WALL_PATTERN.findall(program)
    head = _PROCS_CALLS[: _PROCS_CALLS.index("    def case_block")]
    if (
        len(memory) != 1
        or len(wall) != 1
        or program.count(head) != 1
        or program.count(_LAST_LINE) != 1
    ):
        raise RuntimeError("per-case processes program anchor moved")
    start = program.index(head)
    end = program.index(_LAST_LINE, start) + len(_LAST_LINE)
    result = program[:start] + SERIAL_CALLS + program[end:]
    for old, new in (
        (_PIN_OLD, _PIN_NEW),
        (_INIT_OLD, _INIT_NEW),
        (_COPY_OLD, _COPY_NEW),
    ):
        if result.count(new) != 1:
            raise RuntimeError("per-case processes program anchor moved")
        result = result.replace(new, old)
    if (
        CONTROL_NAME in result
        or procs_program(result, int(memory[0]), int(wall[0])) != program
    ):
        raise RuntimeError("per-case processes program anchor moved")
    return result


__all__ = [
    "CASE_PROCS_DEADLINE_SLACK",
    "CASE_PROCS_FALLBACK_SLACK",
    "CASE_PROCS_MEMORY_SHARE",
    "CASE_PROCS_PROCESS_BYTES",
    "CASE_PROCS_WALL_MARGIN_SECONDS",
    "CONTROL_NAME",
    "FALLBACK_MARK",
    "SERIAL_CALLS",
    "case_procs_count",
    "procs_program",
    "serial_program",
]
