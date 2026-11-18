"""GPU box bring-up in two phases (scripts/dev/gpu_box_up.py), driven against a fake box.

Claims, admin phase (the box's admin user, the operator's own key): it changes the box (driver, docker + containerd,
daemon.json, the carbon-grade lane user and its one restricted key line, the stage root), needs and writes no door
files, streams nothing, refuses to run as carbon-grade, and prints a summary.

Claims, door phase (carbon-grade only, never sudo): it re-verifies the admin work read-only and names the admin step to
re-run when anything is missing; an admin summary must agree with the box; a box that passes every step gets exactly
one box file with exactly the documented fields, 0600 in a 0700 directory, and every failure is a typed stop that
leaves no box file; the class check must repeat on the GPU under allowlist v8, match the class record's digests and
reproduce the class's ops record; nothing but public material reaches the box; a dry run runs nothing. It also
documents the limit: a box that replays another box's output passes (PASS is not security qualification).
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
import subprocess
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


MERGED_DAEMON = {
    "log-driver": "json-file",
    "features": {"containerd-snapshotter": True},
    "runtimes": {"nvidia": {"args": [], "path": "nvidia-container-runtime"}},
}
LANE_LINE = f'restrict,from="{DOOR}" {LANE_PUBKEY}'


class FakeBox:
    """An Ubuntu box with an A100, reached only through the runner. Every command it does not know fails the test.

    Fresh for the admin phase; as the admin phase leaves it for the door phase (``prepared``). Commands with sudo are
    accepted only from the admin user, and the lane user's commands only from carbon-grade.
    """

    def __init__(self, cfg, *, prepared=None, **state):
        self.cfg = cfg
        self.calls = []
        self.users = []
        self.keyscan = f"{IP} ssh-ed25519 {HOST_KEY}\n"
        self.nproc = 30
        self.online = "0-29"
        self.on_main = True
        self.extracts = 0
        self.cleans = 0
        self.mem_kib = 216 * 1024 * 1024
        self.smi = (0, f"{KIND}, {UUID}, 40960 MiB, {DRIVER}\n")
        self.driver_installs = 0
        self.docker = ""
        self.containerd = "v2.4.2"
        self.ctk = False
        self.daemon = '{\n  "log-driver": "json-file"\n}\n'
        self.daemon_live = None
        self.restarts = 0
        self.lane_uid = ""
        self.lane_name = "carbon-grade"
        self.lane_home = ""
        self.groups = ["carbon-grade"]
        self.authorized_keys = ""
        self.stage = "carbon-grade:carbon-grade 755 directory"
        # a fresh Lambda box: no drop-in, sshd on its defaults
        self.sshd_dropin = ""
        self.sshd_writes = 0
        self.sshd_reloads = 0
        self.sshd_includes = True
        # Lambda's Ubuntu 22.04: python3 is 3.10, no newer interpreter until the admin phase installs python3.11
        self.python = ""
        self.python_installs = 0
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
        if prepared if prepared is not None else cfg.phase == "door":
            self.docker = "29.1.3"
            self.ctk = True
            self.daemon = box_up.daemon_json_text(MERGED_DAEMON)
            self.daemon_live = dict(MERGED_DAEMON)
            self.lane_uid = "1001"
            self.lane_home = "/home/carbon-grade"
            self.groups = ["carbon-grade", "docker"]
            self.authorized_keys = LANE_LINE + "\n"
            self.python = "/usr/bin/python3.11"
            self.sshd_dropin = box_up.SSHD_DROPIN_TEXT
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
        assert argv[-2] == "--" and argv[-3].endswith(f"@{IP}")
        self.user = argv[-3].split("@")[0]
        self.users.append(self.user)
        if "sudo" in argv[-1]:
            assert self.user != "carbon-grade", argv[-1]
        return self.remote(argv[-1], pipe_from)

    def _info(self):
        live = self.daemon_live or {}
        snapshotter = (live.get("features") or {}).get("containerd-snapshotter")
        driver = "io.containerd.snapshotter.v1" if snapshotter else "overlay2"
        return json.dumps(
            {
                "ServerVersion": self.docker,
                "DriverStatus": [["driver-type", driver]],
                "Runtimes": {"runc": {}, **(live.get("runtimes") or {})},
            }
        )

    def _lane_only(self):
        assert self.user == "carbon-grade", self.user

    def remote(self, cmd, pipe_from):
        g, cfg = box_up, self.cfg
        # both phases, read-only
        if cmd == g.CMD_SHAPE:
            return 0, f"{self.nproc}\n{self.online}\nMemTotal: {self.mem_kib} kB\n", ""
        if cmd == g.CMD_DRIVER_QUERY:
            return (*self.smi, "")
        if cmd in (g.CMD_DOCKER_VERSION, g.DOOR_DOCKER_VERSION):
            out = f"{self.docker} {self.containerd}\n" if self.docker else ""
            return 0, out, ""
        if cmd in (g.CMD_DOCKER_INFO, g.DOOR_DOCKER_INFO):
            return 0, self._info(), ""
        if cmd == g.CMD_STAGE_ROOT_STAT:
            return 0, self.stage + "\n", ""
        if cmd == g.CMD_PYTHON_FIND:
            return 0, (self.python + "\n") if self.python else "", ""
        if cmd == g.CMD_PYTHON_INSTALL:
            self.python_installs += 1
            self.python = "/usr/bin/python3.11"
            return 0, "", ""
        # admin phase
        if cmd == g.cmd_driver_install(cfg.driver_package):
            self.driver_installs += 1
            return 0, "", ""
        if cmd == g.cmd_docker_install(cfg.docker_version, cfg.containerd_version):
            self.docker = cfg.docker_version
            self.containerd = "v" + cfg.containerd_version
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
        if cmd == g.CMD_LANE_UID:
            return 0, self.lane_uid, ""
        if cmd == g.CMD_LANE_CREATE:
            self.lane_uid = "1001"
            self.lane_home = "/home/carbon-grade"
            return 0, "", ""
        if cmd == g.CMD_LANE_GROUP:
            self.groups.append("docker")
            return 0, "", ""
        if cmd == g.CMD_LANE_ID:
            return (
                0,
                f"{self.lane_uid}\n{' '.join(self.groups)}\n{self.lane_home}\n",
                "",
            )
        if (
            cmd.startswith("sudo -n sh -c ")
            and "printf" in cmd
            and "authorized_keys" in cmd
        ):
            self.authorized_keys = _printed_text(cmd)
            return 0, "", ""
        if cmd in (g.CMD_AUTHORIZED_KEYS_READ, g.CMD_AUTHORIZED_KEYS_BEFORE):
            return 0, self.authorized_keys, ""
        if cmd == g.CMD_STAGE_ROOT:
            return 0, "", ""
        if cmd == g.CMD_SSHD_READ:
            return 0, self.sshd_dropin, ""
        if cmd == g.CMD_SSHD_WRITE:
            self.sshd_writes += 1
            self.sshd_dropin = _printed_text(cmd)
            return 0, "", ""
        if cmd == g.CMD_SSHD_RELOAD:
            self.sshd_reloads += 1
            return 0, "", ""
        if cmd == g.CMD_SSHD_EFFECTIVE:
            on = self.sshd_includes and self.sshd_dropin == g.SSHD_DROPIN_TEXT
            limits = ("100:30:200", "64") if on else ("10:30:100", "10")
            return 0, f"port 22\nmaxstartups {limits[0]}\nmaxsessions {limits[1]}\n", ""
        # door phase, as carbon-grade
        self._lane_only()
        if cmd == g.DOOR_WHOAMI:
            if not self.lane_uid or LANE_LINE not in self.authorized_keys:
                return 255, "", "Permission denied (publickey)."
            return (
                0,
                f"{self.lane_name}\n{self.lane_uid}\n{' '.join(self.groups)}\n{self.lane_home}\n",
                "",
            )
        if cmd == g.DOOR_AUTHORIZED_KEYS_READ:
            return 0, self.authorized_keys, ""
        if cmd.startswith("docker image inspect"):
            image = shlex.split(cmd)[5]
            return 0, (self.loaded.get(image, "") + "\n"), ""
        if cmd == g.DOOR_DOCKER_LOAD:
            assert pipe_from[:2] == ["docker", "save"]
            image = pipe_from[2]
            self.loaded[image] = self.load_as.get(image, image)
            return 0, "Loaded image ID: " + image + "\n", ""
        if cmd == g.DOOR_WORK_DIR:
            return 0, "", ""
        if cmd == g.cmd_tree_extract(HEAD):
            assert pipe_from == g.cmd_git_archive(HEAD)
            self.tree = True
            self.extracts += 1
            return 0, "", ""
        if cmd == g.cmd_prepare(cfg, HEAD, self.python):
            return 0, "{}", ""
        if cmd == g.CMD_DEVICE_READ:
            return 0, self.device, ""
        if cmd == g.cmd_class_out(cfg):
            return 0, "", ""
        if cmd == g.cmd_class_check(cfg, HEAD, UUID):
            return self.class_rc, "", ""
        if cmd == g.CMD_CLASS_OUTPUT_READ:
            return 0, self.class_output, ""
        if cmd == g.CMD_CLASS_OPS_READ:
            return 0, self.class_ops, ""
        if cmd == g.cmd_class_clean(cfg):
            self.cleans += 1
            return 0, "", ""
        raise AssertionError(f"unexpected remote command: {cmd}")

    def remote_commands(self):
        return [argv[-1] for argv, _ in self.calls if argv[0] == "ssh"]


def _pub(tmp_path):
    pub = tmp_path / "lane.pub"
    pub.write_text(LANE_PUBKEY + "\n")
    return pub


def _admin_argv(tmp_path, *extra):
    return [
        "admin",
        "--ip",
        IP,
        "--host-key-fingerprint",
        HOST_FINGERPRINT,
        "--device-kind",
        KIND,
        "--door-ip",
        DOOR,
        "--lane-pubkey",
        str(_pub(tmp_path)),
        *extra,
    ]


def _door_argv(tmp_path, *extra, record=None, ops=None, manifest=None):
    (tmp_path / "jax-image.json").write_text(json.dumps(manifest or _manifest()))
    reference = record or _class_record(DIGESTS, seconds=9.0)
    (tmp_path / "class.json").write_text(json.dumps(reference))
    (tmp_path / "class-ops.json").write_text(json.dumps(ops or _ops_record(reference)))
    return [
        "door",
        "--ip",
        IP,
        "--host-key-fingerprint",
        HOST_FINGERPRINT,
        "--box-name",
        "a100-1",
        "--provider",
        "lambda",
        "--device-kind",
        KIND,
        "--door-ip",
        DOOR,
        "--lane-pubkey",
        str(_pub(tmp_path)),
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
        str(tmp_path / "boxes"),
        *extra,
    ]


def _parse(argv):
    return box_up.config_from_args(box_up.build_parser().parse_args(argv))


def _admin_config(tmp_path, *extra):
    return _parse(_admin_argv(tmp_path, *extra))


def _config(tmp_path, *extra, **kwargs):
    """The door phase's config."""
    return _parse(_door_argv(tmp_path, *extra, **kwargs))


def _config_refusal(argv):
    with pytest.raises(box_up.Refused) as refused:
        _parse(argv)
    return refused.value.reason


def _admin(cfg, box):
    return box_up.run_admin(cfg, box, log=lambda _line: None)


def _run(cfg, box):
    return box_up.bring_up(cfg, box, now=lambda: 1763300000.5, log=lambda _line: None)


def _refused(outcome, reason):
    assert outcome["status"] == "REFUSED", outcome
    assert outcome["reason"] == reason, outcome


def _admin_refused(outcome, reason):
    assert outcome["admin"] == "REFUSED", outcome
    assert outcome["reason"] == reason, outcome


def _no_box_file(tmp_path):
    boxes = tmp_path / "boxes"
    return not list(boxes.iterdir())


# == the two phases together ==========================================================================================


def test_a_fresh_box_is_brought_up_by_the_admin_phase_then_admitted_by_the_door(
    tmp_path,
):
    admin_cfg = _admin_config(tmp_path)
    box = FakeBox(admin_cfg)
    summary = _admin(admin_cfg, box)
    assert summary["admin"] == "PASS", summary
    assert set(box.users) == {"ubuntu"}
    (tmp_path / "admin.json").write_text(json.dumps(summary))
    box.cfg = _config(tmp_path, "--admin-summary", str(tmp_path / "admin.json"))
    box.users.clear()
    outcome = _run(box.cfg, box)
    assert outcome["status"] == "ADMITTED", outcome
    assert set(box.users) == {"carbon-grade"}
    document = json.loads((tmp_path / "boxes" / "a100-1.json").read_text())
    assert document["admin_summary_sha256"] == _sha(
        (tmp_path / "admin.json").read_bytes()
    )


# == the admin phase ===================================================================================================


def test_the_admin_phase_prints_its_summary(tmp_path, capsys):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert box_up.main(_admin_argv(tmp_path), runner=box) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema"] == "carbon.gpu-box-admin.v1"
    assert summary["admin"] == "PASS"
    assert summary["box_ip"] == IP
    assert summary["host_key"] == f"{IP} ssh-ed25519 {HOST_KEY}"
    assert summary["device_uuid"] == UUID and summary["driver_version"] == DRIVER
    assert summary["docker_version"] == "29.1.3"
    assert summary["containerd_version"] == "2.4.2"
    assert summary["shape"] == {
        "cpus": 30,
        "online": "0-29",
        "mem_total_kib": 216 * 1024 * 1024,
    }
    # The box was actually brought up: docker, toolkit, daemon.json, the lane user, its key.
    assert box.docker == "29.1.3" and box.ctk and box.restarts == 1
    assert box.lane_uid == "1001" and "docker" in box.groups
    assert box.authorized_keys == LANE_LINE + "\n"


def test_the_admin_phase_needs_no_door_files_and_writes_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(box_up.tempfile, "tempdir", str(scratch))
    argv = _admin_argv(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    cfg = _parse(argv)
    assert cfg.boxes_dir is None and cfg.class_record is None
    assert cfg.admin_summary is None and cfg.images == ()
    assert _admin(cfg, FakeBox(cfg))["admin"] == "PASS"
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert list(scratch.iterdir()) == []
    for flag in ("--boxes-dir", "--class-record", "--graph-gpu-image-manifest"):
        with pytest.raises(SystemExit):
            box_up.build_parser().parse_args([*argv, flag, "x"])


def test_the_admin_phase_streams_nothing_to_the_box(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    assert [pipe for _, pipe in box.calls if pipe is not None] == []
    session = box_up.Session(cfg, box, log=lambda _l: None)
    with pytest.raises(box_up.Refused) as refused:
        session.call(["ssh", "x"], box_up.cmd_docker_save(JAX))
    assert refused.value.reason == "upload_refused"


def test_the_lane_user_is_refused_as_the_admin(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("ran a command")

    argv = _admin_argv(tmp_path, "--user", "carbon-grade")
    assert _config_refusal(argv) == "admin_user_is_lane_user"
    assert box_up.main(argv, runner=boom) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "admin_user_is_lane_user"


def test_the_admin_phase_logs_in_as_its_user(tmp_path):
    cfg = _admin_config(tmp_path, "--user", "admin2")
    assert cfg.user == "admin2"
    argv = box_up.ssh(cfg, "kh", "true")
    assert argv[-3] == f"admin2@{IP}"


def test_a_second_admin_run_on_a_ready_box_changes_nothing(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    box.calls.clear()
    assert _admin(cfg, box)["admin"] == "PASS"
    commands = box.remote_commands()
    assert box_up.cmd_docker_install("29.1.3", "2.4.2") not in commands
    assert box_up.CMD_TOOLKIT_INSTALL not in commands
    assert box_up.CMD_LANE_CREATE not in commands
    assert box_up.CMD_DOCKER_RESTART not in commands
    assert box.restarts == 1


def test_a_fresh_box_gets_the_sshd_drop_in_for_the_lanes(tmp_path):
    """Every box the admin phase brings up (and so every autoscaled box) gets sshd's lane limits: carbon-a100 refused
    ssh under load on the default MaxStartups 10:30:100 (18 Nov 2026 ~01:30Z)."""
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.sshd_dropin == "MaxStartups 100:30:200\nMaxSessions 64\n"
    assert box.sshd_writes == 1 and box.sshd_reloads == 1
    write = box_up.CMD_SSHD_WRITE
    assert "/etc/ssh/sshd_config.d/00-carbon-lanes.conf" in write
    assert "/usr/sbin/sshd -t" in write and "chmod 0644" in write
    box.calls.clear()
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box_up.CMD_SSHD_WRITE not in box.remote_commands()
    assert box.sshd_writes == 1 and box.sshd_reloads == 2


def test_a_box_where_sshd_does_not_show_the_limits_is_refused(tmp_path):
    cfg = _admin_config(tmp_path)
    outcome = _admin(cfg, FakeBox(cfg, sshd_includes=False))
    _admin_refused(outcome, "sshd_limits_not_in_force")
    assert outcome["step"] == "sshd"


def test_a_wrong_device_kind_is_refused_before_anything_is_installed(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"NVIDIA A100-SXM4-80GB, {UUID}, 81920 MiB, {DRIVER}\n"))
    outcome = _admin(cfg, box)
    _admin_refused(outcome, "wrong_device_kind")
    assert outcome["step"] == "driver"
    assert box.driver_installs == 0 and box.docker == ""


def test_a_device_name_that_only_starts_with_the_kind_is_refused(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"{KIND}-SPECIAL, {UUID}, 40960 MiB, {DRIVER}\n"))
    _admin_refused(_admin(cfg, box), "wrong_device_kind")


def test_more_than_one_gpu_is_refused(tmp_path):
    cfg = _admin_config(tmp_path)
    row = f"{KIND}, {UUID}, 40960 MiB, {DRIVER}\n"
    _admin_refused(_admin(cfg, FakeBox(cfg, smi=(0, row * 2))), "gpu_count")


def test_an_old_driver_is_upgraded_and_the_run_stops_for_a_reboot(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, smi=(0, f"{KIND}, {UUID}, 40960 MiB, 570.172.08\n"))
    _admin_refused(_admin(cfg, box), "driver_upgrade_needs_reboot")
    assert box.driver_installs == 1
    commands = box.remote_commands()
    assert commands[-1] == box_up.cmd_driver_install("nvidia-driver-580-server")
    assert box_up.CMD_DOCKER_VERSION not in commands  # no loop, nothing after


def test_a_missing_driver_is_installed_and_the_run_stops_for_a_reboot(tmp_path):
    cfg = _admin_config(tmp_path, "--driver-package", "nvidia-driver-580")
    box = FakeBox(cfg, smi=(9, "NVIDIA-SMI has failed\n"))
    _admin_refused(_admin(cfg, box), "driver_upgrade_needs_reboot")
    assert box.remote_commands()[-1] == box_up.cmd_driver_install("nvidia-driver-580")


def test_the_driver_floor_compares_versions_not_strings(tmp_path):
    cfg = _admin_config(tmp_path, "--driver-floor", "580.65.06")
    box = FakeBox(cfg, smi=(0, f"{KIND}, {UUID}, 40960 MiB, 580.105.08\n"))
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.driver_installs == 0


def test_every_ssh_to_the_box_is_a_fresh_login_never_a_shared_connection(tmp_path):
    """The door multiplexes ssh to lane boxes (GPUYard ~/.ssh/config, 18 Nov 2026): a reused master would skip the
    lane-key login and the pinned host key this run must prove."""
    for cfg in (_admin_config(tmp_path), _config(tmp_path)):
        argv = box_up.ssh(cfg, "kh", "true")
        options = [argv[i + 1] for i, a in enumerate(argv) if a == "-o"]
        assert "ControlPath=none" in options and "ControlMaster=no" in options
        assert argv.index("ControlPath=none") < argv.index("--")


def test_a_host_key_that_is_not_the_operators_refuses_before_any_ssh(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, keyscan=f"{IP} ssh-ed25519 {_key_body(99)}\n")
    _admin_refused(_admin(cfg, box), "host_key_mismatch")
    assert [argv[0] for argv, _ in box.calls] == ["ssh-keyscan"]


def test_no_host_key_refuses(tmp_path):
    cfg = _admin_config(tmp_path)
    _admin_refused(_admin(cfg, FakeBox(cfg, keyscan="")), "host_key_unavailable")


def test_too_few_cpus_refuses(tmp_path):
    cfg = _admin_config(tmp_path)
    outcome = _admin(cfg, FakeBox(cfg, nproc=15))
    _admin_refused(outcome, "slot_shape_cpus")
    assert outcome["step"] == "shape"


def test_too_little_memory_refuses(tmp_path):
    cfg = _admin_config(tmp_path)
    for mem in (64 * 1024 * 1024, 120 * 1024 * 1024 - 1):
        _admin_refused(_admin(cfg, FakeBox(cfg, mem_kib=mem)), "slot_shape_memory")


def test_exactly_the_minimum_shape_passes(tmp_path):
    cfg = _admin_config(tmp_path)
    # 7 slots x 4 vCPUs x 16 GiB + 8 GiB for the host (owner, 17 Nov 2026)
    box = FakeBox(cfg, nproc=28, online="0-27", mem_kib=120 * 1024 * 1024)
    assert _admin(cfg, box)["admin"] == "PASS"


def test_the_shape_counts_all_cpus_and_needs_0_to_27_online(tmp_path):
    assert box_up.CMD_SHAPE.startswith("nproc --all;")
    assert "/sys/devices/system/cpu/online" in box_up.CMD_SHAPE
    cfg = _admin_config(tmp_path)
    _admin_refused(
        _admin(cfg, FakeBox(cfg, nproc=32, online="0-7,16-31")), "slot_cpus_offline"
    )
    assert box_up.cpu_list("0-3,8,10-11") == {0, 1, 2, 3, 8, 10, 11}


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
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    final = json.loads(box.daemon)
    assert final["features"]["containerd-snapshotter"] is True
    assert final["runtimes"]["nvidia"]["path"] == "nvidia-container-runtime"
    assert final["log-driver"] == "json-file"


def test_a_daemon_without_the_snapshotter_after_restart_refuses(tmp_path):
    cfg = _admin_config(tmp_path)

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

    _admin_refused(_admin(cfg, NoSnapshotter(cfg)), "docker_snapshotter_missing")


def test_a_merged_daemon_json_the_daemon_does_not_show_gets_a_restart(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(
        cfg,
        docker="29.1.3",
        ctk=True,
        daemon=box_up.daemon_json_text(MERGED_DAEMON),
        daemon_live={"runtimes": MERGED_DAEMON["runtimes"]},
    )
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.restarts == 1


def test_a_daemon_that_is_right_is_not_restarted(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.restarts == 1


def test_docker_info_that_is_not_an_object_is_a_typed_refusal(tmp_path):
    cfg = _admin_config(tmp_path)

    class Odd(FakeBox):
        def remote(self, cmd, pipe_from):
            if cmd == box_up.CMD_DOCKER_INFO:
                return 0, "[1]", ""
            return super().remote(cmd, pipe_from)

    _admin_refused(_admin(cfg, Odd(cfg)), "docker_unreadable")


def test_a_box_with_another_containerd_is_reinstalled_to_the_pinned_one(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, docker="29.1.3", containerd="v2.1.0")
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.containerd == "v2.4.2"
    install = box_up.cmd_docker_install("29.1.3", "2.4.2")
    assert (
        '"containerd.io=$c"' in install
        and "apt-mark hold docker-ce docker-ce-cli containerd.io" in install
    )


def test_a_containerd_that_stays_wrong_is_refused(tmp_path):
    cfg = _admin_config(tmp_path)

    class Stuck(FakeBox):
        def remote(self, cmd, pipe_from):
            if cmd == box_up.cmd_docker_install(
                cfg.docker_version, cfg.containerd_version
            ):
                self.docker = cfg.docker_version
                return 0, "", ""
            return super().remote(cmd, pipe_from)

    _admin_refused(
        _admin(cfg, Stuck(cfg, containerd="v2.1.0")), "containerd_version_mismatch"
    )


def test_engine_versions_reads_docker_and_containerd():
    assert box_up.engine_versions("29.1.3 v2.4.2\n") == "29.1.3 2.4.2"
    assert box_up.engine_versions("29.1.3\n") == ""
    assert box_up.engine_versions("") == ""


def test_the_authorized_keys_line_is_exact(tmp_path):
    assert box_up.authorized_keys_line(DOOR, LANE_PUBKEY) == LANE_LINE
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.authorized_keys == LANE_LINE + "\n"
    assert "--home-dir /home/carbon-grade" in box_up.CMD_LANE_CREATE


def test_authorized_keys_that_read_back_differently_refuse(tmp_path):
    cfg = _admin_config(tmp_path)

    class Extra(FakeBox):
        def remote(self, cmd, pipe_from):
            rc, out, err = super().remote(cmd, pipe_from)
            if cmd == box_up.CMD_AUTHORIZED_KEYS_READ:
                out += "ssh-ed25519 AAAA other\n"
            return rc, out, err

    _admin_refused(_admin(cfg, Extra(cfg)), "authorized_keys_mismatch")


def test_a_lane_user_with_uid_zero_refuses(tmp_path):
    cfg = _admin_config(tmp_path)
    _admin_refused(_admin(cfg, FakeBox(cfg, lane_uid="0")), "lane_user_is_root")


def test_a_lane_user_with_another_home_refuses(tmp_path):
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg, lane_uid="1001", lane_home="/srv/carbon-grade")
    _admin_refused(_admin(cfg, box), "lane_home_mismatch")


def test_a_private_key_as_the_lane_key_is_refused(tmp_path):
    argv = _admin_argv(tmp_path)
    (tmp_path / "lane.pub").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----\n"
    )
    assert _config_refusal(argv) == "lane_pubkey_is_private"


def test_an_admin_dry_run_runs_nothing_and_prints_every_command(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("the dry run ran a command")

    assert box_up.main([*_admin_argv(tmp_path), "--dry-run"], runner=boom) == 0
    out = capsys.readouterr().out
    assert f"ssh-keyscan -t ed25519 -p 22 {IP}" in out
    assert "nvidia-ctk runtime configure --runtime=docker" in out
    assert f"ubuntu@{IP}" in out and "carbon-grade@" not in out
    printed = [line for line in out.splitlines() if line.startswith("[")]
    assert len(printed) == len(box_up.plan_admin(_admin_config(tmp_path)))


# == the door phase: who it is and what it may do =====================================================================


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
    assert document["slot_cpusets"] == [
        "0-3",
        "4-7",
        "8-11",
        "12-15",
        "16-19",
        "20-23",
        "24-27",
    ]
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
    # the door's box pool reads exactly this file at its next build (`remote_gpu_build.read_box`): no restart
    from carbon.reconstruction import remote_gpu_build

    lane = remote_gpu_build.read_box(path, kind=KIND, slots=4, root=tmp_path / "host")
    assert (
        lane.spec.name == "a100-1" and lane.spec.docker_host == document["docker_host"]
    )
    assert (
        lane.spec.host_key == document["host_key"] and lane.device.device_uuid == UUID
    )
    assert lane.spec.images == (JAX, TORCH)
    assert lane.spec.slot_cpusets == remote_gpu_build.BOX_SLOT_CPUSETS
    assert box.loaded == {JAX: JAX, TORCH: TORCH} and box.tree
    # The door changed nothing the admin phase owns.
    assert box.restarts == 0 and box.driver_installs == 0


def test_the_door_phase_never_uses_sudo_on_the_box(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert set(box.users) == {"carbon-grade"}
    for command in box.remote_commands():
        assert "sudo" not in command, command
    for _step, command in box_up.plan_door(cfg):
        assert "sudo" not in command, command


def test_the_door_guard_refuses_a_sudo_command(tmp_path):
    cfg = _config(tmp_path)
    session = box_up.Session(cfg, FakeBox(cfg), log=lambda _l: None)
    with pytest.raises(box_up.Refused) as refused:
        session.call(box_up.ssh(cfg, "kh", "sudo -n true"))
    assert refused.value.reason == "door_sudo_refused"


def test_the_door_logs_in_only_as_carbon_grade(tmp_path):
    cfg = _config(tmp_path)
    assert cfg.user == "carbon-grade"
    with pytest.raises(SystemExit):
        box_up.build_parser().parse_args([*_door_argv(tmp_path), "--user", "ubuntu"])


# The admin phase's work, one item missing at a time: the door names the admin step to re-run, and changes nothing.
ADMIN_ITEMS = [
    ("lane_user", {"lane_uid": ""}),
    ("lane_user", {"authorized_keys": f'from="{DOOR}" {LANE_PUBKEY}\n'}),
    ("lane_user", {"groups": ["carbon-grade"]}),
    ("lane_user", {"lane_home": "/srv/carbon-grade"}),
    ("lane_user", {"authorized_keys": LANE_LINE + "\nssh-ed25519 AAAA other\n"}),
    ("shape", {"nproc": 8}),
    ("shape", {"mem_kib": 32 * 1024 * 1024}),
    ("driver", {"smi": (0, f"{KIND}, {UUID}, 40960 MiB, 570.172.08\n")}),
    ("driver", {"smi": (9, "NVIDIA-SMI has failed\n")}),
    ("driver", {"smi": (0, f"NVIDIA A100-SXM4-80GB, {UUID}, 81920 MiB, {DRIVER}\n")}),
    ("docker", {"docker": ""}),
    ("docker", {"docker": "28.0.1"}),
    ("docker", {"containerd": "v2.1.0"}),
    ("docker", {"daemon_live": {"runtimes": MERGED_DAEMON["runtimes"]}}),
    ("docker", {"daemon_live": {"features": {"containerd-snapshotter": True}}}),
    ("stage_root", {"stage": "root:root 755 directory"}),
    ("stage_root", {"stage": "carbon-grade:carbon-grade 777 directory"}),
    ("python", {"python": ""}),
]


@pytest.mark.parametrize(("step", "missing"), ADMIN_ITEMS)
def test_the_door_refuses_when_an_admin_item_is_missing(tmp_path, step, missing):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, **missing)
    outcome = _run(cfg, box)
    _refused(outcome, f"admin_incomplete:{step}")
    assert outcome["step"] == step
    assert box.restarts == 0 and box.driver_installs == 0 and not box.loaded
    assert not box.tree
    assert _no_box_file(tmp_path)


def _admin_summary(**changes):
    """The admin phase's PASS summary of the FakeBox (its exact fields)."""
    summary = {
        "schema": "carbon.gpu-box-admin.v1",
        "admin": "PASS",
        "box_ip": IP,
        "port": 22,
        "host_key": f"{IP} ssh-ed25519 {HOST_KEY}",
        "device_kind": KIND,
        "device_uuid": UUID,
        "driver_version": DRIVER,
        "docker_version": "29.1.3",
        "containerd_version": "2.4.2",
        "shape": {"cpus": 30, "online": "0-29", "mem_total_kib": 216 * 1024 * 1024},
        "lane_user": "carbon-grade",
        "stage_root": "/home/carbon",
        "seconds": 300.0,
    }
    summary.update(changes)
    return summary


def test_a_matching_admin_summary_is_recorded(tmp_path):
    summary = _admin_summary()
    (tmp_path / "admin.json").write_text(json.dumps(summary))
    cfg = _config(tmp_path, "--admin-summary", str(tmp_path / "admin.json"))
    assert _run(cfg, FakeBox(cfg))["status"] == "ADMITTED"
    document = json.loads((tmp_path / "boxes" / "a100-1.json").read_text())
    assert document["admin_summary_sha256"] == _sha(
        (tmp_path / "admin.json").read_bytes()
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("host_key", f"{IP} ssh-ed25519 {_key_body(42)}"),
        ("device_uuid", "GPU-ffffffff-4567-89ab-cdef-0123456789ab"),
        ("driver_version", "580.65.06"),
        ("box_ip", "203.0.113.8"),
        ("port", 2222),
        ("device_kind", "NVIDIA A100-SXM4-80GB"),
        ("docker_version", "28.0.0"),
        ("containerd_version", "2.1.0"),
        ("shape", {"cpus": 16, "online": "0-15", "mem_total_kib": 80 * 1024 * 1024}),
        ("lane_user", "ubuntu"),
        ("stage_root", "/srv/carbon"),
    ],
)
def test_an_admin_summary_that_disagrees_with_the_box_is_refused(
    tmp_path, field, value
):
    summary = _admin_summary(**{field: value})
    (tmp_path / "admin.json").write_text(json.dumps(summary))
    cfg = _config(tmp_path, "--admin-summary", str(tmp_path / "admin.json"))
    box = FakeBox(cfg)
    outcome = _run(cfg, box)
    _refused(outcome, "admin_summary_mismatch")
    assert outcome["detail"].startswith(field)
    assert not box.loaded and _no_box_file(tmp_path)


def test_an_admin_summary_that_did_not_pass_is_refused(tmp_path):
    (tmp_path / "admin.json").write_text(
        json.dumps({"schema": "carbon.gpu-box-admin.v1", "admin": "REFUSED"})
    )
    argv = _door_argv(tmp_path, "--admin-summary", str(tmp_path / "admin.json"))
    assert _config_refusal(argv) == "admin_summary_invalid"


def test_the_device_record_digest_is_the_one_the_door_reads():
    from carbon.reconstruction.host_inventory import HostDeviceRecord

    document = _device_document()
    digest = box_up._device_record(document)
    assert digest == HostDeviceRecord(document, digest).digest
    bad = {**document, "device_uuid": "not-a-uuid"}
    with pytest.raises(box_up.Refused) as refused:
        box_up._device_record(bad)
    assert refused.value.reason == "device_record_invalid"


def test_the_device_record_is_prepared_as_carbon_grade_in_its_own_directory(tmp_path):
    cfg = _config(tmp_path)
    words = shlex.split(box_up.cmd_prepare(cfg, HEAD, "/usr/bin/python3.11"))
    assert words[:3] == [
        "/usr/bin/python3.11",
        "-I",
        f"/home/carbon-grade/carbon-box-up/tree-{HEAD}/scripts/dev/carbon_accelerator.py",
    ]
    assert ("--host-root", "/home/carbon-grade/carbon-box-up/host-root") in set(
        itertools.pairwise(words)
    )


def test_the_admin_phase_installs_a_python_the_device_record_can_run_on(tmp_path):
    """Lambda's Ubuntu 22.04 has only Python 3.10 as python3; Carbon needs >= 3.11 (TE3, 17 Nov 2026: the first live
    door phase refused at ``device``). The admin phase installs python3.11 when no newer one is present, once; the
    door phase runs the device record with it, and refuses (admin_incomplete:python) when there is none.
    """
    cfg = _admin_config(tmp_path)
    box = FakeBox(cfg)
    summary = box_up.run_admin(cfg, box, log=lambda line: None)
    assert summary["admin"] == "PASS", summary
    assert box.python_installs == 1 and box.python == "/usr/bin/python3.11"
    again = box_up.run_admin(cfg, box, log=lambda line: None)
    assert again["admin"] == "PASS" and box.python_installs == 1
    newer = FakeBox(cfg, python="/usr/bin/python3.12")
    assert box_up.run_admin(cfg, newer, log=lambda line: None)["admin"] == "PASS"
    assert newer.python_installs == 0
    words = shlex.split(box_up.cmd_prepare(cfg, HEAD, "/usr/bin/python3.12"))
    assert words[:2] == ["/usr/bin/python3.12", "-I"]
    door = _config(tmp_path)
    ran = FakeBox(door, python="/usr/bin/python3.12")
    assert _run(door, ran)["status"] == "ADMITTED"
    assert (
        box_up.cmd_prepare(door, HEAD, "/usr/bin/python3.12") in ran.remote_commands()
    )
    # a path that is not an absolute python3.1x is never run
    odd = FakeBox(door, python="python3.11; rm -rf /")
    _refused(_run(door, odd), "admin_incomplete:python")


#: carbon-door's own lane key on the same box (Lead 17 Nov 2026: a box may serve two doors)
OTHER_DOOR_LINE = (
    'restrict,from="198.51.100.9" ssh-ed25519 ' + "B" * 68 + " carbon-door-lane"
)


def test_the_admin_phase_keeps_another_doors_lane_key_and_drops_anything_else(tmp_path):
    """authorized_keys is merged, never replaced: this door's line first, another door's restricted lane-key line
    kept, any other line (an unrestricted key above all) dropped; the door phase passes with both doors' lines.
    """
    cfg = _admin_config(tmp_path, "--other-door-ip", "198.51.100.9")
    loose = "ssh-ed25519 " + "C" * 68 + " someone"
    box = FakeBox(
        cfg,
        prepared=True,
        authorized_keys=f"{OTHER_DOOR_LINE}\n{loose}\n{OTHER_DOOR_LINE}\n",
    )
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.authorized_keys == f"{LANE_LINE}\n{OTHER_DOOR_LINE}\n"
    # run again: unchanged
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.authorized_keys == f"{LANE_LINE}\n{OTHER_DOOR_LINE}\n"
    door = _config(tmp_path, "--other-door-ip", "198.51.100.9")
    both = FakeBox(door, authorized_keys=f"{LANE_LINE}\n{OTHER_DOOR_LINE}\n")
    assert _run(door, both)["status"] == "ADMITTED"
    # a door that names no other door accepts only its own line
    alone = _config(tmp_path)
    _refused(
        _run(
            alone, FakeBox(alone, authorized_keys=f"{LANE_LINE}\n{OTHER_DOOR_LINE}\n")
        ),
        "admin_incomplete:lane_user",
    )


def test_a_restricted_line_of_an_unknown_door_is_dropped(tmp_path):
    """V2 (17 Nov 2026): only the configured other doors' lines stay; a well-formed restrict,from= line of any other
    address (planted by anyone who once could write the file) is dropped by the admin phase and refused by the door.
    """
    planted = 'restrict,from="203.0.113.66" ssh-ed25519 ' + "D" * 68 + " planted"
    cfg = _admin_config(tmp_path, "--other-door-ip", "198.51.100.9")
    box = FakeBox(cfg, prepared=True, authorized_keys=f"{planted}\n{OTHER_DOOR_LINE}\n")
    assert _admin(cfg, box)["admin"] == "PASS"
    assert box.authorized_keys == f"{LANE_LINE}\n{OTHER_DOOR_LINE}\n"
    door = _config(tmp_path, "--other-door-ip", "198.51.100.9")
    _refused(
        _run(door, FakeBox(door, authorized_keys=f"{LANE_LINE}\n{planted}\n")),
        "admin_incomplete:lane_user",
    )
    assert box_up.merged_authorized_keys(
        f"{planted}\n", LANE_LINE, ("198.51.100.9",)
    ) == (
        f"{LANE_LINE}\n",
        1,
    )


def test_this_doors_own_line_need_not_be_a_plain_ed25519_line():
    """The door's own key may carry any comment its configuration accepted (review MED-1): only OTHER doors' lines
    must be the strict lane-key form."""
    own = 'restrict,from="203.0.113.5" ssh-ed25519 ' + "A" * 68 + " ryan laptop: lane"
    other = 'restrict,from="198.51.100.9" ssh-ed25519 ' + "B" * 68 + " carbon-door-lane"
    doors = ("198.51.100.9",)
    merged, dropped = box_up.merged_authorized_keys(f"{other}\n", own, doors)
    assert merged == f"{own}\n{other}\n" and dropped == 0
    assert box_up.authorized_keys_ok(merged, own, doors)
    # IPv6 / other forms of another door's line are dropped, never kept
    v6 = 'restrict,from="2001:db8::1" ssh-ed25519 ' + "B" * 68
    assert box_up.merged_authorized_keys(f"{v6}\n", own, doors) == (f"{own}\n", 1)


@pytest.mark.parametrize(
    "keys",
    [
        lambda: f"{LANE_LINE}\nssh-ed25519 " + "C" * 68 + "\n",
        lambda: f"{LANE_LINE}\n" + 'from="198.51.100.9" ssh-ed25519 ' + "B" * 68 + "\n",
        lambda: f"{LANE_LINE}\n{LANE_LINE}\n",
        lambda: f"{LANE_LINE}",
        lambda: f"{OTHER_DOOR_LINE}\n",
        lambda: f"{OTHER_DOOR_LINE}\n{LANE_LINE}\n",
        lambda: f"{LANE_LINE}\r\n",
    ],
)
def test_the_door_refuses_any_line_but_door_lane_keys(tmp_path, keys):
    door = _config(tmp_path)
    box = FakeBox(door, authorized_keys=keys())
    # (without this door's own line it cannot even log in: the same refusal)
    _refused(_run(door, box), "admin_incomplete:lane_user")


def test_the_class_check_runs_like_the_receipted_runner(tmp_path):
    cfg = _config(tmp_path)
    words = shlex.split(box_up.cmd_class_check(cfg, HEAD, UUID))
    image = words.index(JAX)
    flags = words[:image]
    assert flags[:2] == ["docker", "run"]
    pairs = set(itertools.pairwise(flags))
    for pair in (
        ("--user", "65532:65532"),
        ("--network", "none"),
        ("--tmpfs", "/scratch:rw,size=4g"),
        ("--runtime", "nvidia"),
        ("--gpus", f"device={UUID}"),
        ("-v", f"/home/carbon-grade/carbon-box-up/tree-{HEAD}:/carbon:ro"),
        ("-v", "/home/carbon-grade/carbon-box-up/class-check:/out"),
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


def test_the_class_check_output_dir_needs_no_root(tmp_path):
    """A fresh 0703 directory in carbon-grade's 0700 work dir: the container (uid 65532) creates its files, carbon-grade
    reads them only when that uid owns them, and removes the directory afterwards."""
    cfg = _config(tmp_path)
    out = box_up.cmd_class_out(cfg)
    assert out.endswith(
        "rm -rf /home/carbon-grade/carbon-box-up/class-check; "
        "mkdir -m 0703 /home/carbon-grade/carbon-box-up/class-check"
    )
    assert box_up.DOOR_WORK_DIR.endswith("chmod 0700 /home/carbon-grade/carbon-box-up")
    for read in (box_up.CMD_CLASS_OUTPUT_READ, box_up.CMD_CLASS_OPS_READ):
        assert "-maxdepth 0 -type f -user 65532 -size -16777216c" in read
        assert "timeout 30 head -c 16777216 --" in read
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.cleans == 1
    failed = FakeBox(cfg, class_rc=1)
    _refused(_run(cfg, failed), "class_check_failed")
    assert failed.cleans == 1


def test_a_second_door_run_loads_nothing_again(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    box.calls.clear()
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box_up.DOOR_DOCKER_LOAD not in box.remote_commands()


def test_a_door_host_key_mismatch_refuses_before_any_ssh(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg, keyscan=f"{IP} ssh-ed25519 {_key_body(99)}\n")
    _refused(_run(cfg, box), "host_key_mismatch")
    assert [argv[0] for argv, _ in box.calls] == ["ssh-keyscan"]
    assert _no_box_file(tmp_path)


@pytest.mark.parametrize("phase", ["admin", "door"])
def test_every_ssh_pins_the_host_key(tmp_path, phase):
    cfg = _admin_config(tmp_path) if phase == "admin" else _config(tmp_path)
    box = FakeBox(cfg)
    if phase == "admin":
        assert _admin(cfg, box)["admin"] == "PASS"
    else:
        assert _run(cfg, box)["status"] == "ADMITTED"
    for argv, _ in box.calls:
        if argv[0] == "ssh":
            assert "StrictHostKeyChecking=yes" in argv
            assert "GlobalKnownHostsFile=/dev/null" in argv
            assert "ForwardAgent=no" in argv and "ClearAllForwardings=yes" in argv


def test_an_image_whose_id_differs_after_loading_is_refused(tmp_path):
    cfg = _config(tmp_path)
    outcome = _run(cfg, FakeBox(cfg, load_as={TORCH: "sha256:" + "f" * 64}))
    _refused(outcome, "image_id_mismatch")
    assert outcome["step"] == "images"
    assert _no_box_file(tmp_path)


# == the door phase: the class check ==================================================================================


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


def _box_with(cfg, record):
    return FakeBox(
        cfg, class_output=json.dumps(record), class_ops=json.dumps(_ops_record(record))
    )


def test_a_case_not_on_the_gpu_refuses(tmp_path):
    cfg = _config(tmp_path)
    box = _box_with(cfg, _class_record(DIGESTS, on_gpu=False))
    _refused(_run(cfg, box), "class_check_not_on_gpu")


def test_digests_that_differ_from_the_class_record_refuse(tmp_path):
    cfg = _config(tmp_path)
    other = {**DIGESTS, "graph:motor/softmax": "sha256:" + "9" * 64}
    outcome = _run(cfg, _box_with(cfg, _class_record(other)))
    _refused(outcome, "class_check_digest_mismatch")
    assert "graph:motor/softmax state_digest" in outcome["detail"].split(", ")
    assert _no_box_file(tmp_path)


def test_a_case_missing_from_the_class_record_refuses(tmp_path):
    cfg = _config(tmp_path)
    record = _class_record({**DIGESTS, "graph:f02/norm": "sha256:" + "4" * 64})
    _refused(_run(cfg, _box_with(cfg, record)), "class_check_digest_mismatch")


def test_a_run_that_exits_nonzero_never_passes(tmp_path):
    cfg = _config(tmp_path)
    _refused(_run(cfg, FakeBox(cfg, class_rc=1)), "class_check_failed")
    _refused(_run(cfg, FakeBox(cfg, class_output="")), "class_check_failed")


def test_a_class_check_on_a_device_whose_name_only_starts_with_the_kind_refuses(
    tmp_path,
):
    cfg = _config(tmp_path)
    record = _class_record(DIGESTS)
    record["nvidia_smi"]["gpus"] = [f"{KIND} SPECIAL, {DRIVER}, 40960 MiB, 8.0"]
    _refused(_run(cfg, _box_with(cfg, record)), "class_check_wrong_device")


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


def test_the_ops_record_compares_as_canonical_json():
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


# == the door phase: its references and arguments =====================================================================


def test_a_reference_class_record_that_did_not_repeat_is_refused(tmp_path):
    reference = _class_record(DIGESTS, identical={"graph:f08/conv": False})
    assert (
        _config_refusal(_door_argv(tmp_path, record=reference))
        == "class_record_not_gpu_repeats"
    )


def _incomplete(mutate):
    reference = _class_record(DIGESTS)
    mutate(reference)
    return reference


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["cases"][0].pop("state_digest"),
        lambda r: r["cases"][0].update(state_digest=None),
        lambda r: r["cases"][1].update(rebuilds=[]),
        lambda r: r["cases"][1]["rebuilds"][0].pop("predictions_digest"),
        lambda r: r["cases"][2]["rebuilds"][1].update(state_digest=""),
        lambda r: r["cases"][2].update(ran_on_gpu=None),
        lambda r: r["cases"][0].update(bit_identical="yes"),
        lambda r: r.update(all_on_gpu=None),
        lambda r: r.pop("all_bit_identical"),
    ],
    ids=[
        "no-state-digest",
        "null-state-digest",
        "no-rebuilds",
        "rebuild-without-predictions",
        "empty-rebuild-state",
        "ran-on-gpu-missing",
        "bit-identical-not-true",
        "all-on-gpu-missing",
        "all-bit-identical-missing",
    ],
)
def test_an_incomplete_reference_class_record_is_refused(tmp_path, mutate):
    """Validator-2: the digest compare is symmetric, so a field missing from BOTH the reference and the box's record
    would match; an incomplete reference is refused before any box is touched."""
    argv = _door_argv(tmp_path, record=_incomplete(mutate))
    assert _config_refusal(argv) == "class_record_incomplete"


def test_the_complete_reference_fixture_is_accepted():
    box_up.require_complete_reference(_class_record(DIGESTS))


def test_the_manifest_image_must_be_the_jax_image(tmp_path):
    other = "sha256:" + "e" * 64
    assert (
        _config_refusal(_door_argv(tmp_path, manifest=_manifest(image=other)))
        == "graph_gpu_image_mismatch"
    )


def test_a_manifest_that_is_not_the_jax_gpu_worker_is_refused(tmp_path):
    manifest = _manifest(lock="sha256:" + "9" * 64)
    assert (
        _config_refusal(_door_argv(tmp_path, manifest=manifest))
        == "graph_gpu_image_not_jax"
    )


def test_a_malformed_manifest_is_refused(tmp_path):
    manifest = {**_manifest(), "extra": 1}
    assert (
        _config_refusal(_door_argv(tmp_path, manifest=manifest))
        == "graph_gpu_image_manifest_invalid"
    )


def test_a_provider_the_owner_did_not_accept_is_refused(tmp_path):
    argv = _door_argv(tmp_path)
    argv[argv.index("--provider") + 1] = "otherprovider"
    assert _config_refusal(argv) == "provider_not_accepted"


def test_bad_arguments_exit_2_without_running(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("ran a command")

    argv = _door_argv(tmp_path)
    argv[argv.index("--jax-image") + 1] = "jax:latest"
    assert box_up.main(argv, runner=boom) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "bad_argument"


def test_a_door_dry_run_runs_nothing_and_prints_every_command(tmp_path, capsys):
    def boom(argv, pipe_from=None):
        raise AssertionError("the dry run ran a command")

    assert box_up.main([*_door_argv(tmp_path), "--dry-run"], runner=boom) == 0
    out = capsys.readouterr().out
    assert not (tmp_path / "boxes").exists()
    assert f"ssh-keyscan -t ed25519 -p 22 {IP}" in out
    assert f"docker save {TORCH} | ssh" in out
    assert "gpu_rebuild_class_check.py" in out and "--steps 512" in out
    assert f"carbon-grade@{IP}" in out and "ubuntu@" not in out
    assert "sudo" not in out
    printed = [line for line in out.splitlines() if line.startswith("[")]
    assert len(printed) == len(box_up.plan_door(_config(tmp_path)))


# == the door phase: files ============================================================================================


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
    words = shlex.split(box_up.cmd_class_check(cfg, HEAD, UUID))
    assert document["class_check_image_id"] in words


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
    _refused(_run(cfg, box), "admin_incomplete:stage_root")
    assert _no_box_file(tmp_path)


def test_a_failed_readmission_removes_an_earlier_admission(tmp_path):
    cfg = _config(tmp_path)
    assert _run(cfg, FakeBox(cfg))["status"] == "ADMITTED"
    assert len(list((tmp_path / "boxes").iterdir())) == 3
    _refused(_run(cfg, FakeBox(cfg, nproc=8)), "admin_incomplete:shape")
    assert _no_box_file(tmp_path)


def test_a_stale_symlink_is_removed_not_followed(tmp_path):
    cfg = _config(tmp_path)
    (tmp_path / "boxes").mkdir(mode=0o700)
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    (tmp_path / "boxes" / "a100-1.json").symlink_to(target)
    _refused(_run(cfg, FakeBox(cfg, nproc=8)), "admin_incomplete:shape")
    assert not os.path.lexists(tmp_path / "boxes" / "a100-1.json")
    assert target.read_text() == "{}"


def test_a_box_file_that_appears_during_the_run_is_never_replaced(
    tmp_path, monkeypatch
):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    real = box_up.write_box_files

    def racing(cfg_, document, raw_output, raw_ops):
        box_up.box_path(cfg_).write_text("another run")
        os.chmod(box_up.box_path(cfg_), 0o600)
        return real(cfg_, document, raw_output, raw_ops)

    monkeypatch.setattr(box_up, "write_box_files", racing)
    _refused(_run(cfg, box), "box_file_exists")
    assert not any(os.path.lexists(p) for p in box_up.box_files(cfg))


def test_an_unexpected_error_writing_the_box_file_leaves_no_files(
    tmp_path, monkeypatch
):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    real = box_up.write_private

    def failing(directory, path, body):
        if path == box_up.box_path(cfg):
            raise OSError("disk full")
        return real(directory, path, body)

    monkeypatch.setattr(box_up, "write_private", failing)
    with pytest.raises(OSError):
        _run(cfg, box)
    assert not any(os.path.lexists(p) for p in box_up.box_files(cfg))


# == the door phase: only public material leaves the door ==============================================================


def test_only_public_material_goes_to_the_box(tmp_path):
    cfg = _config(tmp_path, "--ssh-key", str(tmp_path / "lane_key"))
    (tmp_path / "lane_key").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n")
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    streamed = [pipe for _, pipe in box.calls if pipe is not None]
    assert streamed == [
        ["docker", "save", JAX],
        ["docker", "save", TORCH],
        ["git", "-C", str(box_up.ROOT), "archive", "--format=tar", HEAD, "--"]
        + list(box_up.TREE_PATHS),
    ]
    for argv, _ in box.calls:
        text = " ".join(argv)
        assert "PRIVATE KEY" not in text and "secret" not in text
    # the box file names the lane key's PATH (the door's builds use exactly it), never its contents
    document = json.loads((tmp_path / "boxes" / "a100-1.json").read_text())
    assert document["ssh_key"] == str(tmp_path / "lane_key")
    assert "secret" not in json.dumps(document)


def test_the_guard_refuses_any_other_upload(tmp_path):
    cfg = _config(tmp_path)
    session = box_up.Session(cfg, FakeBox(cfg), log=lambda _l: None)
    for pipe in (
        ["git", "-C", str(box_up.ROOT), "archive", "--format=tar", HEAD],
        box_up.cmd_git_archive(HEAD) + [".agent"],
        ["cat", str(tmp_path / "lane_key")],
        ["docker", "save", "sha256:" + "e" * 64],
        ["tar", "-c", "/home"],
    ):
        with pytest.raises(box_up.Refused) as refused:
            session.call(["ssh", "x"], pipe)
        assert refused.value.reason == "upload_refused"
    with pytest.raises(box_up.Refused) as refused:
        session.call(["ssh", "x", "echo '-----BEGIN RSA PRIVATE KEY-----'"])
    assert refused.value.reason == "secret_refused"


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
    _refused(_run(cfg, box), "tree_not_on_origin_main")
    assert box.extracts == 0
    assert not [pipe for _, pipe in box.calls if pipe and pipe[0] == "git"]


def test_the_tree_is_extracted_afresh_on_every_run_into_carbon_grades_dir(tmp_path):
    cfg = _config(tmp_path)
    box = FakeBox(cfg)
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert _run(cfg, box)["status"] == "ADMITTED"
    assert box.extracts == 2
    extract = box_up.cmd_tree_extract(HEAD)
    assert extract.startswith(
        "set -eu; rm -rf /home/carbon-grade/carbon-box-up/tree-*;"
    )
    assert f"mv /home/carbon-grade/carbon-box-up/tree-{HEAD}.part " in extract


# == malformed box output ==============================================================================================


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


def test_an_unexpected_shape_inside_a_step_is_a_typed_refusal(tmp_path):
    """Any parse error a step did not foresee becomes `<step>_output_invalid`, never a traceback."""
    cfg = _config(tmp_path)
    session = box_up.Session(cfg, FakeBox(cfg), log=lambda _l: None)

    def odd():
        return {"a": 1}["missing"]

    with pytest.raises(box_up.Refused) as refused:
        session.run_step("images", odd)
    assert refused.value.reason == "images_output_invalid"
    assert refused.value.detail.startswith("KeyError")


# == the documented limit ==============================================================================================


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


# -- review of the phase split: the class-check output and the admin summary ------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.pop("shape"),
        lambda s: s.update(extra=1),
        lambda s: s.update(port="22"),
        lambda s: s.update(port=True),
        lambda s: s.update(seconds="300"),
        lambda s: s.update(shape=[30]),
    ],
    ids=["missing", "extra", "port-str", "port-bool", "seconds-str", "shape-list"],
)
def test_an_admin_summary_not_exactly_the_admin_phase_document_is_refused(
    tmp_path, mutate
):
    summary = _admin_summary()
    mutate(summary)
    (tmp_path / "admin.json").write_text(json.dumps(summary))
    argv = _door_argv(tmp_path, "--admin-summary", str(tmp_path / "admin.json"))
    assert _config_refusal(argv) == "admin_summary_invalid"


def test_an_empty_admin_summary_path_is_refused_not_ignored(tmp_path):
    assert (
        _config_refusal(_door_argv(tmp_path, "--admin-summary", ""))
        == "admin_summary_invalid"
    )


def _sh(script, cwd):
    return subprocess.run(
        ["sh", "-c", script], cwd=cwd, capture_output=True, text=True, check=False
    )


def _local_read(tmp_path, name, uid):
    """`_read_worker_file`'s script with the box paths and the worker uid replaced by local ones."""
    out = tmp_path / "out"
    script = box_up._read_worker_file(name).replace(box_up.CLASS_OUT, str(out))
    return _sh(script.replace(f"-user {box_up.WORKER_UID}", f"-user {uid}"), tmp_path)


@pytest.mark.skipif(sys.platform != "linux", reason="GNU find/head/timeout")
def test_the_worker_file_read_refuses_a_symlink_a_fifo_and_a_directory(tmp_path):
    uid = os.getuid()
    out = tmp_path / "out"
    out.mkdir()
    secret = tmp_path / "secret"
    secret.write_text("authorized_keys line")
    (out / "class-check.json").symlink_to(secret)
    done = _local_read(tmp_path, "class-check.json", uid)
    assert done.returncode != 0 and "authorized_keys" not in done.stdout
    (out / "class-check.json").unlink()
    os.mkfifo(out / "class-check.json")
    done = _local_read(
        tmp_path, "class-check.json", uid
    )  # returns at once: never opens the FIFO
    assert done.returncode != 0 and done.stdout == ""
    (out / "class-check.json").unlink()
    (out / "class-check.json").mkdir()
    assert _local_read(tmp_path, "class-check.json", uid).returncode != 0
    (out / "class-check.json").rmdir()
    (out / "class-check.json").write_text('{"ok": 1}')
    done = _local_read(tmp_path, "class-check.json", uid)
    assert done.returncode == 0 and done.stdout == '{"ok": 1}'
    # a regular file of another owner: refused
    assert _local_read(tmp_path, "class-check.json", uid + 1).returncode != 0


@pytest.mark.skipif(sys.platform != "linux", reason="python in a subprocess")
def test_the_purge_program_removes_what_the_container_left_even_a_0000_dir(tmp_path):
    out = tmp_path / "out"
    (out / "sub" / "deep").mkdir(parents=True)
    (out / "sub" / "deep" / "x").write_text("x")
    (out / "f").write_text("f")
    os.symlink("/etc/hostname", out / "link")
    os.chmod(out / "sub" / "deep", 0)
    os.chmod(out / "sub", 0)
    program = box_up._PURGE_PROGRAM.replace("'/out'", repr(str(out)))
    done = subprocess.run(
        [sys.executable, "-I", "-c", program],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert list(out.iterdir()) == []
    assert os.path.exists("/etc/hostname")


def test_the_class_check_dir_is_purged_as_the_container_uid_before_and_after(tmp_path):
    cfg = _config(tmp_path)
    purge = box_up.cmd_class_purge(cfg)
    assert purge.startswith(
        "docker run --rm --user 65532:65532 --network none --read-only -v "
    )
    assert cfg.jax_image in purge and "sudo" not in purge
    assert purge in box_up.cmd_class_out(cfg) and "|| true" in box_up.cmd_class_out(cfg)
    assert box_up.cmd_class_clean(cfg).startswith(purge)
