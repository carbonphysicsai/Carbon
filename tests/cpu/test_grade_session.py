"""Item 4: ONE CONTAINER SESSION PER GRADE (`research_carrier.grade_session`).

A counted grade's fixed inference ops run one after another in one worker container, each its own `docker exec` (a new
process), with per-op ledger operations, intents, controls and evidence. A fake Docker CLI keeps the container state, so
each test checks what was created, exec'd, shown at `/input` and removed. Real containment (the reset program, the
controls of a real daemon, bit-equal outputs) is the scratch-door run's evidence, not these tests'.
"""

import json
import re
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.reconstruction import grade_lanes
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

MEMBER = "DIRECT_BUNDLE_PUBLIC_INFERENCE"
IMAGE = SimpleNamespace(image_id="sha256:" + "2" * 64)


@pytest.fixture
def door(tmp_path, monkeypatch):
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "grade-session-fixture",
            "implementation": "fixture",
            "objective": "test-only",
            "sampling": "public-test-only",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    state = SimpleNamespace(
        ledger=ledger,
        live={},  # container name -> launch label
        created=[],  # (name, launch, input dir)
        started=[],
        removed=[],
        resets=[],
        programs=[],  # (container, exec argv, files seen at /input)
        controls=[],
        holds=[],
        active_holds=0,
        fail_program=set(),  # op identities whose program raises
        fail_reset=0,  # how many next resets refuse
        watchdogs=[],
        reapers=[],
    )

    class CLI:
        def run(self, arguments, **kwargs):
            command = arguments[0]
            if command == "create":
                _, name, launch, source = arguments
                assert name not in state.live
                state.live[name] = launch
                state.created.append((name, launch, Path(source)))
            elif command == "start":
                assert arguments[1] in state.live
                state.started.append(arguments[1])
            elif command == "exec":
                assert arguments[1] in state.live, "exec into a removed container"
                if arguments[-1] == carrier.SESSION_RESET:
                    state.resets.append(arguments[1])
                    if state.fail_reset:
                        state.fail_reset -= 1
                        raise WorkerFailure(WorkerCode.RUNTIME)
            elif command == "ps":
                name = arguments[-1].removeprefix("name=^").removesuffix("$")
                return SimpleNamespace(stdout=b"x" if name in state.live else b"")
            return SimpleNamespace(stdout=b"")

        def json(self, arguments, **kwargs):
            raise WorkerFailure(WorkerCode.UNAVAILABLE)

        def stream_to_file(self, arguments, destination, **kwargs):
            name = arguments[1]
            assert name in state.live, "exec into a removed container"
            if destination.name == "stdout.txt":
                launch = state.live[name]
                source = next(
                    src for n, lb, src in state.created if n == name and lb == launch
                )
                seen = {p.name: p.read_bytes() for p in sorted(source.iterdir())}
                identity = json.loads(seen["identity.txt"])
                state.programs.append((name, list(arguments), seen))
                if identity in state.fail_program:
                    raise WorkerFailure(WorkerCode.RUNTIME)
            destination.write_bytes(b"stream")
            return 6

    def remove(*, cli, container_name, launch_digest):
        if container_name in state.live:
            assert state.live[container_name] == launch_digest
            del state.live[container_name]
        state.removed.append((container_name, launch_digest))

    def controls(**kwargs):
        state.controls.append(kwargs)
        return "sha256:" + "1" * 64, {"input": str(kwargs["input_directory"])}

    @contextmanager
    def hold(*, identity=None, **kwargs):
        state.holds.append(identity)
        state.active_holds += 1
        try:
            yield None
        finally:
            state.active_holds -= 1

    def decode(source, target, **kwargs):
        target.mkdir()
        (target / "out.json").write_bytes(b"{}")

    monkeypatch.setattr(carrier, "DockerCLI", CLI)
    monkeypatch.setattr(
        carrier, "doctor", lambda **kwargs: SimpleNamespace(eligible=True, cpuset="0,1")
    )
    monkeypatch.setattr(
        carrier,
        "create_arguments",
        lambda **kw: [
            "create",
            kw["container_name"],
            kw["launch_digest"],
            str(kw["input_directory"]),
        ],
    )
    monkeypatch.setattr(
        carrier, "spawn_watchdog", lambda **kw: state.watchdogs.append(kw)
    )
    monkeypatch.setattr(
        carrier.liveness_reaper,
        "controller_guard",
        lambda: {"kind": "CONTROLLER_LIVENESS", "pid": 1, "identity": "fixture"},
    )
    monkeypatch.setattr(
        carrier.liveness_reaper,
        "spawn_liveness_reaper",
        lambda **kw: state.reapers.append(kw),
    )
    monkeypatch.setattr(carrier, "inspect_effective_controls", controls)
    monkeypatch.setattr(carrier, "observe_effective_resources", lambda **kw: {})
    monkeypatch.setattr(carrier, "remove_exact_container", remove)
    monkeypatch.setattr(carrier, "decode_output_stream", decode)
    monkeypatch.setattr(grade_lanes, "container_hold", hold)
    # The ledger lease is a POSIX flock (not this test's subject); reconcile takes it.
    monkeypatch.setattr(carrier, "_numerical_lease", lambda ledger: nullcontext())

    def run(identity, provenance=MEMBER, **overrides):
        return carrier._run_locked(
            ledger,
            **{
                "owner": "alice",
                "identity": identity,
                "source": "# fixed synthetic public program; never executed",
                "files": {
                    "identity.txt": json.dumps(identity).encode(),
                    "state.npz": b"state-" + identity.encode(),
                },
                "image": IMAGE,
                "seconds": 60,
                "provenance": provenance,
                "extra_resources": {"research_trials": 1},
                **overrides,
            },
        )

    state.run = run
    return state


def intent(door, result):
    return json.loads(
        (door.ledger.root / result["operation"] / "intent.json").read_bytes()
    )


def test_no_session_is_todays_path(door):
    """Outside `grade_session()` every op creates, starts and removes its own container, as today."""
    first, second = door.run("graded"), door.run("pair-primary")
    assert len(door.created) == 2 and door.resets == []
    for result, (name, launch, source) in zip((first, second), door.created):
        recorded = intent(door, result)
        assert "session" not in recorded
        assert name == recorded["container"] == "carbon-d4-" + recorded["launch"][7:31]
        assert source == door.ledger.root / result["operation"] / "input"
        assert (name, launch) in door.removed
    assert door.holds == [door_identity for door_identity in ("graded", "pair-primary")]
    assert door.live == {}
    assert not list(door.ledger.root.glob("session-*"))


def test_one_session_runs_every_member_op_in_one_container(door):
    with carrier.grade_session() as session:
        results = [door.run(i) for i in ("graded", "pair-primary", "pair-repeat")]
        assert len(door.live) == 1
        assert session.opened == 1
    # ONE create / start / hold for three ops; a reset before every op after the first.
    assert len(door.created) == 1 and len(door.started) == 1
    name, launch, source = door.created[0]
    assert name == carrier.SESSION_CONTAINER_PREFIX + launch[7:31]
    assert source.name == "input" and source.parent.name == "session-" + launch[7:]
    assert door.holds == ["grade-session-" + launch[7:]]
    assert door.resets == [name, name]
    # Its own deadline watchdog and controller-liveness reaper.
    assert [w["container_name"] for w in door.watchdogs] == [name]
    assert [r["container_name"] for r in door.reapers] == [name]
    # Every op keeps its own ledger operation and intent, naming the session container and its exec sequence.
    assert len({r["operation"] for r in results}) == 3
    for sequence, result in enumerate(results, start=1):
        recorded = intent(door, result)
        assert recorded["container"] == name
        assert recorded["session"] == {"launch": launch, "sequence": sequence}
        resources = json.loads(
            (door.ledger.root / result["operation"] / "resources.json").read_bytes()
        )
        assert resources["session"] == {
            "container": name,
            "sequence": sequence,
            "counters": "SESSION_CUMULATIVE",
        }
        assert (
            door.ledger.operation_state(recorded["identity"], owner="alice")
            == "SUCCEEDED"
        )
    # Controls are re-read per op against the session container and its input folder.
    assert [c["container_name"] for c in door.controls] == [name] * 3
    assert {c["launch_digest"] for c in door.controls} == {launch}
    assert {c["input_directory"] for c in door.controls} == {source}
    # Grade end: the container is removed (confirmed) and the session folder is gone.
    assert door.removed == [(name, launch)]
    assert door.live == {} and not source.parent.exists()
    assert door.active_holds == 0


def test_each_op_sees_only_its_own_inputs_and_todays_command(door):
    with carrier.grade_session():
        for identity in ("graded", "pair-primary", "pair-repeat"):
            door.run(identity)
    with_session = [(argv, seen) for _, argv, seen in door.programs]
    door.programs.clear()
    door.run("graded-today")  # today's own container, outside any session
    _, today_argv, today_seen = door.programs[0]
    for (argv, seen), identity in zip(
        with_session, ("graded", "pair-primary", "pair-repeat")
    ):
        # Exactly the op's own staged bytes at /input (nothing of an earlier op), and the same exec command line as
        # today's container, the container name aside.
        assert json.loads(seen["identity.txt"]) == identity
        assert seen["state.npz"] == b"state-" + identity.encode()
        assert set(seen) == set(today_seen)
        assert argv[0] == today_argv[0] == "exec"
        assert argv[2:] == today_argv[2:]
        assert argv[-1] == carrier.BOOTSTRAP
    assert today_seen["state.npz"] == b"state-graded-today"


def test_a_failed_op_removes_the_session_and_the_next_op_gets_a_new_one(door):
    door.fail_program.add("pair-primary")
    with carrier.grade_session() as session:
        door.run("graded")
        with pytest.raises(WorkerFailure):
            door.run("pair-primary")
        # Removed in that op's own cleanup, before its outcome: nothing of it is left for the next op.
        assert door.live == {}
        assert door.active_holds == 0
        # As today, the failed op is reconciled (the ledger runs one numerical worker at a time).
        carrier.reconcile_worker(door.ledger, owner="alice", identity="pair-primary")
        door.run("pair-repeat")
        assert session.opened == 2
    (first, first_launch, _), (second, second_launch, _) = door.created
    assert first != second and first_launch != second_launch
    assert door.removed[0] == (first, first_launch)
    assert door.removed[-1] == (second, second_launch)
    assert len(door.holds) == 2 and door.active_holds == 0
    # A new container needs no reset: it is a fresh container, as today.
    assert door.resets == [first]


def test_a_refused_reset_removes_the_container_and_the_op_runs_in_a_new_one(door):
    door.fail_reset = 1
    with carrier.grade_session() as session:
        door.run("graded")
        result = door.run("pair-primary")
        assert session.opened == 2
    (first, first_launch, _), (second, _, _) = door.created
    assert (first, first_launch) in door.removed
    assert intent(door, result)["container"] == second
    assert door.ledger.operation_state("pair-primary", owner="alice") == "SUCCEEDED"


def test_the_speed_stage_closes_the_session_and_keeps_its_own_container(door):
    with carrier.grade_session() as session:
        door.run("graded")
        assert door.active_holds == 1
        timed = door.run("single-call-abc")
        door.run("menu-rowcheck")
        assert session.opened == 2
    names = [name for name, _, _ in door.created]
    assert names[0].startswith(carrier.SESSION_CONTAINER_PREFIX)
    assert names[1] == intent(door, timed)["container"]
    assert names[1].startswith("carbon-d4-") and "session" not in intent(door, timed)
    assert names[2].startswith(carrier.SESSION_CONTAINER_PREFIX)
    # The session was removed, and its hold released, before the timing op asked for its own.
    first_removal = door.removed.index((names[0], door.created[0][1]))
    assert first_removal < door.removed.index((names[1], door.created[1][1]))
    assert door.holds[1] == "single-call-abc"


def test_the_exclusive_timing_context_also_closes_the_session(door):
    with carrier.grade_session():
        door.run("graded")
        with grade_lanes.timing_exclusive():
            result = door.run("timed")
        assert "session" not in intent(door, result)
    assert door.created[0][0] in [name for name, _ in door.removed]


def test_ops_that_are_not_members_keep_their_own_container(door):
    with carrier.grade_session():
        door.run("graded")
        other = door.run("practice", provenance="BATTERY_PUBLIC_PRACTICE")
        door.run("pair-primary")
    assert "session" not in intent(door, other)
    assert len(door.created) == 2  # the session (both members) + the practice op's own


@pytest.mark.parametrize("raised", [RuntimeError("grade failed"), KeyboardInterrupt()])
def test_grade_end_removes_everything_on_any_exit(door, raised):
    with pytest.raises(type(raised)), carrier.grade_session():
        door.run("graded")
        raise raised
    name, launch, source = door.created[0]
    assert door.removed == [(name, launch)]
    assert door.live == {} and not source.parent.exists()
    assert door.active_holds == 0
    assert carrier._GRADE_SESSION.get() is None


def test_sessions_never_nest_and_never_outlive_their_grade(door):
    with carrier.grade_session():
        with pytest.raises(ValueError), carrier.grade_session():
            pass
        door.run("graded")
    assert carrier._GRADE_SESSION.get() is None
    door.run("graded-next-grade")
    assert door.created[-1][0].startswith("carbon-d4-")


def test_an_op_that_would_outlive_the_session_starts_a_new_one(door, monkeypatch):
    with carrier.grade_session() as session:
        door.run("graded")
        monkeypatch.setattr(
            session,
            "deadline_unix",
            session.deadline_unix - carrier.SESSION_LIFETIME_SECONDS,
        )
        door.run("pair-primary")
        assert session.opened == 2
    assert len(door.removed) == 2


def test_reconcile_removes_the_session_container_an_op_intent_names(door, monkeypatch):
    door.fail_program.add("graded")

    def stuck(*, cli, container_name, launch_digest):
        raise WorkerFailure(WorkerCode.CLEANUP)

    with pytest.raises(WorkerFailure), carrier.grade_session():
        monkeypatch.setattr(carrier, "remove_exact_container", stuck)
        door.run("graded")
    assert door.ledger.operation_state("graded", owner="alice") == "RESERVED"
    name, launch, _ = door.created[0]
    seen = []
    monkeypatch.setattr(
        carrier,
        "remove_exact_container",
        lambda **kw: (
            seen.append((kw["container_name"], kw["launch_digest"])),
            door.live.pop(kw["container_name"], None),
        ),
    )
    result = carrier.reconcile_worker(door.ledger, owner="alice", identity="graded")
    assert result["state"] == "FAILED_INFRA"
    assert seen == [(name, launch)]


def test_intent_container_reads_both_forms_and_refuses_a_malformed_session():
    launch = "sha256:" + "a" * 64
    label = "sha256:" + "b" * 64
    assert carrier._intent_container({}, launch) == ("carbon-d4-" + "a" * 24, launch)
    assert carrier._intent_container({"session": {"launch": label}}, launch) == (
        carrier.SESSION_CONTAINER_PREFIX + "b" * 24,
        label,
    )
    for bad in ({"launch": "sha256:xyz"}, {"launch": None}, "x"):
        with pytest.raises(ValueError):
            carrier._intent_container({"session": bad}, launch)
    assert carrier._container_names(launch) == (
        "carbon-d4-" + "a" * 24,
        carrier.SESSION_CONTAINER_PREFIX + "a" * 24,
    )


def test_the_reset_rebuilds_exactly_what_the_image_entrypoint_makes():
    """The reset's /scratch layout is the image entrypoint's own (a new container's), and it refuses on residue."""
    compile(carrier.SESSION_RESET, "<reset>", "exec")
    entrypoint = (
        Path(carrier.__file__).parents[1]
        / "reconstruction"
        / "worker"
        / "entrypoint.py"
    ).read_text()
    made = re.search(r"for child in \(([^)]*)\)", entrypoint).group(1)
    assert [x.strip().strip('"') for x in made.split(",")] == [
        "home",
        "tmp",
        "cache",
        "jax-cache",
    ]
    assert (
        "for c in ('home','tmp','cache','jax-cache'): (s/c).mkdir(mode=0o700)"
        in carrier.SESSION_RESET
    )
    assert '(scratch / "control-ready").touch(mode=0o400' in entrypoint
    assert "(s/'control-ready').touch(mode=0o400)" in carrier.SESSION_RESET
    for refusal in (
        "sys.exit(3)",
        "sys.exit(4)",
        "sys.exit(5)",
        "sys.exit(6)",
        "sys.exit(7)",
        "sys.exit(8)",
    ):
        assert refusal in carrier.SESSION_RESET
    assert (
        "wipe('/scratch')" in carrier.SESSION_RESET
        and "wipe('/dev/shm')" in carrier.SESSION_RESET
    )
