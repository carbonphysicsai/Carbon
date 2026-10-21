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
#: The host's own home identity, as the carrier records it before launch.
HOME_IDENTITY = {"st_dev": 64768, "st_ino": 2228226}
HOST = {
    "proc1_comm": "systemd",
    "self_cgroup": "0::/user.slice/user-1000.slice\n",
    "home_identity": HOME_IDENTITY,
}
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
        "host_home_mounts": {"outcome": "ok", "matches": 0, "below_home": []},
        "host_home_identity": dict(ABSENT),
        "host_home_canary": dict(ABSENT),
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
    "host_home_mounted": (
        lambda o, d: o.update(host_home_mounts={"outcome": "ok", "matches": 1}),
        "host_home",
    ),
    "host_home_mounts_unreadable": (
        lambda o, d: o.update(host_home_mounts={"outcome": "denied"}),
        "host_home",
    ),
    "host_home_is_the_hosts_directory": (
        lambda o, d: o.update(
            host_home_identity={"outcome": "ok", "mode": "0o40750", **HOME_IDENTITY}
        ),
        "host_home",
    ),
    "host_home_canary_readable": (
        lambda o, d: o.update(host_home_canary={"outcome": "ok", "bytes": 61}),
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
            "home_canary_file": None,
            "network_target": list(cc.NETWORK_TARGET),
            "dns_name": cc.DNS_NAME,
            "write_targets": [*cc.WRITE_TARGETS, "/tmp/x"],
            "nonce": "00",
            "output_name": cc.OUTPUT_NAME,
        }
    )
    compile(source, "<cell>", "exec")
    assert "__DATA__" not in source and source.count(HOME) == 1
    # The cell reads no file under the home but the planted canary, and only the
    # mount count, the home's device and inode and the canary's digest leave it.
    assert ".profile" not in source and "listdir(home)" not in source


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
    # HOME does not exist here: no home canary could be planted, and none is claimed.
    assert data["home_canary_file"] is None
    assert report["home_canary"] == {"planted": False, "removed": True}


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


# -- the host-home probe: identity and mounts, not whether the path exists ---------------------
def _home_probe(observed, host=HOST):
    rows = cc.evaluate(
        observed,
        host,
        canary_digest="0" * 64,
        write_targets=["/", "/tmp", "/opt", "/input"],
    )
    return {r["probe"]: r["status"] for r in rows}["host_home"]


def _observed(**changes):
    return {
        "host_home_mounts": {"outcome": "ok", "matches": 0, "below_home": []},
        "host_home_identity": dict(ABSENT),
        "host_home_canary": dict(ABSENT),
        **changes,
    }


def test_the_images_own_home_of_the_same_name_passes():
    # The container sees a directory at the host home's path (an Ubuntu base ships
    # /home/ubuntu) with another device and inode, no mount of the host home, and no canary.
    own = {"outcome": "ok", "mode": "0o40750", "st_dev": 51, "st_ino": 537443}
    assert _home_probe(_observed(host_home_identity=own)) == "PASS"
    # The same inode number on another device is also not the host's directory.
    other_device = {**own, "st_ino": HOME_IDENTITY["st_ino"]}
    assert _home_probe(_observed(host_home_identity=other_device)) == "PASS"


def test_the_hosts_own_directory_fails_by_identity():
    same = {"outcome": "ok", "mode": "0o40750", **HOME_IDENTITY}
    assert _home_probe(_observed(host_home_identity=same)) == "FAIL"


def test_a_visible_home_whose_host_identity_is_unknown_fails_closed():
    visible = {"outcome": "ok", "mode": "0o40750", "st_dev": 51, "st_ino": 537443}
    assert (
        _home_probe(
            _observed(host_home_identity=visible), {**HOST, "home_identity": None}
        )
        == "FAIL"
    )
    # An absent or denied path needs no identity to be hidden.
    assert _home_probe(_observed(), {**HOST, "home_identity": None}) == "PASS"


def test_an_odd_stat_outcome_fails_closed():
    assert (
        _home_probe(_observed(host_home_identity={"outcome": "error", "errno": 5}))
        == "FAIL"
    )


def test_a_canary_that_was_not_planted_is_neutral_and_a_readable_one_fails():
    assert _home_probe(_observed(host_home_canary={"outcome": "not_planted"})) == "PASS"
    assert (
        _home_probe(_observed(host_home_canary={"outcome": "ok", "bytes": 1})) == "FAIL"
    )


def _mount_function(tmp_path, home, mountinfo, *, dev="8:1", root="/home/ubuntu"):
    """The cell's own home_mounts, run against a mountinfo text. ``dev`` and ``root`` are
    where the host home lives on its filesystem (dev None: unknown, plain paths)."""
    source = cc.cell_source({"host_home": home})
    start = source.index("def inside(")
    end = source.index("def home_identity(")
    info = tmp_path / "mountinfo"
    info.write_text(mountinfo)
    namespace = {
        "Path": lambda _path: info,
        "home": home,
        "hashlib": hashlib,
        "DATA": {"home_fs_dev": dev, "home_fs_root": root},
    }
    exec(source[start:end], namespace)  # noqa: S102 - the fixed cell, against a fixture
    return namespace["home_mounts"]()


MOUNTINFO = (
    "100 99 0:50 / / rw,relatime - overlay overlay rw\n"
    "101 100 0:51 / /scratch rw,nosuid - tmpfs tmpfs rw\n"
    # the carrier's own input mount: a source below the host home, at another point
    "102 100 8:1 /home/ubuntu/.carbon/ledger/operation-1/input /input ro - ext4 /dev/sda1 rw\n"
    "103 100 0:52 / /proc rw - proc proc rw\n"
)
INPUT_SOURCE = cc.source_digest(
    {"dev": "8:1", "root": "/home/ubuntu/.carbon/ledger/operation-1/input"}
)


@pytest.mark.parametrize(
    "extra,matches,below",
    [
        # only the carrier's own mount, listed by point and a digest of its source
        ("", 0, 1),
        # a bind of the whole home somewhere else
        ("104 100 8:1 /home/ubuntu /mnt/h ro - ext4 /dev/sda1 rw\n", 1, 1),
        # a mount at the home's own path, and one inside it
        ("104 100 8:1 /x /home/ubuntu ro - ext4 /dev/sda1 rw\n", 1, 1),
        ("104 100 8:1 /x /home/ubuntu/.carbon ro - ext4 /dev/sda1 rw\n", 1, 1),
        # a mount above it, and a bind of an ancestor, or of the whole filesystem
        ("104 100 8:1 /x /home ro - ext4 /dev/sda1 rw\n", 1, 1),
        ("104 100 8:1 /home /mnt/h ro - ext4 /dev/sda1 rw\n", 1, 1),
        ("104 100 8:1 / /host ro - ext4 /dev/sda1 rw\n", 1, 1),
        # another directory of the home: not a match, but listed and so not exempt
        ("104 100 8:1 /home/ubuntu/.ssh /mnt/s ro - ext4 /dev/sda1 rw\n", 0, 2),
        # unrelated: a sibling whose name starts the same, and another filesystem
        ("104 100 8:1 /home/ubuntu2 /mnt/o ro - ext4 /dev/sda1 rw\n", 0, 1),
        ("104 100 8:1 /x /home/ubuntu2 ro - ext4 /dev/sda1 rw\n", 0, 1),
        ("104 100 8:9 /home/ubuntu /mnt/h ro - ext4 /dev/sdb1 rw\n", 0, 1),
        ("104 100 8:9 / /mnt/h ro - ext4 /dev/sdb1 rw\n", 0, 1),
    ],
)
def test_the_cell_counts_mounts_that_show_the_host_home(
    tmp_path, extra, matches, below
):
    seen = _mount_function(tmp_path, "/home/ubuntu", MOUNTINFO + extra)
    assert seen["matches"] == matches and len(seen["below_home"]) == below
    assert {"point": "/input", "source": INPUT_SOURCE} in seen["below_home"]
    assert "ubuntu" not in json.dumps(seen["below_home"])  # points and digests only


def test_when_the_hosts_filesystem_is_unknown_plain_paths_decide(tmp_path):
    # No device: the root filesystem bind is not counted (the container's own root is "/"),
    # but a bind of the home or an ancestor still is.
    plain = {"dev": None, "root": "/home/ubuntu"}
    assert _mount_function(tmp_path, "/home/ubuntu", MOUNTINFO, **plain)["matches"] == 0
    bind = MOUNTINFO + "104 100 8:1 /home/ubuntu /mnt/h ro - ext4 /dev/sda1 rw\n"
    assert _mount_function(tmp_path, "/home/ubuntu", bind, **plain)["matches"] == 1


def test_fs_location_gives_the_device_and_the_path_inside_it(tmp_path):
    info = tmp_path / "mountinfo"
    info.write_text(
        "1 0 8:1 / / rw - ext4 /dev/sda1 rw\n"
        "2 1 8:2 /users /home rw - ext4 /dev/sda2 rw\n"
        "3 1 8:3 / /home/ubuntu/big rw - ext4 /dev/sda3 rw\n"
    )
    assert cc.fs_location("/home/ubuntu/.carbon/x", str(info)) == {
        "dev": "8:2",
        "root": "/users/ubuntu/.carbon/x",
    }
    assert cc.fs_location("/home/ubuntu/big/y", str(info)) == {
        "dev": "8:3",
        "root": "/y",
    }
    assert cc.fs_location("/etc/x", str(info)) == {"dev": "8:1", "root": "/etc/x"}
    # An unreadable mountinfo leaves plain paths.
    assert cc.fs_location("/home/ubuntu", str(tmp_path / "absent")) == {
        "dev": None,
        "root": "/home/ubuntu",
    }


def _mounts_probe(below, declared):
    observed = _observed(
        host_home_mounts={"outcome": "ok", "matches": 0, "below_home": below}
    )
    return _home_probe(observed, {**HOST, "declared_mounts": declared})


def test_only_the_carriers_declared_mount_sources_are_exempt():
    own = {"point": "/input", "source": INPUT_SOURCE}
    ssh = {
        "point": "/input",
        "source": cc.source_digest({"dev": "8:1", "root": "/home/ubuntu/.ssh"}),
    }
    assert _mounts_probe([own], [own]) == "PASS"
    assert _mounts_probe([], []) == "PASS"
    # An undeclared mount from under the home fails: another directory of the home, the
    # same source at another mount point, and anything when nothing is declared.
    assert _mounts_probe([ssh], [own]) == "FAIL"
    assert _mounts_probe([{**own, "point": "/mnt/x"}], [own]) == "FAIL"
    assert _mounts_probe([own], []) == "FAIL"
    assert (
        _home_probe(_observed(host_home_mounts={"outcome": "ok", "matches": 0}))
        == "FAIL"
    )


def test_the_home_canary_is_planted_readable_and_removed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    planted = cc.plant_home_canary(str(home))
    assert planted is not None and planted.parent == home
    assert planted.read_bytes().startswith(b"CARBON-CONTAINMENT-HOME-CANARY:")
    assert cc.remove_home_canary(planted) is True and list(home.iterdir()) == []
    # A home that cannot be written to plants nothing, and "nothing" is removed.
    assert cc.plant_home_canary(str(tmp_path / "absent")) is None
    assert cc.remove_home_canary(None) is True


def test_the_home_identity_is_recorded_from_the_host(tmp_path):
    status = os.stat(tmp_path)
    assert cc.home_identity(str(tmp_path)) == {
        "st_dev": status.st_dev,
        "st_ino": status.st_ino,
    }
    assert cc.home_identity(str(tmp_path / "absent")) is None


def test_a_home_canary_is_planted_for_the_cell_and_removed_end_to_end(
    tmp_path, monkeypatch
):
    install(monkeypatch, FakeDocker())
    home = tmp_path / "home"
    home.mkdir()
    parent = tmp_path / "canaries"
    parent.mkdir()
    report = cc.containment_check(
        root=tmp_path / "gate", image=IMAGE, canary_parent=parent, host_home=str(home)
    )
    assert report["status"] == "PASS", report
    assert report["home_canary"] == {"planted": True, "removed": True}
    assert list(home.iterdir()) == []
    data = cell_data(tmp_path / "gate" / report["operation"])
    assert Path(data["home_canary_file"]).parent == home


def test_a_home_canary_left_behind_fails_the_check(tmp_path, monkeypatch):
    install(monkeypatch, FakeDocker())
    monkeypatch.setattr(cc, "remove_home_canary", lambda planted: False)
    home = tmp_path / "home"
    home.mkdir()
    parent = tmp_path / "canaries"
    parent.mkdir()
    report = cc.containment_check(
        root=tmp_path / "gate", image=IMAGE, canary_parent=parent, host_home=str(home)
    )
    assert report["status"] == "FAIL" and report["reason"] == "home_canary_not_removed"


class DeclaredMountDocker(FakeDocker):
    """The cell reports a mount from under the home, as the lane's own /input is."""

    def __init__(self, source_of):
        super().__init__()
        self.source_of = source_of

    def stream_kept(self, arguments, operation, *, timeout):
        super().stream_kept(arguments, operation, timeout=timeout)
        output = operation / "scratch" / "output" / cc.OUTPUT_NAME
        observed = json.loads(output.read_text())
        observed["host_home_mounts"]["below_home"] = [
            {"point": "/input", "source": self.source_of(operation)}
        ]
        output.write_text(json.dumps(observed))


def test_the_lanes_own_input_mount_passes_and_any_other_source_fails(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        cc, "fs_location", lambda path, *_: {"dev": "8:1", "root": "/fs" + str(path)}
    )

    def own(operation):
        return cc.source_digest(
            {"dev": "8:1", "root": "/fs" + str(operation / "input")}
        )

    install(monkeypatch, DeclaredMountDocker(own))
    report, _ = check(tmp_path / "own")
    assert report["status"] == "PASS", report

    def elsewhere(operation):
        return cc.source_digest(
            {"dev": "8:1", "root": "/fs" + str(operation / "other")}
        )

    install(monkeypatch, DeclaredMountDocker(elsewhere))
    report, _ = check(tmp_path / "other")
    failing = [p["probe"] for p in report["probes"] if p["status"] == "FAIL"]
    assert report["status"] == "FAIL" and failing == ["host_home"]
