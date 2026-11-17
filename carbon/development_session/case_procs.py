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

Workers only when the WORST case fits (Validator-2 F1, 16 Nov): every worker stopped at its deadline and then every
row made by the parent alone (`CASE_PROCS_FALLBACK_SLACK` x the sampled per-row time x the rows) must still end by the
wall margin, else the pass is the one-process pass from the start (`case_procs_deadline`). A pass that fits in one
process but sits near the wall is therefore graded exactly as before.

A fallback is Carbon's ONCE (Validator-2 F2, 16 Nov): every fallback leaves a ``case_procs:`` line on stderr; a failed
pass of a per-case processes program that carries it is Carbon's (`research_carrier._case_procs_fell_back`), and a
durable record of it, keyed on the pass's content (owner, program, control, state, inputs: `fallback_key`), makes EVERY
later run of that same pass run the one-process program (`serial_program`, via `pass_program`), whose wall and memory
stops the host classifies exactly as any one-process pass. The wall margin lies before the host's own program wall
(its 45 s reserve, its 60 s setup budget and 30 s for the exec), and a fallback stops with the mark the moment it
passes it, so a fallback never meets the host's wall without the mark.

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
#: The host's own program reserve: `research_carrier._run_locked` ends the program stage ``seconds - 45`` after the op
#: started (its `program_timeout`). Held equal by a test.
CASE_PROCS_HOST_RESERVE_SECONDS = 45
#: The host's setup budget (`research_carrier._PROGRAM_SETUP_BUDGET_SECONDS`): a program stage that started later has
#: no candidate wall stop at all. Held equal by a test.
CASE_PROCS_HOST_SETUP_SECONDS = 60
#: OPERATIONAL, not science: the seconds before the version's inference wall (counted from the program's start) by
#: which the parent's own calls must be done; a fallback past it stops the pass as Carbon's instead. The host's reserve
#: and setup budget plus 30 s for the exec and the interpreter's start, so it always lies before the host's own program
#: wall (Validator-2 F1/F2 repair, 16 Nov: at 30 s it lay AFTER the host's wall).
CASE_PROCS_WALL_MARGIN_SECONDS = (
    CASE_PROCS_HOST_RESERVE_SECONDS + CASE_PROCS_HOST_SETUP_SECONDS + 30
)
#: OPERATIONAL, not science: the parent's estimate of its own remaining calls is multiplied by this before it is
#: compared with the time left, and in the worst-case gate (`case_procs_deadline`).
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


def case_procs_deadline(
    now,
    startup,
    first,
    per_row,
    cores,
    longest,
    rows,
    sampled,
    wall_end,
    slack,
    fallback_slack,
):
    """The workers' deadline (monotonic seconds), or None: no workers, the one-process pass (Validator-2 F1).

    A worker repeats the parent's start and first call, then runs on one core, so a row may take up to ``cores`` times
    the parent's per-row time: its allowance is ``slack`` x (startup + first + per_row x cores x the longest slice).
    WORST CASE: every worker stopped at that deadline and then all ``rows`` made by the parent alone (``fallback_slack``
    x per_row x rows) must still end by ``wall_end``, else None; the deadline is capped there. None too when the sample
    already made every row. Self-contained: the program carries its source.
    """
    if sampled >= rows:
        return None
    latest = wall_end - fallback_slack * per_row * rows
    deadline = now + slack * (startup + first + per_row * cores * longest)
    if deadline > latest:
        return None
    return min(deadline, latest)


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
    "            if fell_back and index not in sample:\n"
    "                row_time = max(row_time, time.perf_counter() - row_clock)\n"
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
__DEADLINE_SOURCE__
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
        # Workers only when the WORST case fits: every worker stopped at its deadline and every row then made here
        # still ends by the wall margin (operational, not science). Else the one-process pass, exactly as before.
        deadline = case_procs_deadline(time.monotonic(), startup, first, per_row, len(cores),
                                       max(high - low for low, high in slices), rows, len(sample), case_wall_end,
                                       __SLACK__, __FALLBACK_SLACK__)
        if deadline is None:
            slices = []
    if slices:
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
    fell_back = len(done) < len(slices)
    # after a fallback, the longest row this process has made (the sampled per-row time to start with)
    row_time = per_row if fell_back else 0.0
    for low, high in slices or [(0, rows)]:
        if low in done:
            blocks.append(done[low])
            continue
        for index in range(low, high):
            if fell_back and time.monotonic() + __FALLBACK_SLACK__ * row_time > case_wall_end:
                # look-ahead: a row is never STARTED after a fallback unless it can end by the wall margin (rows
                # slower than sampled): Carbon's, with the mark, before the host's wall
                print(f"case_procs: CARBON: row {index} of {rows} would end past the wall margin after a fallback",
                      file=sys.stderr)
                sys.exit(3)
            row_clock = time.perf_counter()
            # the rows this process already computed (the sample) are its own answers: reused, not recomputed
            blocks.append(sample[index] if index in sample else case_block(index))
            if fell_back and index not in sample:
                row_time = max(row_time, time.perf_counter() - row_clock)
"""


def _indented_source(function) -> str:
    """A function's own source, indented into the per-case branch."""
    return "".join(
        ("    " + line) if line.strip() else line
        for line in inspect.getsource(function).splitlines(keepends=True)
    ).rstrip("\n")


def _edits(memory_bytes: int, wall_seconds: int):
    for value in (memory_bytes, wall_seconds):
        if type(value) is not int or value <= 0:
            raise RuntimeError("per-case processes version worker limits unregistered")
    calls = (
        _PROCS_CALLS.replace("__COUNT_SOURCE__", _indented_source(case_procs_count))
        .replace("__DEADLINE_SOURCE__", _indented_source(case_procs_deadline))
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


def is_procs_program(program) -> bool:
    """Whether ``program`` is a per-case processes program (`procs_program`)."""
    return type(program) is str and CONTROL_NAME in program


def fell_back(program, diagnostic) -> bool:
    """Whether a FAILED run of ``program`` fell back (Validator-2 F2): a per-case processes program whose private
    diagnostic carries a fallback line. Only then is the failure Carbon's; a one-process program's diagnostic is never
    read for the mark (its stops are classified as before, whatever its stderr says). The mark counts only at the start
    of a line, as the program prints it: text echoed inside a traceback or an error message never starts one.
    """
    return (
        is_procs_program(program)
        and type(diagnostic) is bytes
        and any(line.startswith(FALLBACK_MARK) for line in diagnostic.split(b"\n"))
    )


#: The durable record of one pass's fallback, beside the owner's ledger (`fallback_path`).
FALLBACK_SCHEMA = "carbon.development.case-procs-fallback.v1"


def fallback_key(owner, program, files) -> str:
    """The content of one graded pass: the owner, the program and the staged control, state and inputs. Every later run
    of the same pass has the same key, whatever its ledger identity (a re-queued attempt, a regrade re-run).
    """
    import hashlib
    import json

    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    return sha(
        json.dumps(
            {
                "schema": FALLBACK_SCHEMA,
                "owner": owner,
                "program_sha256": sha(program.encode()),
                **{
                    name: sha(files[name])
                    for name in ("control.json", "state.npz", "inputs.npz")
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def fallback_path(root, key):
    from pathlib import Path

    return Path(root) / ("case-procs-fallback-" + key + ".json")


def record_fallback(root, owner, program, files) -> None:
    """Write (once, durably) that this pass fell back: every later run of it runs `serial_program` (`pass_program`)."""
    import json
    import os
    from pathlib import Path

    key = fallback_key(owner, program, files)
    Path(root).mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {"schema": FALLBACK_SCHEMA, "key": key}, sort_keys=True, separators=(",", ":")
    ).encode()
    try:
        with open(fallback_path(root, key), "xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass


def pass_program(ledger, owner, program, files) -> str:
    """The program a run of this pass runs: ``program``, or its one-process program (`serial_program`) once a run of
    the same pass fell back (`record_fallback` under ``ledger.root``). Any program other than a per-case processes one
    is returned unchanged (the ledger is then not read).
    """
    if not is_procs_program(program):
        return program
    if fallback_path(ledger.root, fallback_key(owner, program, files)).is_file():
        return serial_program(program)
    return program


def program_digests(challenge_id, version) -> dict:
    """The two inference programs a per-case processes version can grade with (Validator-2 F3): the graded program
    (per-case processes) and the one-process program a pass runs after its recorded fallback (`pass_program`), as
    ``sha256:`` digests of their text. For the version's declared-change record and evidence.
    """
    import hashlib

    from .direct_graph_construction_worker import case_procs_infer_program

    graded = case_procs_infer_program(challenge_id, version)
    return {
        "graded_program_sha256": "sha256:"
        + hashlib.sha256(graded.encode()).hexdigest(),
        "fallback_retry_program_sha256": "sha256:"
        + hashlib.sha256(serial_program(graded).encode()).hexdigest(),
    }


__all__ = [
    "CASE_PROCS_DEADLINE_SLACK",
    "CASE_PROCS_FALLBACK_SLACK",
    "CASE_PROCS_HOST_RESERVE_SECONDS",
    "CASE_PROCS_HOST_SETUP_SECONDS",
    "CASE_PROCS_MEMORY_SHARE",
    "CASE_PROCS_PROCESS_BYTES",
    "CASE_PROCS_WALL_MARGIN_SECONDS",
    "CONTROL_NAME",
    "FALLBACK_MARK",
    "FALLBACK_SCHEMA",
    "SERIAL_CALLS",
    "case_procs_count",
    "case_procs_deadline",
    "fallback_key",
    "fallback_path",
    "fell_back",
    "is_procs_program",
    "pass_program",
    "procs_program",
    "program_digests",
    "record_fallback",
    "serial_program",
]


if (
    __name__ == "__main__"
):  # python -I -m carbon.development_session.case_procs CHALLENGE VERSION
    import json
    import sys

    print(json.dumps(program_digests(sys.argv[1], sys.argv[2]), sort_keys=True))
