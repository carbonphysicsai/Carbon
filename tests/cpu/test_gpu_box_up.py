"""One-command GPU box bring-up (scripts/dev/gpu_box_up.py), driven against a fake box.

Claims: a box that passes every step gets exactly one box file with exactly the documented fields, 0600 in a 0700
directory; every failure is a typed stop that leaves no box file (a stale one is removed); the host key is pinned;
the slot shape is checked; the class check must repeat on the GPU under allowlist v8, match the class record's
digests and reproduce the class's ops record; daemon.json keeps the snapshotter and the nvidia runtime;
authorized_keys is exactly one line; nothing but public material reaches the box; a dry run runs nothing.
It also documents the limit: a box that replays another box's output passes (PASS is not security qualification).
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import itertools
import json
import os
import shlex
import stat
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/gpu_box_up.py"
spec = importlib.util.spec_from_file_location("gpu_box_up", SCRIPT)
box_up = importlib.util.module_from_spec(spec)
sys.modules["gpu_box_up"] = box_up
spec.loader.exec_module(box_up)

KIND = "NVIDIA A100-SXM4-40GB"
UUID = "GPU-0123abcd-4567-89ab-cdef-0123456789ab"
DRIVER = "580.95.05"
IP = "203.0.113.7"
DOOR = "198.51.100.2"
HEAD = "c" * 40
JAX = "sha256:" + "a" * 64
TORCH = "sha256:" + "b" * 64


def _key_body(seed: int) -> str:
    blob = (
        len(b"ssh-ed25519").to_bytes(4, "big")
        + b"ssh-ed25519"
        + (32).to_bytes(4, "big")
        + bytes((seed + i) % 256 for i in range(32))
    )
    return base64.b64encode(blob).decode()


HOST_KEY = _key_body(1)
HOST_FINGERPRINT = "SHA256:" + base64.b64encode(
    hashlib.sha256(base64.b64decode(HOST_KEY)).digest()
).decode().rstrip("=")
LANE_PUBKEY = f"ssh-ed25519 {_key_body(7)} lane@door"


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _class_record(
    digests: dict, *, seconds=1.0, identical=None, on_gpu=True, cpu="sha256:" + "c" * 64
):
    cases = []
    for name, digest in digests.items():
        kind, rest = name.split(":")
        key, arch = rest.split("/")
        same = True if identical is None else identical.get(name, True)
        cases.append(
            {
                "kind": kind,
                "key": key,
                "arch": arch,
                "bit_identical": same,
                "state_digest": digest if same else None,
                "ran_on_gpu": on_gpu,
                "ops": ["dot_general", "tanh"],
                "cpu_state_digest": cpu,
                "parity_vs_cpu": {"max_abs": 1e-6, "rows": 64},
                "rebuilds": [
                    {
                        "state_digest": digest,
                        "predictions_digest": _sha(f"{name} {digest}".encode()),
                        "backend": "gpu",
                        "seconds": seconds + index,
                    }
                    for index in range(2)
                ],
            }
        )
    all_same = all(c["bit_identical"] for c in cases)
    return {
        "schema": "carbon.gpu-rebuild.class-check.v1",
        "nvidia_smi": {"gpus": [f"{KIND}, {DRIVER}, 40960 MiB, 8.0"], "returncode": 0},
        "steps": 512,
        "cases": cases,
        "all_bit_identical": all_same,
        "all_on_gpu": on_gpu,
        "verdict": (
            "GPU_REPEATS" if all_same and on_gpu else "NOT_REPEATABLE_OR_NOT_GPU"
        ),
    }


def _ops_record(record, *, allowlist=None, ops=("dot_general", "tanh")):
    return {
        "schema": "carbon.graph-gpu-ops.v1",
        "allowlist_digest": allowlist or box_up._allowlist_v8_digest(),
        "class_record_digest": _sha(json.dumps(record, sort_keys=True).encode()),
        "ops": sorted(ops),
    }


DIGESTS = {
    "graph:f08/mlp": "sha256:" + "1" * 64,
    "graph:f08/conv": "sha256:" + "2" * 64,
    "graph:motor/softmax": "sha256:" + "3" * 64,
}


def _device_document():
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return {
        "schema": "carbon.accelerator-host-device.v1",
        "record_id": "a100-1",
        "workload_profile_id": GPU_PROFILE.profile_id,
        "device_uuid": UUID,
        "device_kind": KIND,
        "driver_version": DRIVER,
        "driver_model": "N/A",
        "compute_capability": "8.0",
        "device_memory_mib": 40960,
        "display_active": "Disabled",
        "platform": "LINUX_VIRTUAL_MACHINE",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "lambda",
        "observed_at_unix": 1763300000.0,
        "observation_provenance": "vendor query tool at nvidia-smi, run by the operator",
        "observation_authority": "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION",
    }


def _printed_text(command: str) -> str:
    """The text a write_file_script command writes (the argument after ``printf '%s'``)."""
    words = shlex.split(shlex.split(command)[4])
    return words[words.index("printf") + 2]


class FakeBox:
    """A fresh Ubuntu box with an A100, reached only through the runner. Every command it does not know fails the test."""

    def __init__(self, cfg, **state):
        self.cfg = cfg
        self.calls = []
        self.keyscan = f"{IP} ssh-ed25519 {HOST_KEY}\n"
        self.nproc = 30
        self.online = "0-29"
        self.on_main = True
        self.extracts = 0
        self.mem_kib = 216 * 1024 * 1024
        self.smi = (0, f"{KIND}, {UUID}, 40960 MiB, {DRIVER}\n")
        self.driver_installs = 0
        self.docker = ""
        self.ctk = False
        self.daemon = '{\n  "log-driver": "json-file"\n}\n'
        self.daemon_live = None
        self.restarts = 0
        self.lane_uid = ""
        self.groups = ["carbon-grade"]
        self.authorized_keys = ""
        self.stage = "carbon-grade:carbon-grade 755 directory"
        self.loaded = {}
        self.load_as = {}
        self.tree = False
        self.device = json.dumps(_device_document(), sort_keys=True)
        record = _class_record(DIGESTS, seconds=2.5)
        self.class_rc = 0
        self.class_output = json.dumps(record, indent=1, sort_keys=True) + "\n"
        self.class_ops = json.dumps(
            _ops_record(record), sort_keys=True, separators=(",", ":")
        )
        self.__dict__.update(state)

    def __call__(self, argv, pipe_from=None):
        self.calls.append((list(argv), pipe_from))
        if argv[0] == "ssh-keyscan":
            assert argv == ["ssh-keyscan", "-t", "ed25519", "-p", "22", IP]
            return 0, self.keyscan, ""
        if argv[:3] == ["git", "-C", str(box_up.ROOT)]:
            if argv == box_up.cmd_git_on_main(HEAD):
                return (0, "", "") if self.on_main else (1, "", "")
            assert argv[3:] == ["rev-parse", "HEAD"]
            return 0, HEAD + "\n", ""
        assert argv[0] == "ssh" and "StrictHostKeyChecking=yes" in argv
        known = next(a for a in argv if a.startswith("UserKnownHostsFile="))
        pinned = Path(known.split("=", 1)[1]).read_text()
        assert pinned == f"{IP} ssh-ed25519 {HOST_KEY}\n"
        assert argv[-3:-1] == [f"ubuntu@{IP}", "--"]
        return self.remote(argv[-1], pipe_from)

    def remote(self, cmd, pipe_from):
        g, cfg = box_up, self.cfg
        if cmd == g.CMD_SHAPE:
            return 0, f"{self.nproc}\n{self.online}\nMemTotal: {self.mem_kib} kB\n", ""
        if cmd == g.CMD_DRIVER_QUERY:
            return (*self.smi, "")
        if cmd == g.cmd_driver_install(cfg.driver_package):
            self.driver_installs += 1
            return 0, "", ""
        if cmd == g.CMD_DOCKER_VERSION:
            return 0, self.docker + ("\n" if self.docker else ""), ""
        if cmd == g.cmd_docker_install(cfg.docker_version):
            self.docker = cfg.docker_version
            return 0, "", ""
        if cmd == g.CMD_CTK_PRESENT:
            return 0, "/usr/bin/nvidia-ctk\n" if self.ctk else "", ""
        if cmd == g.CMD_TOOLKIT_INSTALL:
            self.ctk = True
            return 0, "", ""
        if cmd == g.CMD_DAEMON_READ:
            return 0, self.daemon, ""
        if cmd == g.CMD_CTK_CONFIGURE:
            value = json.loads(self.daemon) if self.daemon.strip() else {}
            value.setdefault("runtimes", {})["nvidia"] = {
                "args": [],
                "path": "nvidia-container-runtime",
            }
            self.daemon = json.dumps(value, indent=4)
            return 0, "", ""
        if cmd.startswith("sudo -n sh -c ") and "/etc/docker/daemon.json.part" in cmd:
            self.daemon = _printed_text(cmd)
            return 0, "", ""
        if cmd == g.CMD_DOCKER_RESTART:
            self.restarts += 1
            self.daemon_live = json.loads(self.daemon)
            return 0, "", ""
        if cmd == g.CMD_DOCKER_INFO:
            live = self.daemon_live or {}
            snapshotter = (live.get("features") or {}).get("containerd-snapshotter")
            driver = "io.containerd.snapshotter.v1" if snapshotter else "overlay2"
            return (
                0,
                json.dumps(
                    {
                        "ServerVersion": self.docker,
                        "DriverStatus": [["driver-type", driver]],
                        "Runtimes": {"runc": {}, **(live.get("runtimes") or {})},
                    }
                ),
                "",
            )
        if cmd == g.CMD_LANE_UID:
            return 0, self.lane_uid, ""
        if cmd == g.CMD_LANE_CREATE:
            self.lane_uid = "1001"
            return 0, "", ""
        if cmd == g.CMD_LANE_GROUP:
            self.groups.append("docker")
            return 0, "", ""
        if cmd == g.CMD_LANE_ID:
            return 0, f"{self.lane_uid}\n{' '.join(self.groups)}\n", ""
        if (
            cmd.startswith("sudo -n sh -c ")
            and "printf" in cmd
            and "authorized_keys" in cmd
        ):
            self.authorized_keys = _printed_text(cmd)
            return 0, "", ""
        if cmd == g.CMD_AUTHORIZED_KEYS_READ:
            return 0, self.authorized_keys, ""
        if cmd == g.CMD_STAGE_ROOT:
            return 0, "", ""
        if cmd == g.CMD_STAGE_ROOT_STAT:
            return 0, self.stage + "\n", ""
        if cmd.startswith("sudo -n docker image inspect"):
            image = shlex.split(cmd)[7]
            return 0, (self.loaded.get(image, "") + "\n"), ""
        if cmd == g.CMD_DOCKER_LOAD:
            assert pipe_from[:2] == ["docker", "save"]
            image = pipe_from[2]
            self.loaded[image] = self.load_as.get(image, image)
            return 0, "Loaded image ID: " + image + "\n", ""
        if cmd == g.cmd_work_dir(cfg):
            return 0, "", ""
        if cmd == g.CMD_TREE_EXTRACT:
            assert pipe_from == g.cmd_git_archive(HEAD)
            self.tree = True
            self.extracts += 1
            return 0, "", ""
        if cmd == g.cmd_prepare(cfg):
            return 0, "{}", ""
        if cmd == g.CMD_DEVICE_READ:
            return 0, self.device, ""
        if cmd == g.CMD_CLASS_OUT:
            return 0, "", ""
        if cmd == g.cmd_class_check(cfg, UUID):
            return self.class_rc, "", ""
        if cmd == g.CMD_CLASS_OUTPUT_READ:
            return 0, self.class_output, ""
        if cmd == g.CMD_CLASS_OPS_READ:
            return 0, self.class_ops, ""
        raise AssertionError(f"unexpected remote command: {cmd}")

    def remote_commands(self):
        return [argv[-1] for argv, _ in self.calls if argv[0] == "ssh"]


def _manifest(image=JAX, lock=None):
    from carbon.reconstruction.accelerators import GPU_PROFILE

    return {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": image,
        "config_digest": image,
        "source_tree_digest": "sha256:" + "1" * 64,
        "wheel_digest": "sha256:" + "2" * 64,
        "lock_digest": lock or GPU_PROFILE.environment_lock_digest,
        "base_image_digest": "sha256:" + "3" * 64,
        "build_recipe_digest": "sha256:" + "4" * 64,
        "entrypoint_digest": "sha256:" + "5" * 64,
    }


def _argv(tmp_path, *extra, record=None, ops=None, manifest=None):
    boxes = tmp_path / "boxes"
    (tmp_path / "jax-image.json").write_text(json.dumps(manifest or _manifest()))
    pub = tmp_path / "lane.pub"
    pub.write_text(LANE_PUBKEY + "\n")
    reference = record or _class_record(DIGESTS, seconds=9.0)
    (tmp_path / "class.json").write_text(json.dumps(reference))
    (tmp_path / "class-ops.json").write_text(json.dumps(ops or _ops_record(reference)))
    return [
        "--ssh",
        f"ubuntu@{IP}",
        "--box-name",
        "a100-1",
        "--provider",
        "lambda",
        "--device-kind",
        KIND,
        "--door-ip",
        DOOR,
        "--lane-pubkey",
        str(pub),
        "--host-key-fingerprint",
        HOST_FINGERPRINT,
        "--jax-image",
        JAX,
        "--image",
        TORCH,
        "--graph-gpu-image-manifest",
        str(tmp_path / "jax-image.json"),
        "--class-record",
        str(tmp_path / "class.json"),
        "--class-ops-record",
        str(tmp_path / "class-ops.json"),
        "--boxes-dir",
        str(boxes),
        *extra,
    ]


def _config(tmp_path, *extra, **kwargs):
    args = box_up.build_parser().parse_args(_argv(tmp_path, *extra, **kwargs))
    return box_up.config_from_args(args)


def _run(cfg, box):
    return box_up.bring_up(cfg, box, now=lambda: 1763300000.5, log=lambda _line: None)


def _refused(outcome, reason):
    assert outcome["status"] == "REFUSED", outcome
    assert outcome["reason"] == reason, outcome


# -- the happy path -------------------------------------------------------------------------------------------------


def test_a_passing_box_gets_exactly_the_box_file(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    outcome = _run(cfg, box)
    assert outcome["status"] == "ADMITTED", outcome
    path = tmp_path / "boxes" / "a100-1.json"
    assert outcome["box_file"] == str(path)
    document = json.loads(path.read_text())
    assert set(document) == {
        "schema",
        "name",
        "docker_host",
        "stage_root",
        "slot_cpusets",
        "device",
        "device_digest",
        "driver_version",
        "host_key",
        "images",
        "tree_commit",
        "class_check_image_id",
        "class_check",
        "check_output_sha256",
        "check_ops_record_sha256",
        "admitted_unix",
    }
    device = _device_document()
    assert document["schema"] == "carbon.remote-gpu-build-box.v1"
    assert document["name"] == "a100-1"
    assert document["docker_host"] == f"ssh://carbon-grade@{IP}"
    assert document["stage_root"] == "/home/carbon"
    assert document["slot_cpusets"] == ["0-3", "4-7", "8-11", "12-15"]
    assert document["device"] == device
    canonical = json.dumps(device, sort_keys=True, separators=(",", ":")).encode()
    assert document["device_digest"] == _sha(canonical)
    assert document["driver_version"] == DRIVER
    assert document["host_key"] == f"{IP} ssh-ed25519 {HOST_KEY}"
    assert document["images"] == [JAX, TORCH]
    assert document["tree_commit"] == HEAD
    assert document["class_check_image_id"] == JAX
    assert document["class_check"] == {
        "case_digests": DIGESTS,
        "class_record_sha256": _sha((tmp_path / "class.json").read_bytes()),
        "class_ops_record_sha256": _sha((tmp_path / "class-ops.json").read_bytes()),
    }
    assert document["check_output_sha256"] == _sha(box.class_output.encode())
    assert document["check_ops_record_sha256"] == _sha(box.class_ops.encode())
    assert document["admitted_unix"] == 1763300000
    # The box was actually brought up: docker installed, toolkit, images, tree.
    assert box.docker == "29.1.3" and box.ctk and box.tree and box.restarts == 1
    assert box.loaded == {JAX: JAX, TORCH: TORCH}


def test_the_device_record_digest_is_the_one_the_door_reads():
    from carbon.reconstruction.host_inventory import HostDeviceRecord

    document = _device_document()
    digest = box_up._device_record(document)
    assert digest == HostDeviceRecord(document, digest).digest
    bad = {**document, "device_uuid": "not-a-uuid"}
    with pytest.raises(box_up.Refused) as refused:
        box_up._device_record(bad)
    assert refused.value.reason == "device_record_invalid"


def test_the_class_check_runs_like_the_receipted_runner(tmp_path):
    cfg = _config(tmp_path)
    words = shlex.split(box_up.cmd_class_check(cfg, UUID))
    image = words.index(JAX)
    flags = words[:image]
    assert flags[:4] == ["sudo", "-n", "docker", "run"]
    pairs = set(itertools.pairwise(flags))
    for pair in (
        ("--user", "65532:65532"),
        ("--network", "none"),
        ("--tmpfs", "/scratch:rw,size=4g"),
        ("--runtime", "nvidia"),
        ("--gpus", f"device={UUID}"),
        ("-v", "/var/lib/carbon-box-up/tree:/carbon:ro"),
        ("-v", "/var/lib/carbon-box-up/class-check:/out"),
        ("-e", "PYTHONPATH=/carbon"),
        ("--entrypoint", "/opt/carbon-worker/bin/python"),
    ):
        assert pair in pairs, pair
    assert "--rm" in flags and "--read-only" in flags
    assert words[image + 1 :] == [
        "-I",
        "-X",
        "faulthandler",
        "/carbon/scripts/dev/gpu_rebuild_class_check.py",
        "--out",
        "/out/class-check.json",
        "--ops-record",
        "/out/ops-record.json",
        "--steps",
        "512",
        "--no-torch",
    ]


def test_a_second_run_on_a_ready_box_changes_nothing(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    box.calls.clear()
    assert _run(cfg, box)["status"] == "ADMITTED"
    commands = box.remote_commands()
    assert box_up.cmd_docker_install("29.1.3") not in commands
    assert box_up.CMD_TOOLKIT_INSTALL not in commands
    assert box_up.CMD_LANE_CREATE not in commands
    assert box_up.CMD_DOCKER_LOAD not in commands
    assert box_up.CMD_DOCKER_RESTART not in commands
    assert box.restarts == 1
    assert (
        json.loads((tmp_path / "boxes" / "a100-1.json").read_text())["name"] == "a100-1"
    )


# -- typed stops ------------------------------------------------------------------------------------------------------


def _no_box_file(tmp_path):
    boxes = tmp_path / "boxes"
    return not list(boxes.iterdir())


def test_a_wrong_device_kind_is_refused_before_anything_is_installed(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"NVIDIA A100-SXM4-80GB, {UUID}, 81920 MiB, {DRIVER}\n"))
    outcome = _run(cfg, box)
    _refused(outcome, "wrong_device_kind")
    assert outcome["step"] == "driver"
    assert box.driver_installs == 0 and box.docker == ""
    assert _no_box_file(tmp_path)


def test_more_than_one_gpu_is_refused(tmp_path):
    cfg = _config(tmp_path)
    row = f"{KIND}, {UUID}, 40960 MiB, {DRIVER}\n"
    _refused(_run(cfg, FakeBox(cfg, smi=(0, row * 2))), "gpu_count")


def test_an_old_driver_is_upgraded_and_the_run_stops_for_a_reboot(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"{KIND}, {UUID}, 40960 MiB, 570.172.08\n"))
    outcome = _run(cfg, box)
    _refused(outcome, "driver_upgrade_needs_reboot")
    assert box.driver_installs == 1
    commands = box.remote_commands()
    assert commands[-1] == box_up.cmd_driver_install("nvidia-driver-580-server")
    assert box_up.CMD_DOCKER_VERSION not in commands  # no loop, nothing after
    assert _no_box_file(tmp_path)


def test_a_missing_driver_is_installed_and_the_run_stops_for_a_reboot(tmp_path):
    cfg = _config(tmp_path, "--driver-package", "nvidia-driver-580")
    box = FakeBox(cfg, smi=(9, "NVIDIA-SMI has failed\n"))
    _refused(_run(cfg, box), "driver_upgrade_needs_reboot")
    assert box.remote_commands()[-1] == box_up.cmd_driver_install("nvidia-driver-580")


def test_the_driver_floor_compares_versions_not_strings(tmp_path):
    cfg = _config(tmp_path, "--driver-floor", "580.65.06")
    box = FakeBox(cfg, smi=(0, f"{KIND}, {UUID}, 40960 MiB, 580.105.08\n"))
    box.device = json.dumps({**_device_document(), "driver_version": "580.105.08"})
    assert _run(cfg, box)["status"] == "ADMITTED"


def test_an_image_whose_id_differs_after_loading_is_refused(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, load_as={TORCH: "sha256:" + "f" * 64})
    outcome = _run(cfg, box)
    _refused(outcome, "image_id_mismatch")
    assert outcome["step"] == "images"
    assert _no_box_file(tmp_path)


def test_one_case_that_did_not_repeat_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS, identical={"graph:f08/conv": False})
    box = FakeBox(
        cfg,
        class_rc=1,
        class_output=json.dumps(record, indent=1, sort_keys=True) + "\n",
        class_ops=json.dumps(_ops_record(record)),
    )
    outcome = _run(cfg, box)
    _refused(outcome, "class_check_not_bit_identical")
    assert outcome["detail"] == "graph:f08/conv"
    assert _no_box_file(tmp_path)


def test_a_case_not_on_the_gpu_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS, on_gpu=False)
    box = FakeBox(
        cfg,
        class_output=json.dumps(record),
        class_ops=json.dumps(_ops_record(record)),
    )
    _refused(_run(cfg, box), "class_check_not_on_gpu")


def test_digests_that_differ_from_the_class_record_refuse(tmp_path):
    cfg = _config(tmp_path)
    other = {**DIGESTS, "graph:motor/softmax": "sha256:" + "9" * 64}
    record = _class_record(other)
    box = FakeBox(
        cfg,
        class_output=json.dumps(record),
        class_ops=json.dumps(_ops_record(record)),
    )
    outcome = _run(cfg, box)
    _refused(outcome, "class_check_digest_mismatch")
    assert "graph:motor/softmax state_digest" in outcome["detail"].split(", ")
    assert _no_box_file(tmp_path)


def test_a_case_missing_from_the_class_record_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record({**DIGESTS, "graph:f02/norm": "sha256:" + "4" * 64})
    box = FakeBox(
        cfg,
        class_output=json.dumps(record),
        class_ops=json.dumps(_ops_record(record)),
    )
    _refused(_run(cfg, box), "class_check_digest_mismatch")


def test_a_run_that_exits_nonzero_never_passes(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, class_rc=1)), "class_check_failed")
    _refused(_run(cfg, FakeBox(cfg, class_output="")), "class_check_failed")


# -- condition 1: the class's exact ops record ----------------------------------------------------------------------


def test_an_ops_record_that_differs_from_the_class_ops_record_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = json.loads(FakeBox(cfg).class_output)
    box = FakeBox(cfg, class_ops=json.dumps(_ops_record(record, ops=("dot_general",))))
    _refused(_run(cfg, box), "class_check_ops_mismatch")


def test_an_ops_record_under_another_allowlist_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = json.loads(FakeBox(cfg).class_output)
    box = FakeBox(
        cfg, class_ops=json.dumps(_ops_record(record, allowlist="sha256:" + "0" * 64))
    )
    _refused(_run(cfg, box), "class_check_not_allowlist_v8")


def test_an_ops_record_from_another_run_refuses(tmp_path):
    cfg = _config(tmp_path)
    stale = _class_record(DIGESTS, seconds=77.0)
    box = FakeBox(cfg, class_ops=json.dumps(_ops_record(stale)))
    _refused(_run(cfg, box), "class_check_ops_record_unbound")


def test_a_missing_ops_record_refuses(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, class_ops="")), "class_check_output_invalid")


def test_the_ops_record_compares_as_canonical_json(tmp_path):
    """Key order and spacing do not matter; every value but the run-naming digest must be equal."""
    record = _class_record(DIGESTS, seconds=3.0)
    reference = _ops_record(_class_record(DIGESTS, seconds=9.0))
    raw_ops = json.dumps(dict(reversed(list(_ops_record(record).items()))), indent=3)
    summary = box_up.evaluate_class_check(
        json.dumps(record),
        raw_ops,
        class_record=_class_record(DIGESTS, seconds=9.0),
        class_ops_record=reference,
        device_kind=KIND,
        allowlist_v8=box_up._allowlist_v8_digest(),
    )
    assert summary == {"case_digests": DIGESTS}


# -- condition 2: the pinned host key -------------------------------------------------------------------------------


def test_a_host_key_that_is_not_the_operators_refuses_before_any_ssh(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, keyscan=f"{IP} ssh-ed25519 {_key_body(99)}\n")
    outcome = _run(cfg, box)
    _refused(outcome, "host_key_mismatch")
    assert [argv[0] for argv, _ in box.calls] == ["ssh-keyscan"]
    assert _no_box_file(tmp_path)


def test_no_host_key_refuses(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, keyscan="")), "host_key_unavailable")


def test_every_ssh_pins_the_host_key(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    for argv, _ in box.calls:
        if argv[0] == "ssh":
            assert "StrictHostKeyChecking=yes" in argv
            assert "GlobalKnownHostsFile=/dev/null" in argv


# -- condition 3: files ---------------------------------------------------------------------------------------------


def test_the_box_file_is_a_private_regular_file_in_a_private_directory(tmp_path):
    cfg = _config(tmp_path)
    assert _run(cfg, FakeBox(cfg))["status"] == "ADMITTED"
    directory = os.lstat(tmp_path / "boxes")
    info = os.lstat(tmp_path / "boxes" / "a100-1.json")
    assert stat.S_IMODE(directory.st_mode) == 0o700
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_uid == os.geteuid()
    assert sorted(p.name for p in (tmp_path / "boxes").iterdir()) == [
        "a100-1.class-check.json",
        "a100-1.json",
        "a100-1.ops-record.json",
    ]
    for name in ("a100-1.class-check.json", "a100-1.ops-record.json"):
        side = os.lstat(tmp_path / "boxes" / name)
        assert stat.S_ISREG(side.st_mode) and stat.S_IMODE(side.st_mode) == 0o600


def test_a_boxes_dir_others_can_read_is_refused(tmp_path):
    cfg = _config(tmp_path)
    (tmp_path / "boxes").mkdir(mode=0o755)
    os.chmod(tmp_path / "boxes", 0o755)
    box = FakeBox(cfg)
    _refused(_run(cfg, box), "boxes_dir_unsafe")
    assert box.calls == []


def test_a_stale_box_file_is_removed_on_failure(tmp_path):
    """Removal ON FAILURE: box files that appear after the start-of-run removal (mid-run) are gone after the refusal."""
    cfg = _config(tmp_path)

    class Planting(FakeBox):
        def remote(self, cmd, pipe_from):
            if cmd == box_up.CMD_STAGE_ROOT_STAT:
                for path in box_up.box_files(cfg):
                    path.write_text("{}")
            return super().remote(cmd, pipe_from)

    box = Planting(cfg, stage="root:root 755 directory")
    _refused(_run(cfg, box), "stage_root_mismatch")
    assert _no_box_file(tmp_path)


def test_a_failed_readmission_removes_an_earlier_admission(tmp_path):
    cfg = _config(tmp_path)
    assert _run(cfg, FakeBox(cfg))["status"] == "ADMITTED"
    assert len(list((tmp_path / "boxes").iterdir())) == 3
    _refused(
        _run(cfg, FakeBox(cfg, stage="root:root 755 directory")), "stage_root_mismatch"
    )
    assert _no_box_file(tmp_path)


def test_a_stale_symlink_is_removed_not_followed(tmp_path):
    cfg = _config(tmp_path)
    (tmp_path / "boxes").mkdir(mode=0o700)
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    (tmp_path / "boxes" / "a100-1.json").symlink_to(target)
    _refused(_run(cfg, FakeBox(cfg, nproc=8)), "slot_shape_cpus")
    assert not os.path.lexists(tmp_path / "boxes" / "a100-1.json")
    assert target.read_text() == "{}"


# -- condition 4: slot shape ----------------------------------------------------------------------------------------


def test_too_few_cpus_refuses(tmp_path):
    cfg = _config(tmp_path)
    outcome = _run(cfg, FakeBox(cfg, nproc=15))
    _refused(outcome, "slot_shape_cpus")
    assert outcome["step"] == "shape"


def test_too_little_memory_refuses(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, mem_kib=64 * 1024 * 1024)), "slot_shape_memory")
    _refused(_run(cfg, FakeBox(cfg, mem_kib=72 * 1024 * 1024 - 1)), "slot_shape_memory")


def test_exactly_the_minimum_shape_passes(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, nproc=16, mem_kib=72 * 1024 * 1024)
    assert _run(cfg, box)["status"] == "ADMITTED"


# -- condition 5: nothing secret reaches the box --------------------------------------------------------------------


def test_only_public_material_goes_to_the_box(tmp_path):
    cfg = _config(tmp_path, "--ssh-key", str(tmp_path / "operator_key"))
    (tmp_path / "operator_key").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n"
    )
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    streamed = [pipe for _, pipe in box.calls if pipe is not None]
    assert streamed == [
        ["docker", "save", JAX],
        ["docker", "save", TORCH],
        ["git", "-C", str(box_up.ROOT), "archive", "--format=tar", HEAD, "--"]
        + list(box_up.TREE_PATHS),
    ]
    lane_body = LANE_PUBKEY.split()[1]
    for argv, _ in box.calls:
        text = " ".join(argv)
        assert "PRIVATE KEY" not in text and "secret" not in text
        if argv[0] == "ssh":
            assert "ForwardAgent=no" in argv and "ClearAllForwardings=yes" in argv
            command = argv[-1]
            # The only key material in any command is the lane's public key.
            if "ssh-ed25519" in command:
                assert lane_body in command and "authorized_keys" in command


def test_a_private_key_as_the_lane_key_is_refused(tmp_path):
    argv = _argv(tmp_path)
    (tmp_path / "lane.pub").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----\n"
    )
    with pytest.raises(box_up.Refused) as refused:
        box_up.config_from_args(box_up.build_parser().parse_args(argv))
    assert refused.value.reason == "lane_pubkey_is_private"


def test_the_guard_refuses_any_other_upload(tmp_path):
    cfg = _config(tmp_path)
    session = box_up.Session(cfg, FakeBox(cfg), log=lambda _l: None)
    for pipe in (
        ["git", "-C", str(box_up.ROOT), "archive", "--format=tar", HEAD],
        box_up.cmd_git_archive(HEAD) + [".agent"],
        ["cat", str(tmp_path / "operator_key")],
        ["docker", "save", "sha256:" + "e" * 64],
        ["tar", "-c", "/home"],
    ):
        with pytest.raises(box_up.Refused) as refused:
            session.call(["ssh", "x"], pipe)
        assert refused.value.reason == "upload_refused"
    with pytest.raises(box_up.Refused) as refused:
        session.call(["ssh", "x", "echo '-----BEGIN RSA PRIVATE KEY-----'"])
    assert refused.value.reason == "secret_refused"


# -- daemon.json and authorized_keys ---------------------------------------------------------------------------------


def test_the_daemon_json_merge_keeps_the_snapshotter_and_the_nvidia_runtime():
    ctk = {
        "log-driver": "json-file",
        "features": {"buildkit": True},
        "runtimes": {"nvidia": {"args": [], "path": "nvidia-container-runtime"}},
    }
    merged = box_up.merge_daemon_json(json.dumps(ctk, indent=4))
    assert merged == {
        "log-driver": "json-file",
        "features": {"buildkit": True, "containerd-snapshotter": True},
        "runtimes": {"nvidia": {"args": [], "path": "nvidia-container-runtime"}},
    }
    # A second pass over its own output changes nothing.
    assert box_up.merge_daemon_json(box_up.daemon_json_text(merged)) == merged
    with pytest.raises(box_up.Refused) as refused:
        box_up.merge_daemon_json('{"features": {"containerd-snapshotter": true}}')
    assert refused.value.reason == "docker_nvidia_runtime_missing"


def test_the_box_daemon_json_ends_with_both(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    final = json.loads(box.daemon)
    assert final["features"]["containerd-snapshotter"] is True
    assert final["runtimes"]["nvidia"]["path"] == "nvidia-container-runtime"
    assert final["log-driver"] == "json-file"


def test_a_daemon_without_the_snapshotter_after_restart_refuses(tmp_path):
    cfg = _config(tmp_path)

    class NoSnapshotter(FakeBox):
        def remote(self, cmd, pipe_from):
            if cmd == box_up.CMD_DOCKER_INFO:
                info = {
                    "ServerVersion": "29.1.3",
                    "DriverStatus": [],
                    "Runtimes": {"nvidia": {}},
                }
                return 0, json.dumps(info), ""
            return super().remote(cmd, pipe_from)

    _refused(_run(cfg, NoSnapshotter(cfg)), "docker_snapshotter_missing")


def test_the_authorized_keys_line_is_exact(tmp_path):
    assert box_up.authorized_keys_line(DOOR, LANE_PUBKEY) == (
        f'from="{DOOR}",no-agent-forwarding,no-port-forwarding,no-X11-forwarding {LANE_PUBKEY}'
    )
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.authorized_keys == (
        f'from="{DOOR}",no-agent-forwarding,no-port-forwarding,no-X11-forwarding {LANE_PUBKEY}\n'
    )


def test_authorized_keys_that_read_back_differently_refuse(tmp_path):
    cfg = _config(tmp_path)

    class Extra(FakeBox):
        def remote(self, cmd, pipe_from):
            rc, out, err = super().remote(cmd, pipe_from)
            if cmd == box_up.CMD_AUTHORIZED_KEYS_READ:
                out += "ssh-ed25519 AAAA other\n"
            return rc, out, err

    _refused(_run(cfg, Extra(cfg)), "authorized_keys_mismatch")


def test_a_lane_user_with_uid_zero_refuses(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, lane_uid="0")), "lane_user_is_root")


# -- dry run --------------------------------------------------------------------------------------------------------


def test_a_dry_run_runs_nothing_and_prints_every_command(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("the dry run ran a command")

    assert box_up.main([*_argv(tmp_path), "--dry-run"], runner=boom) == 0
    out = capsys.readouterr().out
    assert not (tmp_path / "boxes").exists()
    assert f"ssh-keyscan -t ed25519 -p 22 {IP}" in out
    assert "nvidia-ctk runtime configure --runtime=docker" in out
    assert f"docker save {TORCH} | ssh" in out
    assert "gpu_rebuild_class_check.py" in out and "--steps 512" in out
    printed = [line for line in out.splitlines() if line.startswith("[")]
    assert len(printed) == len(box_up.plan(_config(tmp_path)))


def test_bad_arguments_exit_2_without_running(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("ran a command")

    argv = _argv(tmp_path)
    argv[argv.index("--jax-image") + 1] = "jax:latest"
    assert box_up.main(argv, runner=boom) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "bad_argument"


# -- V2: exact device name -------------------------------------------------------------------------------------------


def test_a_device_name_that_only_starts_with_the_kind_is_refused(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"{KIND}-SPECIAL, {UUID}, 40960 MiB, {DRIVER}\n"))
    _refused(_run(cfg, box), "wrong_device_kind")


def test_a_class_check_on_a_device_whose_name_only_starts_with_the_kind_refuses(
    tmp_path,
):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS)
    record["nvidia_smi"]["gpus"] = [f"{KIND} SPECIAL, {DRIVER}, 40960 MiB, 8.0"]
    box = FakeBox(
        cfg, class_output=json.dumps(record), class_ops=json.dumps(_ops_record(record))
    )
    _refused(_run(cfg, box), "class_check_wrong_device")


# -- V2: every digest ------------------------------------------------------------------------------------------------


def _box_with(cfg, record):
    return FakeBox(
        cfg, class_output=json.dumps(record), class_ops=json.dumps(_ops_record(record))
    )


def test_a_rebuild_predictions_digest_that_differs_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS)
    record["cases"][1]["rebuilds"][1]["predictions_digest"] = "sha256:" + "8" * 64
    outcome = _run(cfg, _box_with(cfg, record))
    _refused(outcome, "class_check_digest_mismatch")
    assert outcome["detail"] == "graph:f08/conv rebuilds[1].predictions_digest"


def test_a_digest_missing_on_one_side_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS)
    del record["cases"][0]["rebuilds"][0]["predictions_digest"]
    outcome = _run(cfg, _box_with(cfg, record))
    _refused(outcome, "class_check_digest_mismatch")
    assert outcome["detail"] == "graph:f08/mlp rebuilds[0].predictions_digest"


def test_a_different_number_of_rebuilds_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS)
    record["cases"][2]["rebuilds"].append(dict(record["cases"][2]["rebuilds"][0]))
    _refused(_run(cfg, _box_with(cfg, record)), "class_check_digest_mismatch")


def test_only_the_cpu_parity_digest_differing_is_still_admitted(tmp_path):
    """A lane box never runs a CPU build (remote_gpu_build.eligible needs an accelerator), so the class record's CPU
    parity run is not this box's to reproduce."""
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS, cpu="sha256:" + "d" * 64)
    record["cases"][0]["parity_vs_cpu"] = {"max_abs": 3e-4, "rows": 64}
    record["cases"][0]["cpu_error"] = None
    assert _run(cfg, _box_with(cfg, record))["status"] == "ADMITTED"


def test_a_reference_class_record_that_did_not_repeat_is_refused(tmp_path):
    reference = _class_record(DIGESTS, identical={"graph:f08/conv": False})
    argv = _argv(tmp_path, record=reference)
    with pytest.raises(box_up.Refused) as refused:
        box_up.config_from_args(box_up.build_parser().parse_args(argv))
    assert refused.value.reason == "class_record_not_gpu_repeats"


# -- V2: the receiver's image and the class check's own files --------------------------------------------------------


def _config_refusal(argv):
    with pytest.raises(box_up.Refused) as refused:
        box_up.config_from_args(box_up.build_parser().parse_args(argv))
    return refused.value.reason


def test_the_manifest_image_must_be_the_jax_image(tmp_path):
    other = "sha256:" + "e" * 64
    assert (
        _config_refusal(_argv(tmp_path, manifest=_manifest(image=other)))
        == "graph_gpu_image_mismatch"
    )


def test_a_manifest_that_is_not_the_jax_gpu_worker_is_refused(tmp_path):
    manifest = _manifest(lock="sha256:" + "9" * 64)
    assert (
        _config_refusal(_argv(tmp_path, manifest=manifest)) == "graph_gpu_image_not_jax"
    )


def test_a_malformed_manifest_is_refused(tmp_path):
    manifest = {**_manifest(), "extra": 1}
    assert (
        _config_refusal(_argv(tmp_path, manifest=manifest))
        == "graph_gpu_image_manifest_invalid"
    )


def test_the_class_check_output_is_kept_beside_the_box_file(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    boxes = tmp_path / "boxes"
    document = json.loads((boxes / "a100-1.json").read_text())
    output = (boxes / "a100-1.class-check.json").read_bytes()
    ops = (boxes / "a100-1.ops-record.json").read_bytes()
    assert output == box.class_output.encode()
    assert ops == box.class_ops.encode()
    assert document["check_output_sha256"] == _sha(output)
    assert document["check_ops_record_sha256"] == _sha(ops)
    words = shlex.split(box_up.cmd_class_check(cfg, UUID))
    assert document["class_check_image_id"] in words


# -- review: docker restart ------------------------------------------------------------------------------------------


def test_a_merged_daemon_json_the_daemon_does_not_show_gets_a_restart(tmp_path):
    cfg = _config(tmp_path)
    merged = {
        "log-driver": "json-file",
        "features": {"containerd-snapshotter": True},
        "runtimes": {"nvidia": {"args": [], "path": "nvidia-container-runtime"}},
    }
    box = FakeBox(
        cfg,
        docker="29.1.3",
        ctk=True,
        daemon=box_up.daemon_json_text(merged),
        daemon_live={"runtimes": merged["runtimes"]},
    )
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.restarts == 1


def test_a_daemon_that_is_right_is_not_restarted(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.restarts == 1
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.restarts == 1


# -- review: malformed box output ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            {
                "class_output": json.dumps(
                    {**_class_record(DIGESTS), "nvidia_smi": ["x"]}
                )
            },
            None,
        ),
        ({"class_ops": '{"schema": "carbon.graph-gpu-ops.v1", "ops": NaN}'}, None),
        (
            {"class_output": json.dumps({**_class_record(DIGESTS), "cases": ["x"]})},
            None,
        ),
        ({"class_output": "[1, 2]"}, None),
        ({"device": '{"device_kind": NaN}'}, "device_record_invalid"),
        (
            {"device": json.dumps({**_device_document(), "device_memory_mib": "x"})},
            "device_record_invalid",
        ),
    ],
)
def test_malformed_box_output_is_a_typed_refusal(tmp_path, change, reason):
    cfg = _config(tmp_path)
    if "class_output" in change and "class_ops" not in change:
        try:
            record = json.loads(change["class_output"])
            change["class_ops"] = json.dumps(_ops_record(record))
        except (TypeError, ValueError, AttributeError):
            pass
    outcome = _run(cfg, FakeBox(cfg, **change))
    assert outcome["status"] == "REFUSED"
    if reason:
        assert outcome["reason"] == reason
    else:
        assert outcome["step"] == "class_check"
        assert outcome["reason"].startswith("class_check_")
    assert _no_box_file(tmp_path)


def test_docker_info_that_is_not_an_object_is_a_typed_refusal(tmp_path):
    cfg = _config(tmp_path)

    class Odd(FakeBox):
        def remote(self, cmd, pipe_from):
            if cmd == box_up.CMD_DOCKER_INFO:
                return 0, "[1]", ""
            return super().remote(cmd, pipe_from)

    _refused(_run(cfg, Odd(cfg)), "docker_unreadable")


def test_an_unexpected_shape_inside_a_step_is_a_typed_refusal(tmp_path):
    """Any parse error a step did not foresee becomes `<step>_output_invalid`, never a traceback."""
    cfg = _config(tmp_path)
    session = box_up.Session(cfg, FakeBox(cfg), log=lambda _l: None)

    def odd():
        return {"a": 1}["missing"]

    with pytest.raises(box_up.Refused) as refused:
        session.run_step("lane_user", odd)
    assert refused.value.reason == "lane_user_output_invalid"
    assert refused.value.detail.startswith("KeyError")


# -- review: the tree ------------------------------------------------------------------------------------------------


def test_only_the_class_check_paths_are_archived():
    archive = box_up.cmd_git_archive(HEAD)
    paths = archive[archive.index("--") + 1 :]
    assert paths == list(box_up.TREE_PATHS)
    for path in paths:
        assert (box_up.ROOT / path).exists(), path
        for private in (".agent", "Business", "codex-queue", "tests", ".git"):
            assert not path.startswith(private)


def test_a_commit_not_on_origin_main_never_leaves_the_door(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, on_main=False)
    outcome = _run(cfg, box)
    _refused(outcome, "tree_not_on_origin_main")
    assert box.extracts == 0
    assert not [pipe for _, pipe in box.calls if pipe and pipe[0] == "git"]


def test_the_tree_is_extracted_afresh_on_every_run(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.extracts == 2
    assert "rm -rf /var/lib/carbon-box-up/tree;" in box_up.CMD_TREE_EXTRACT


# -- review: CPUs online ---------------------------------------------------------------------------------------------


def test_the_shape_counts_all_cpus_and_needs_0_to_15_online(tmp_path):
    assert box_up.CMD_SHAPE.startswith("nproc --all;")
    assert "/sys/devices/system/cpu/online" in box_up.CMD_SHAPE
    cfg = _config(tmp_path)
    box = FakeBox(cfg, nproc=32, online="0-7,16-31")
    _refused(_run(cfg, box), "slot_cpus_offline")
    assert box_up.cpu_list("0-3,8,10-11") == {0, 1, 2, 3, 8, 10, 11}


# -- the provider ----------------------------------------------------------------------------------------------------


def test_a_provider_the_owner_did_not_accept_is_refused(tmp_path):
    argv = _argv(tmp_path)
    argv[argv.index("--provider") + 1] = "otherprovider"
    assert _config_refusal(argv) == "provider_not_accepted"


# -- the documented limit --------------------------------------------------------------------------------------------


def test_limit_a_box_replaying_another_boxs_output_is_admitted_pass_is_not_security_qualification(
    tmp_path,
):
    """Every value deciding PASS comes from the box. A box that returns another box's recorded class-check output
    (here: the class record itself, byte for byte, with its ops record) is admitted. This documents the limit; the
    lane's per-build re-reads and the door's determinism checks remain the guard."""
    reference = _class_record(DIGESTS, seconds=9.0)
    reference_ops = _ops_record(reference)
    cfg = _config(tmp_path, record=reference, ops=reference_ops)
    replay = FakeBox(
        cfg,
        class_rc=0,
        class_output=json.dumps(reference),
        class_ops=json.dumps(reference_ops),
    )
    assert _run(cfg, replay)["status"] == "ADMITTED"
    assert "replays another box's output can" in box_up.__doc__
