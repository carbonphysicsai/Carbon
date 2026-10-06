"""The carrier containment check (GRAPHITE-CARRIER-CONTAINMENT-01).

Claims tested:

- each probe's classification, directly: a contained observation passes every
  probe; each breach (the canary read or listed, the host's own PID 1, the
  host's cgroup, the host home visible, any network attempt succeeding, any
  write outside /scratch succeeding or missing) fails exactly its probe;
- end to end through the REAL carrier code (`run_script` -> `_run` ->
  `miner_container.create_arguments` -> the docker command sequence) with a
  recording Docker double standing where the daemon stands: a contained cell
  passes with the image id and the create arguments' digest reported; a
  breach fails the check; the probe targets are the planted canary and the
  generic home path, passed as data;
- fail closed: no Docker, no manifest, an image that does not verify, a
  carrier refusal, a cell that failed or wrote nothing are each a FAIL, typed
  `containment_check_unavailable` where the check could not run;
- the canary is removed on every path, failures included;
- the host process makes no network attempt while the check runs (the
  prelive's own network guard sees none);
- both gates wire it: `phase4 prelive`'s `carrier_containment` step is a
  phase-4 live-path blocker and fails closed without a manifest; the phase-3
  dry run reports `dry_run.carrier_containment` and exits nonzero unless it
  passes;
- one real-Docker run, only where Docker and the pinned image exist
  (`CARBON_ANALYSIS_IMAGE_MANIFEST`).

Mutations live in `test_carrier_containment_mutations.py`. Not security
acceptance.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import containment_check as cc
from carbon.development_session import miner_container, research_image
from carbon.development_session import research_carrier as carrier
from carbon.development_session.research_image import ResearchImageIdentity
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

IMAGE = ResearchImageIdentity(
    "sha256:" + "b" * 64, "sha256:" + "c" * 64, "sha256:" + "d" * 64
)
HOST = {"proc1_comm": "systemd", "self_cgroup": "0::/user.slice/user-1000.slice\n"}
HOME = "/home/<user>"
ABSENT = {"outcome": "absent"}
EROFS = {"outcome": "error", "type": "OSError", "errno": 30}
UNREACHABLE = {"outcome": "error", "type": "OSError", "errno": 101}


def cell_data(operation):
    """The data the check put into the cell, read back from the staged cell."""
    source = (operation / "input" / "program.py").read_text()
    (line,) = [x for x in source.splitlines() if x.startswith("DATA = json.loads(")]
    return json.loads(ast.literal_eval(line[len("DATA = json.loads(") : -1]))


def contained(data):
    return {
        "uid": 65532,
        "canary_read": dict(ABSENT),
        "canary_list": dict(ABSENT),
        "proc1_comm": {"outcome": "ok", "value": "python"},
        "self_cgroup": {"outcome": "ok", "value": "0::/\n"},
        "host_home_stat": dict(ABSENT),
        "host_home_list": dict(ABSENT),
        "host_home_read": dict(ABSENT),
        "network_tcp": dict(UNREACHABLE),
        "network_udp": dict(UNREACHABLE),
        "network_dns": {"outcome": "error", "type": "gaierror", "errno": -3},
        "writes": {
            target: (dict(ABSENT) if target == data["canary_dir"] else dict(EROFS))
            for target in data["write_targets"]
        },
    }


def _read_canary(observed, data):
    body = Path(data["canary_file"]).read_bytes()
    observed["canary_read"] = {
        "outcome": "ok",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


#: Each breach, and the one probe it must fail.
BREACHES = {
    "canary_read": (_read_canary, "canary_read"),
    "canary_listed": (
        lambda o, d: o.update(canary_list={"outcome": "ok", "entries": 1}),
        "canary_read",
    ),
    "host_init": (
        lambda o, d: o.update(proc1_comm={"outcome": "ok", "value": "systemd"}),
        "proc1_comm",
    ),
    "init_unreadable": (
        lambda o, d: o.update(proc1_comm={"outcome": "denied"}),
        "proc1_comm",
    ),
    "host_cgroup": (
        lambda o, d: o.update(
            self_cgroup={"outcome": "ok", "value": "0::/system.slice/docker-1.scope\n"}
        ),
        "self_cgroup",
    ),
    "host_home_visible": (
        lambda o, d: o.update(host_home_stat={"outcome": "ok", "mode": "0o40750"}),
        "host_home",
    ),
    "host_home_listed": (
        lambda o, d: o.update(host_home_list={"outcome": "ok", "entries": 3}),
        "host_home",
    ),
    "tcp_connected": (
        lambda o, d: o.update(network_tcp={"outcome": "ok"}),
        "network",
    ),
    "udp_sent": (lambda o, d: o.update(network_udp={"outcome": "ok"}), "network"),
    "dns_resolved": (
        lambda o, d: o.update(network_dns={"outcome": "ok", "addresses": 2}),
        "network",
    ),
    "root_written": (
        lambda o, d: o["writes"].update({"/": {"outcome": "ok"}}),
        "write_outside_scratch",
    ),
    "canary_dir_written": (
        lambda o, d: o["writes"].update({d["canary_dir"]: {"outcome": "ok"}}),
        "write_outside_scratch",
    ),
    "write_probe_missing": (
        lambda o, d: o["writes"].pop("/tmp"),
        "write_outside_scratch",
    ),
}


def _data(tmp_path):
    directory = tmp_path / "canary-dir"
    directory.mkdir(exist_ok=True)
    canary = directory / "canary.txt"
    canary.write_bytes(b"CARBON-CONTAINMENT-CANARY:test")
    return {
        "canary_file": str(canary),
        "canary_dir": str(directory),
        "write_targets": [*cc.WRITE_TARGETS, str(directory)],
    }, hashlib.sha256(canary.read_bytes()).hexdigest()


def _evaluate(observed, data, canary_digest):
    return {
        p["probe"]: p["status"]
        for p in cc.evaluate(
            observed,
            HOST,
            canary_digest=canary_digest,
            write_targets=data["write_targets"],
        )
    }


# -- each probe's classification -----------------------------------------------------------
def test_a_contained_observation_passes_every_probe(tmp_path):
    data, canary_digest = _data(tmp_path)
    statuses = _evaluate(contained(data), data, canary_digest)
    assert list(statuses) == list(cc.PROBES)
    assert set(statuses.values()) == {"PASS"}


@pytest.mark.parametrize("breach", sorted(BREACHES))
def test_each_breach_fails_exactly_its_probe(tmp_path, breach):
    data, canary_digest = _data(tmp_path)
    observed = contained(data)
    mutate, probe = BREACHES[breach]
    mutate(observed, data)
    statuses = _evaluate(observed, data, canary_digest)
    assert statuses[probe] == "FAIL"
    assert {k for k, v in statuses.items() if v == "FAIL"} == {probe}


def test_a_canary_read_fails_its_probe(tmp_path):
    data, canary_digest = _data(tmp_path)
    observed = contained(data)
    _read_canary(observed, data)
    probes = cc.evaluate(
        observed, HOST, canary_digest=canary_digest, write_targets=data["write_targets"]
    )
    row = probes[0]
    assert row["probe"] == "canary_read" and row["status"] == "FAIL"
    assert row["observed"]["marker_matched"] is True


def test_the_hosts_own_init_fails_its_probe(tmp_path):
    data, canary_digest = _data(tmp_path)
    observed = contained(data)
    observed["proc1_comm"] = {"outcome": "ok", "value": HOST["proc1_comm"]}
    assert _evaluate(observed, data, canary_digest)["proc1_comm"] == "FAIL"
    # An unreadable host PID 1 cannot be compared: it fails closed too.
    host = {**HOST, "proc1_comm": None}
    rows = cc.evaluate(
        contained(data),
        host,
        canary_digest=canary_digest,
        write_targets=data["write_targets"],
    )
    assert {r["probe"]: r["status"] for r in rows}["proc1_comm"] == "FAIL"


def test_a_network_success_fails_its_probe(tmp_path):
    data, canary_digest = _data(tmp_path)
    for name in ("network_tcp", "network_udp", "network_dns"):
        observed = contained(data)
        observed[name] = {"outcome": "ok"}
        assert _evaluate(observed, data, canary_digest)["network"] == "FAIL", name


def test_a_missing_or_malformed_observation_fails_every_probe(tmp_path):
    data, canary_digest = _data(tmp_path)
    for observed in (None, {}, {"canary_read": "absent"}):
        assert set(_evaluate(observed, data, canary_digest).values()) == {"FAIL"}


def test_the_cell_takes_its_targets_as_data_only(tmp_path):
    source = cc.cell_source(
        {
            "canary_file": "/tmp/x/canary.txt",
            "canary_dir": "/tmp/x",
            "host_home": HOME,
            "network_target": list(cc.NETWORK_TARGET),
            "dns_name": cc.DNS_NAME,
            "write_targets": [*cc.WRITE_TARGETS, "/tmp/x"],
            "nonce": "00",
            "output_name": cc.OUTPUT_NAME,
        }
    )
    compile(source, "<cell>", "exec")
    assert "__DATA__" not in source and source.count(HOME) == 1
    # The only host file the cell reads under the home is a generic shell
    # profile, and only its length leaves the cell.
    assert 'len(Path(home, ".profile").read_bytes())' in source


# -- end to end through the real carrier code, Docker replaced ----------------------------
class FakeDocker:
    """Records every command; the cell 'runs' as a host callback that writes
    the observation the containment cell would."""

    def __init__(self, *, breach=None, absent=False, stream_error=None, output=True):
        self.breach, self.absent = breach, absent
        self.stream_error, self.output = stream_error, output
        self.commands = []

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        self.commands.append(list(arguments))
        return SimpleNamespace(stdout=b"", stderr=b"", returncode=0)

    def json(self, arguments, *, timeout=30):
        self.commands.append(list(arguments))
        if self.absent:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        if arguments[0] == "version":
            return {"Version": "fake"}
        return {"Running": True, "OOMKilled": False}

    def stream_kept(self, arguments, operation, *, timeout):
        self.commands.append(list(arguments))
        (operation / "stdout.txt").write_bytes(b"containment cell complete\n")
        (operation / "stderr.txt").write_bytes(b"")
        if self.stream_error is not None:
            raise self.stream_error
        output = operation / "scratch" / "output"
        output.mkdir(exist_ok=True)
        if self.output:
            data = cell_data(operation)
            observed = contained(data)
            if self.breach is not None:
                BREACHES[self.breach][0](observed, data)
            (output / cc.OUTPUT_NAME).write_text(json.dumps(observed))

    def created(self):
        return [c for c in self.commands if c and c[0] == "create"]


def install(monkeypatch, fake, removed=None):
    removed = [] if removed is None else removed
    monkeypatch.setattr(carrier, "DockerCLI", lambda: fake)
    monkeypatch.setattr(
        carrier, "doctor", lambda **kwargs: SimpleNamespace(eligible=True, cpuset="0")
    )
    monkeypatch.setattr(research_image, "verify_image", lambda image, cli: image)
    monkeypatch.setattr(carrier, "spawn_watchdog", lambda **kwargs: None)
    monkeypatch.setattr(
        carrier,
        "remove_exact_container",
        lambda **kwargs: removed.append(kwargs["container_name"]),
    )
    monkeypatch.setattr(
        miner_container,
        "inspect_isolation",
        lambda cli, run: {"lane": miner_container.LANE, "network": "none"},
    )
    monkeypatch.setattr(cc, "host_view", lambda: dict(HOST))
    return removed


def check(tmp_path, **kwargs):
    parent = tmp_path / "canaries"
    parent.mkdir(parents=True, exist_ok=True)
    return (
        cc.containment_check(
            root=tmp_path / "gate",
            image=IMAGE,
            canary_parent=parent,
            host_home=HOME,
            **kwargs,
        ),
        parent,
    )


def test_a_contained_cell_passes_through_the_real_carrier(tmp_path, monkeypatch):
    fake = FakeDocker()
    removed = install(monkeypatch, fake)
    report, parent = check(tmp_path)
    assert report["status"] == "PASS" and report["code"] is None, report
    assert [p["probe"] for p in report["probes"]] == list(cc.PROBES)
    assert {p["status"] for p in report["probes"]} == {"PASS"}
    assert report["image_id"] == IMAGE.image_id
    assert report["create_arguments_digest"].startswith("sha256:")
    assert report["canary"]["removed"] is True and list(parent.iterdir()) == []
    # The lane's own fixed create arguments, the run's container removed.
    (create,) = fake.created()
    assert create[create.index("--network") + 1] == "none"
    assert "--read-only" in create and create[-1] == IMAGE.image_id
    assert f"org.opencontainers.image.carbon.lane={miner_container.LANE}" in create
    assert removed == [create[create.index("--name") + 1]]
    # The digest is of exactly those arguments.
    from carbon.development_session.profile import canonical, digest

    assert report["create_arguments_digest"] == digest(canonical(create))
    # The probe targets were the planted canary and the generic home path.
    operation = tmp_path / "gate" / report["operation"]
    data = cell_data(operation)
    assert Path(data["canary_file"]).parent.parent == parent
    assert data["host_home"] == HOME


@pytest.mark.parametrize("breach", ["canary_read", "host_init", "tcp_connected"])
def test_a_breach_fails_the_check_end_to_end(tmp_path, monkeypatch, breach):
    install(monkeypatch, FakeDocker(breach=breach))
    report, parent = check(tmp_path)
    assert report["status"] == "FAIL" and report["code"] == cc.FAILED
    failing = [p["probe"] for p in report["probes"] if p["status"] == "FAIL"]
    assert failing == [BREACHES[breach][1]]
    assert report["canary"]["removed"] is True and list(parent.iterdir()) == []


def test_no_docker_fails_closed_typed(tmp_path, monkeypatch):
    fake = FakeDocker(absent=True)
    install(monkeypatch, fake)
    report, parent = check(tmp_path)
    assert report["status"] == "FAIL" and report["code"] == cc.UNAVAILABLE
    assert report["reason"] == "docker_unavailable"
    assert fake.created() == [] and list(parent.iterdir()) == []


def test_a_missing_docker_binary_fails_closed_typed(tmp_path, monkeypatch):
    class NoBinary(FakeDocker):
        def json(self, arguments, *, timeout=30):
            raise FileNotFoundError("docker")

    fake = NoBinary()
    install(monkeypatch, fake)
    report, parent = check(tmp_path)
    assert report["status"] == "FAIL" and report["code"] == cc.UNAVAILABLE
    assert report["reason"] == "docker_unavailable"
    assert fake.created() == [] and list(parent.iterdir()) == []


def test_no_manifest_or_an_unreadable_one_fails_closed(tmp_path):
    report = cc.containment_check(root=tmp_path / "gate", manifest=None)
    assert (report["status"], report["code"], report["reason"]) == (
        "FAIL",
        cc.UNAVAILABLE,
        "analysis_image_manifest_not_given",
    )
    bad = tmp_path / "analysis-image.json"
    bad.write_text("{}")
    report = cc.containment_check(root=tmp_path / "gate", manifest=bad)
    assert report["reason"] == "analysis_image_manifest_unreadable"
    assert report["status"] == "FAIL"


def test_an_image_that_does_not_verify_fails_closed(tmp_path, monkeypatch):
    fake = FakeDocker()
    install(monkeypatch, fake)

    def refuse(image, cli):
        raise ValueError("analysis image identity differs")

    monkeypatch.setattr(research_image, "verify_image", refuse)
    report, parent = check(tmp_path)
    assert report["code"] == cc.UNAVAILABLE
    assert report["reason"] == "pinned_image_unavailable"
    assert fake.created() == [] and list(parent.iterdir()) == []


def test_the_canary_is_removed_even_when_the_run_fails(tmp_path, monkeypatch):
    # An infrastructure failure inside the carrier: typed, canary gone.
    install(
        monkeypatch,
        FakeDocker(
            stream_error=WorkerFailure(
                WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
            )
        ),
    )
    report, parent = check(tmp_path)
    assert report["status"] == "FAIL" and report["code"] == cc.UNAVAILABLE
    assert report["reason"] == "carrier_run_failed"
    assert report["canary"]["removed"] is True
    assert list(parent.iterdir()) == []


def test_the_canary_is_removed_when_the_check_is_interrupted(tmp_path, monkeypatch):
    install(monkeypatch, FakeDocker(stream_error=KeyboardInterrupt()))
    parent = tmp_path / "canaries"
    parent.mkdir()
    with pytest.raises(KeyboardInterrupt):
        cc.containment_check(
            root=tmp_path / "gate", image=IMAGE, canary_parent=parent, host_home=HOME
        )
    assert list(parent.iterdir()) == []


def test_a_cell_that_failed_or_wrote_nothing_fails(tmp_path, monkeypatch):
    install(
        monkeypatch,
        FakeDocker(
            stream_error=WorkerFailure(
                WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nstderr:\n"
            )
        ),
    )
    report, parent = check(tmp_path)
    assert report["status"] == "FAIL" and report["reason"] == "containment_cell_failed"
    assert report["observation"] == "NONZERO_EXIT"
    assert list(parent.iterdir()) == []
    install(monkeypatch, FakeDocker(output=False))
    report, parent = check(tmp_path / "again")
    assert report["status"] == "FAIL" and report["reason"] == "cell_output_missing"
    assert {p["status"] for p in report["probes"]} == {"FAIL"}


def test_a_canary_left_behind_fails_the_check(tmp_path, monkeypatch):
    install(monkeypatch, FakeDocker())
    monkeypatch.setattr(cc, "remove_canary", lambda directory: False)
    report, _ = check(tmp_path)
    assert report["status"] == "FAIL" and report["reason"] == "canary_not_removed"


def test_the_host_process_makes_no_network_attempt(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite.phase4_prelive import network_guard

    install(monkeypatch, FakeDocker())
    with network_guard() as attempts:
        report, _ = check(tmp_path)
    assert report["status"] == "PASS" and attempts == []


# -- the gates --------------------------------------------------------------------------------
def test_the_prelive_step_is_a_phase4_blocker_and_fails_closed(tmp_path, monkeypatch):
    from test_graphite_phase4 import _synthetic_adapter
    from test_graphite_phase4_prelive import SCORING, _committed_by_digest, _grant_copy

    from carbon.agent_campaign.graphite import phase4
    from carbon.agent_campaign.graphite import phase4_prelive as prelive
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    copy = _grant_copy(tmp_path)
    _committed_by_digest(monkeypatch, copy)
    refused = tmp_path / "refused.json"
    refused.write_text(
        json.dumps({**json.loads(copy.read_bytes()), "monetary_ceiling": "100.00"})
    )
    printed = []
    code = prelive.prelive(
        tmp_path / "root",
        _synthetic_adapter(weak=False),
        phase4.attack_modules(),
        grant_path=refused,  # stops the gate after its first two steps
        challenge=BATTERY_CHALLENGE,
        emit=printed.append,
        scoring=SCORING,
    )
    report = json.loads(printed[-1])
    rows = {row["path"]: row for row in report["paths"]}
    step = rows[prelive.CONTAINMENT_STEP]
    assert report["paths"][0]["path"] == prelive.CONTAINMENT_STEP
    assert step["status"] == "FAIL" and step["phase4_live_path"] is True
    assert step["detail"]["error"] == "ContainmentNotPassed"
    assert report["carrier_containment"]["code"] == cc.UNAVAILABLE
    assert report["carrier_containment"]["reason"] == (
        "analysis_image_manifest_not_given"
    )
    blocking = {f["path"]: f for f in report["blocking_findings"]}
    assert blocking[prelive.CONTAINMENT_STEP]["blocks_phase4_live_run"] is True
    assert report["verdict"] == "FAIL" and report["phase4_live_path"] == "FAIL"
    assert code == 4 and report["network_attempts"] == []


def test_the_prelive_step_passes_on_a_passing_check(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite import phase4_prelive as prelive

    install(monkeypatch, FakeDocker())
    seen = {}
    real = cc.containment_check

    def through(*, root, manifest):
        seen["manifest"] = manifest
        return real(root=root, image=IMAGE, canary_parent=tmp_path, host_home=HOME)

    monkeypatch.setattr(cc, "containment_check", through)
    with prelive.network_guard() as attempts, prelive.sqlite_thread_guard() as uses:
        gate = prelive._Gate(uses)
        ok, detail = gate.check(
            prelive.CONTAINMENT_STEP,
            ("the step",),
            lambda: prelive.carrier_containment(tmp_path, "pinned.json"),
        )
    assert ok, detail
    assert detail["status"] == "PASS" and seen["manifest"] == "pinned.json"
    assert attempts == [] and uses.cross_thread == []


def test_the_phase3_dry_run_exits_nonzero_unless_containment_passes(tmp_path, capsys):
    from carbon.agent_campaign.graphite import phase3
    from carbon.challenge_validator import scoring as challenge_scoring
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    scoring = challenge_scoring.scoring_for(BATTERY_CHALLENGE)
    code = phase3.dry_run(tmp_path, scoring)
    printed = capsys.readouterr().out
    report = json.loads(printed[printed.index("{\n") :])
    containment = report["dry_run"]["carrier_containment"]
    assert containment["status"] == "FAIL" and containment["code"] == cc.UNAVAILABLE
    # Everything else in the dry run passed: the containment check alone
    # makes it exit nonzero.
    assert report["provider_state"] == "succeeded"
    assert report["dry_run"]["real_pod_path"]["status"] == "OK"
    assert report["dry_run"]["pod_failure_path"]["status"] == "OK"
    assert code == 4


def test_the_phase3_dry_run_passes_its_manifest_to_the_check(tmp_path, monkeypatch):
    from containment_double import passing_report

    from carbon.agent_campaign.graphite import phase3

    seen = []

    def recording(*, root, manifest=None):
        seen.append(manifest)
        return passing_report(root=root, manifest=manifest)

    monkeypatch.setattr(cc, "containment_check", recording)
    out = io.StringIO()
    with redirect_stdout(out):
        from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

        code = phase3.main(
            [
                "run",
                "--root",
                str(tmp_path / "r"),
                "--challenge",
                BATTERY_CHALLENGE,
                "--dry-run",
                "--analysis-image-manifest",
                "pinned.json",
            ]
        )
    assert code == 0 and seen == ["pinned.json"]


# -- the real lane ---------------------------------------------------------------------------
REAL_MANIFEST = os.environ.get("CARBON_ANALYSIS_IMAGE_MANIFEST")


@pytest.mark.skipif(
    not (REAL_MANIFEST and shutil.which("docker")),
    reason="needs Docker and CARBON_ANALYSIS_IMAGE_MANIFEST (the pinned image); "
    "the gates themselves still fail closed without them",
)
def test_the_real_lane_contains_the_cell(tmp_path):
    from carbon.agent_campaign.graphite.phase4_prelive import network_guard

    with network_guard() as attempts:
        report = cc.containment_check(root=tmp_path / "gate", manifest=REAL_MANIFEST)
    assert report["status"] == "PASS", json.dumps(report, indent=1)
    assert {p["status"] for p in report["probes"]} == {"PASS"}
    assert report["canary"]["removed"] is True
    assert not Path(report["canary"]["planted_in"]).joinpath("canary.txt").exists()
    assert attempts == []
