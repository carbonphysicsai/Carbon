#!/usr/bin/env python3
"""Bring a freshly rented GPU box up as a remote GPU build lane, with one command from the door host.

Owner's order: rented A100 boxes are used on demand. A fresh rental is brought up with ONE command from the door in
under 20 minutes, and it must pass an automatic per-box class check before it takes work; a box that fails is never
used. This tool drives the box over ssh as its admin user (the operator's key), one idempotent step at a time, and
stops at the first failure with a typed reason:

  host_key     the box's ed25519 host key equals the operator's ``--host-key-fingerprint``; every later ssh pins it
  shape        >= 16 logical CPUs and >= 4 x 16 GiB + 8 GiB MemTotal (4 slots x 4 cores x 16 GiB, always)
  driver       exactly one GPU named ``--device-kind``, driver >= ``--driver-floor`` (an older one is upgraded from the
               provider's apt repo and the run stops: ``driver_upgrade_needs_reboot``)
  docker       Docker Engine ``--docker-version`` from Docker's apt repo, the containerd image store and the nvidia
               runtime merged into daemon.json, both shown by ``docker info``
  lane_user    ``carbon-grade`` (not root, in the docker group), authorized_keys exactly one door-restricted line
  stage_root   ``/home/carbon`` owned carbon-grade:carbon-grade, mode 0755
  images       each ``--image`` streamed from the door's daemon (``docker save | docker load``) and proved by its id
  tree         a world-readable copy of this Carbon tree (``git archive`` of HEAD)
  device       the box's host device record (``carbon_accelerator.py prepare`` on the box), fetched back
  class_check  ``gpu_rebuild_class_check.py`` in the pinned JAX image on the box's GPU: every case bit-identical and
               on the GPU, the ops record measured against allowlist v8, every case's state digest equal to the class
               record's and the ops record equal to the class's ops record

Only on PASS is the box file ``<--boxes-dir>/<--box-name>.json`` (schema ``carbon.remote-gpu-build-box.v1``) written,
atomically, 0600 in a 0700 directory. A run starts by removing a box file of that name, so a box that is being
(re)brought up, or that failed, is never offered. ``--dry-run`` prints every command it would run and runs none.

What goes to the box: the lane's PUBLIC key, the public Carbon tree, public worker images and daemon.json. Nothing
else (no private key, no agent forwarding). The tool never reboots a box and never touches the door's own daemon
beyond ``docker save``. A PASS is a per-box class check, not scientific or security qualification.

    python3 -I scripts/dev/gpu_box_up.py --ssh ubuntu@203.0.113.7 --box-name a100-1 --provider lambda \\
        --device-kind "NVIDIA A100-SXM4-40GB" --door-ip 198.51.100.2 --lane-pubkey lane.pub \\
        --host-key-fingerprint SHA256:... --jax-image sha256:... --image sha256:... \\
        --class-record a100-class-check.json --class-ops-record a100-ops-record.json --boxes-dir ~/.carbon/boxes
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.reconstruction.remote_lane import parse_docker_host

BOX_SCHEMA = "carbon.remote-gpu-build-box.v1"
CLASS_CHECK_SCHEMA = "carbon.gpu-rebuild.class-check.v1"
OPS_SCHEMA = "carbon.graph-gpu-ops.v1"
LANE_USER = "carbon-grade"
STAGE_ROOT = "/home/carbon"
#: The tool's own working directory on the box (the tree, the host record, the class-check output).
WORK = "/var/lib/carbon-box-up"
HOST_ROOT = f"{WORK}/host-root"
CLASS_OUT = f"{WORK}/class-check"
#: Every box has the same shape: 4 slots x 4 cores, 16 GiB RAM per slot, plus headroom for the host.
SLOT_CPUSETS = ("0-3", "4-7", "8-11", "12-15")
MIN_CPUS = 16
MIN_MEM_KIB = (len(SLOT_CPUSETS) * 16 + 8) * 1024 * 1024
WORKER_USER = "65532:65532"
WORKER_PYTHON = "/opt/carbon-worker/bin/python"
CLASS_CHECK_STEPS = 512
DEFAULT_DRIVER_FLOOR = "580.65.06"
DEFAULT_DRIVER_PACKAGE = "nvidia-driver-580-server"
DEFAULT_DOCKER_VERSION = "29.1.3"

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ADMIN = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_VERSION = re.compile(r"[0-9]+(\.[0-9]+)*")
_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
_PACKAGE = re.compile(r"[a-z0-9][a-z0-9.+-]{1,99}")
_DEVICE_KIND = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.\-]{0,95}")
_PUBLIC_KEY_TYPES = frozenset(
    {
        "ssh-ed25519",
        "ssh-rsa",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "sk-ssh-ed25519@openssh.com",
        "sk-ecdsa-sha2-nistp256@openssh.com",
    }
)


class Refused(Exception):
    """A typed stop: ``reason`` is a stable code, ``detail`` says what was seen."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _sha256(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


# -- configuration ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    admin: str
    ip: str
    port: int
    ssh_key: str | None
    name: str
    provider: str
    device_kind: str
    driver_floor: str
    driver_package: str
    docker_version: str
    door_ip: str
    lane_pubkey: str
    host_key_fingerprint: str
    images: tuple[str, ...]
    jax_image: str
    boxes_dir: Path
    class_record: dict
    class_record_sha256: str
    class_ops_record: dict
    class_ops_record_sha256: str


def public_key_line(text: str) -> str:
    """The one public key line of ``text``, or Refused: a private key (or anything else) never goes to the box."""
    if "PRIVATE KEY" in text:
        raise Refused("lane_pubkey_is_private", "--lane-pubkey must be the .pub file")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise Refused("lane_pubkey_invalid", "expected exactly one public key line")
    parts = lines[0].split()
    if len(parts) < 2 or parts[0] not in _PUBLIC_KEY_TYPES:
        raise Refused("lane_pubkey_invalid", "not an OpenSSH public key")
    try:
        blob = base64.b64decode(parts[1], validate=True)
        size = int.from_bytes(blob[:4], "big")
        embedded = blob[4 : 4 + size].decode("ascii")
    except (ValueError, UnicodeDecodeError):
        raise Refused("lane_pubkey_invalid", "the key body is not base64") from None
    if embedded != parts[0]:
        raise Refused("lane_pubkey_invalid", "the key body names another key type")
    return lines[0]


def authorized_keys_line(door_ip: str, pubkey: str) -> str:
    """The lane user's only authorized_keys line: the door's address, no forwarding of any kind."""
    return (
        f'from="{door_ip}",no-agent-forwarding,no-port-forwarding,no-X11-forwarding '
        f"{pubkey}"
    )


def _version(text: str) -> tuple[int, ...]:
    if not _VERSION.fullmatch(text):
        raise Refused("driver_version_unreadable", text)
    return tuple(int(part) for part in text.split("."))


def _load_json_file(path: str, reason: str) -> tuple[dict, str]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError):
        raise Refused(reason, f"cannot read {path}") from None
    if type(value) is not dict:
        raise Refused(reason, f"{path} is not a JSON object")
    return value, _sha256(raw)


def config_from_args(args) -> Config:
    user, sep, ip = args.ssh.partition("@")
    if not sep or not _ADMIN.fullmatch(user):
        raise Refused("bad_argument", "--ssh must be USER@IPV4")
    try:
        if ipaddress.ip_address(ip).version != 4:
            raise ValueError
        door = str(ipaddress.ip_address(args.door_ip))
    except ValueError:
        raise Refused(
            "bad_argument", "--ssh needs an IPv4 address; --door-ip an IP"
        ) from None
    if not 1 <= args.port <= 65535:
        raise Refused("bad_argument", "--port")
    if not _NAME.fullmatch(args.box_name) or not _NAME.fullmatch(args.provider):
        raise Refused(
            "bad_argument", "--box-name/--provider: letters, digits, '-', '_'"
        )
    if not _DEVICE_KIND.fullmatch(args.device_kind):
        raise Refused("bad_argument", "--device-kind")
    _version(args.driver_floor)
    if not _VERSION.fullmatch(args.docker_version):
        raise Refused("bad_argument", "--docker-version")
    if not _PACKAGE.fullmatch(args.driver_package):
        raise Refused("bad_argument", "--driver-package")
    if not _FINGERPRINT.fullmatch(args.host_key_fingerprint):
        raise Refused("bad_argument", "--host-key-fingerprint must be SHA256:<43>")
    images = list(dict.fromkeys([args.jax_image, *args.image]))
    for image in images:
        if not _IMAGE_ID.fullmatch(image):
            raise Refused("bad_argument", f"image ids are full sha256 ids: {image}")
    try:
        pubkey = public_key_line(Path(args.lane_pubkey).read_text(encoding="utf-8"))
    except OSError:
        raise Refused(
            "lane_pubkey_invalid", f"cannot read {args.lane_pubkey}"
        ) from None
    record, record_sha = _load_json_file(args.class_record, "class_record_invalid")
    ops, ops_sha = _load_json_file(args.class_ops_record, "class_ops_record_invalid")
    if record.get("schema") != CLASS_CHECK_SCHEMA:
        raise Refused("class_record_invalid", "not a class-check record")
    if ops.get("schema") != OPS_SCHEMA:
        raise Refused("class_ops_record_invalid", "not a graph GPU ops record")
    return Config(
        admin=user,
        ip=ip,
        port=args.port,
        ssh_key=args.ssh_key,
        name=args.box_name,
        provider=args.provider,
        device_kind=args.device_kind,
        driver_floor=args.driver_floor,
        driver_package=args.driver_package,
        docker_version=args.docker_version,
        door_ip=door,
        lane_pubkey=pubkey,
        host_key_fingerprint=args.host_key_fingerprint,
        images=tuple(images),
        jax_image=args.jax_image,
        boxes_dir=Path(args.boxes_dir).expanduser(),
        class_record=record,
        class_record_sha256=record_sha,
        class_ops_record=ops,
        class_ops_record_sha256=ops_sha,
    )


# -- the commands (one definition each, shared by the run and the dry run) -------------------------------------------


def sudo_sh(script: str) -> str:
    return "sudo -n sh -c " + shlex.quote(script)


def write_file_script(path: str, text: str, *, mode: str, owner: str) -> str:
    """Shell that writes ``text`` to ``path`` atomically (temp file + rename) with its owner and mode. ``path`` is a
    shell word this module builds itself (a plain path, or ``"$h/..."``); only ``text`` is quoted here.
    """
    part = f"{path}.part"
    return (
        f"umask 077; printf '%s' {shlex.quote(text)} > {part}; "
        f"chown {owner} {part}; chmod {mode} {part}; mv -f {part} {path}"
    )


def cmd_keyscan(cfg: Config) -> list[str]:
    return ["ssh-keyscan", "-t", "ed25519", "-p", str(cfg.port), cfg.ip]


def ssh(cfg: Config, known_hosts: str, command: str) -> list[str]:
    """The one way a command reaches the box: the pinned host key, no agent, no forwarding."""
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "ForwardAgent=no",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        "-p",
        str(cfg.port),
    ]
    if cfg.ssh_key:
        argv += ["-i", cfg.ssh_key, "-o", "IdentitiesOnly=yes"]
    return argv + [f"{cfg.admin}@{cfg.ip}", "--", command]


CMD_SHAPE = "nproc; grep '^MemTotal:' /proc/meminfo"
CMD_DRIVER_QUERY = (
    "nvidia-smi --query-gpu=name,uuid,memory.total,driver_version "
    "--format=csv,noheader"
)


def cmd_driver_install(package: str) -> str:
    return sudo_sh(
        "set -eu; export DEBIAN_FRONTEND=noninteractive; apt-get update; "
        f"apt-get install -y {package}"
    )


CMD_DOCKER_VERSION = (
    "sudo -n docker version --format '{{.Server.Version}}' 2>/dev/null || true"
)


def cmd_docker_install(version: str) -> str:
    pattern = "^5:" + version.replace(".", r"\.") + "-"
    return sudo_sh(
        "set -eu; export DEBIAN_FRONTEND=noninteractive; "
        "for p in docker.io docker-doc docker-compose docker-compose-v2 podman-docker; do "
        "apt-get remove -y $p >/dev/null 2>&1 || true; done; "
        "apt-get update; apt-get install -y ca-certificates curl gnupg; "
        "install -m 0755 -d /etc/apt/keyrings; "
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc; "
        "chmod a+r /etc/apt/keyrings/docker.asc; . /etc/os-release; "
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] '
        'https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" '
        "> /etc/apt/sources.list.d/docker.list; apt-get update; "
        f"v=$(apt-cache madison docker-ce | awk '{{print $3}}' | grep -E '{pattern}' | head -n1); "
        'test -n "$v"; apt-mark unhold docker-ce docker-ce-cli >/dev/null 2>&1 || true; '
        'apt-get install -y --allow-downgrades "docker-ce=$v" "docker-ce-cli=$v" containerd.io; '
        "apt-mark hold docker-ce docker-ce-cli; systemctl enable --now docker"
    )


CMD_CTK_PRESENT = "command -v nvidia-ctk || true"
CMD_TOOLKIT_INSTALL = sudo_sh(
    "set -eu; export DEBIAN_FRONTEND=noninteractive; apt-get update; "
    "apt-get install -y ca-certificates curl gnupg; "
    "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --batch --yes --dearmor "
    "-o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg; "
    "curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list "
    "| sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' "
    "> /etc/apt/sources.list.d/nvidia-container-toolkit.list; "
    "apt-get update; apt-get install -y nvidia-container-toolkit"
)
DAEMON_JSON = "/etc/docker/daemon.json"
CMD_DAEMON_READ = sudo_sh(f"cat {DAEMON_JSON} 2>/dev/null || true")
CMD_CTK_CONFIGURE = "sudo -n nvidia-ctk runtime configure --runtime=docker"
CMD_DOCKER_RESTART = "sudo -n systemctl restart docker"
CMD_DOCKER_INFO = "sudo -n docker info --format '{{json .}}'"


def cmd_daemon_write(text: str) -> str:
    return sudo_sh(
        "set -eu; "
        + write_file_script(DAEMON_JSON, text, mode="0644", owner="root:root")
    )


CMD_LANE_UID = f"id -u {LANE_USER} 2>/dev/null || true"
CMD_LANE_CREATE = f"sudo -n useradd --create-home --shell /bin/bash {LANE_USER}"
CMD_LANE_GROUP = f"sudo -n usermod -aG docker {LANE_USER}"
CMD_LANE_ID = f"id -u {LANE_USER}; id -nG {LANE_USER}"
_LANE_HOME = f'"$(getent passwd {LANE_USER} | cut -d: -f6)"'


def cmd_authorized_keys_write(line: str) -> str:
    return sudo_sh(
        f'set -eu; h={_LANE_HOME}; test -n "$h"; '
        f'install -d -o {LANE_USER} -g {LANE_USER} -m 0700 "$h/.ssh"; '
        + write_file_script(
            '"$h/.ssh/authorized_keys"',
            line + "\n",
            mode="0600",
            owner=f"{LANE_USER}:{LANE_USER}",
        )
    )


CMD_AUTHORIZED_KEYS_READ = sudo_sh(f"cat {_LANE_HOME}/.ssh/authorized_keys")
CMD_STAGE_ROOT = (
    f"sudo -n install -d -o {LANE_USER} -g {LANE_USER} -m 0755 {STAGE_ROOT}"
)
CMD_STAGE_ROOT_STAT = f"stat -c '%U:%G %a %F' {STAGE_ROOT}"


def cmd_image_id(image: str) -> str:
    return f"sudo -n docker image inspect --format '{{{{.Id}}}}' {image} 2>/dev/null || true"


CMD_DOCKER_LOAD = "sudo -n docker load"


def cmd_docker_save(image: str) -> list[str]:
    return ["docker", "save", image]


def cmd_git_head() -> list[str]:
    return ["git", "-C", str(ROOT), "rev-parse", "HEAD"]


def cmd_git_archive(commit: str) -> list[str]:
    return ["git", "-C", str(ROOT), "archive", "--format=tar", commit]


def cmd_work_dir(cfg: Config) -> str:
    return f"sudo -n install -d -o {cfg.admin} -m 0755 {WORK}"


def tree_dir(commit: str) -> str:
    return f"{WORK}/tree-{commit}"


def cmd_tree_present(commit: str) -> str:
    return f"test -d {tree_dir(commit)} && echo present || true"


def cmd_tree_extract(commit: str) -> str:
    tree = tree_dir(commit)
    return (
        f"set -eu; rm -rf {tree}.part; mkdir -m 0755 {tree}.part; tar -x -C {tree}.part; "
        f"chmod -R a+rX,go-w {tree}.part; mv {tree}.part {tree}"
    )


def cmd_prepare(cfg: Config, commit: str) -> str:
    return shlex.join(
        [
            "python3",
            "-I",
            f"{tree_dir(commit)}/scripts/dev/carbon_accelerator.py",
            "--host-root",
            HOST_ROOT,
            "prepare",
            "--record-id",
            cfg.name,
            "--provider",
            cfg.provider,
            "--container-runtime",
            "DOCKER_ENGINE",
            "--platform",
            "LINUX_VIRTUAL_MACHINE",
        ]
    )


CMD_DEVICE_READ = f"cat {HOST_ROOT}/host-device.json"
CMD_CLASS_OUT = sudo_sh(
    f"set -eu; rm -rf {CLASS_OUT}; install -d -o 65532 -g 65532 -m 0700 {CLASS_OUT}"
)
CMD_CLASS_OUTPUT_READ = f"sudo -n cat {CLASS_OUT}/class-check.json"
CMD_CLASS_OPS_READ = f"sudo -n cat {CLASS_OUT}/ops-record.json"


def cmd_class_check(cfg: Config, commit: str, uuid: str) -> str:
    """The receipted class-check runner's container, on this box's one GPU. ``--entrypoint`` replaces the worker
    image's admission entrypoint by its own Python; ``TMPDIR`` points into the tmpfs (the root is read-only).
    """
    return shlex.join(
        [
            "sudo",
            "-n",
            "docker",
            "run",
            "--rm",
            "--user",
            WORKER_USER,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/scratch:rw,size=4g",
            "--runtime",
            "nvidia",
            "--gpus",
            f"device={uuid}",
            "-v",
            f"{tree_dir(commit)}:/carbon:ro",
            "-v",
            f"{CLASS_OUT}:/out",
            "-e",
            "PYTHONPATH=/carbon",
            "-e",
            "TMPDIR=/scratch",
            "--entrypoint",
            WORKER_PYTHON,
            cfg.jax_image,
            "-I",
            "-X",
            "faulthandler",
            "/carbon/scripts/dev/gpu_rebuild_class_check.py",
            "--out",
            "/out/class-check.json",
            "--ops-record",
            "/out/ops-record.json",
            "--steps",
            str(CLASS_CHECK_STEPS),
            "--no-torch",
        ]
    )


# -- pure checks --------------------------------------------------------------------------------------------------------


def merge_daemon_json(text: str) -> dict:
    """daemon.json with the containerd image store switched on, keeping every other key (the nvidia runtime that
    ``nvidia-ctk runtime configure`` merged in among them)."""
    try:
        value = json.loads(text) if text.strip() else {}
    except ValueError:
        raise Refused("daemon_json_invalid", "daemon.json is not JSON") from None
    if type(value) is not dict:
        raise Refused("daemon_json_invalid", "daemon.json is not an object")
    features = value.get("features") or {}
    if type(features) is not dict:
        raise Refused("daemon_json_invalid", "features is not an object")
    merged = {**value, "features": {**features, "containerd-snapshotter": True}}
    if "nvidia" not in (merged.get("runtimes") or {}):
        raise Refused(
            "docker_nvidia_runtime_missing", "nvidia-ctk added no nvidia runtime"
        )
    return merged


def daemon_json_text(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def host_key_fingerprint(key_b64: str) -> str:
    blob = base64.b64decode(key_b64, validate=True)
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode(
        "ascii"
    ).rstrip("=")


def case_id(case: dict) -> str:
    return f'{case.get("kind")}:{case.get("key")}/{case.get("arch")}'


def _case_digests(record: dict, reason: str) -> dict:
    cases = record.get("cases")
    if type(cases) is not list or not cases:
        raise Refused(reason, "no cases")
    digests = {}
    for case in cases:
        if type(case) is not dict or case_id(case) in digests:
            raise Refused(reason, "malformed or repeated case")
        digests[case_id(case)] = case.get("state_digest")
    return digests


def evaluate_class_check(
    raw_output: str,
    raw_ops: str,
    *,
    class_record: dict,
    class_ops_record: dict,
    device_kind: str,
    allowlist_v8: str,
) -> dict:
    """PASS (the per-case digests) or Refused. PASS = every case bit-identical and on the GPU, on this device class;
    the ops record measured against allowlist v8 and bound to this very output; every case's state digest equal to
    the class record's; the ops record equal to the class's ops record (all but its ``class_record_digest``, which
    names the run that wrote it)."""
    try:
        record = json.loads(raw_output)
    except ValueError:
        raise Refused("class_check_output_invalid", "class-check.json") from None
    if type(record) is not dict or record.get("schema") != CLASS_CHECK_SCHEMA:
        raise Refused("class_check_output_invalid", "not a class-check record")
    digests = _case_digests(record, "class_check_output_invalid")
    cases = record["cases"]
    repeated_not = [case_id(c) for c in cases if c.get("bit_identical") is not True]
    if repeated_not:
        raise Refused("class_check_not_bit_identical", ", ".join(repeated_not))
    off_gpu = [case_id(c) for c in cases if c.get("ran_on_gpu") is not True]
    if off_gpu or record.get("all_on_gpu") is not True:
        raise Refused("class_check_not_on_gpu", ", ".join(off_gpu))
    if record.get("verdict") != "GPU_REPEATS":
        raise Refused("class_check_verdict", str(record.get("verdict")))
    rows = (record.get("nvidia_smi") or {}).get("gpus") or []
    if not rows or any(not str(r).startswith(device_kind + ",") for r in rows):
        raise Refused("class_check_wrong_device", "; ".join(map(str, rows)))
    try:
        ops = json.loads(raw_ops)
    except ValueError:
        raise Refused("class_check_output_invalid", "ops-record.json") from None
    if type(ops) is not dict or ops.get("schema") != OPS_SCHEMA:
        raise Refused("class_check_output_invalid", "not a graph GPU ops record")
    if ops.get("allowlist_digest") != allowlist_v8:
        raise Refused("class_check_not_allowlist_v8", str(ops.get("allowlist_digest")))
    # gpu_rebuild_class_check.ops_record binds the record it was derived from by this digest.
    if ops.get("class_record_digest") != _sha256(
        json.dumps(record, sort_keys=True).encode()
    ):
        raise Refused("class_check_ops_record_unbound", "ops record names another run")
    reference = _case_digests(class_record, "class_record_invalid")
    if digests != reference:
        differ = sorted(
            k
            for k in set(digests) | set(reference)
            if digests.get(k) != reference.get(k)
        )
        raise Refused("class_check_digest_mismatch", ", ".join(differ))

    def comparable(value):
        return _canonical(
            {k: v for k, v in value.items() if k != "class_record_digest"}
        )

    if comparable(ops) != comparable(class_ops_record):
        raise Refused("class_check_ops_mismatch", "ops record differs from the class's")
    return {"case_digests": digests}


def _allowlist_v8_digest() -> str:
    from carbon.level4.allowlist import Allowlist, v8_bytes

    return Allowlist(v8_bytes()).digest


def _device_record(document: dict) -> str:
    """The host device record's digest, once the door's own reader accepts it for the GPU profile."""
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
    )
    from carbon.reconstruction.worker.model import WorkerFailure

    digest = _sha256(_canonical(document))
    try:
        require_host_device(HostDeviceRecord(document, digest), GPU_PROFILE)
    except WorkerFailure:
        raise Refused(
            "device_record_invalid", "the host device record fails its shape"
        ) from None
    return digest


# -- box files ---------------------------------------------------------------------------------------------------------


def ready_boxes_dir(path: Path) -> Path:
    """The boxes directory: a real directory, owned by this user, mode 0700 (created so when missing)."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Refused("boxes_dir_unsafe", f"{path} must be a 0700 directory you own")
    return path


def box_path(cfg: Config) -> Path:
    return cfg.boxes_dir / f"{cfg.name}.json"


def remove_box_file(cfg: Config) -> None:
    path = box_path(cfg)
    if os.path.lexists(path):
        os.unlink(path)


def write_box_file(cfg: Config, document: dict) -> Path:
    """Atomic: a 0600 temp file in the same directory, fsynced, renamed over the name."""
    path = box_path(cfg)
    fd, part = tempfile.mkstemp(
        prefix=f".{cfg.name}.", suffix=".part", dir=cfg.boxes_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, indent=1, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(part, 0o600)
        os.replace(part, path)
    except BaseException:
        if os.path.lexists(part):
            os.unlink(part)
        raise
    directory = os.open(cfg.boxes_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return path


# -- the run -----------------------------------------------------------------------------------------------------------


def subprocess_runner(argv, pipe_from=None):
    """The real runner: ``argv`` -> ``(rc, stdout, stderr)``; ``pipe_from`` is a local command whose stdout feeds it."""
    if pipe_from is None:
        done = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return done.returncode, done.stdout, done.stderr
    with tempfile.TemporaryFile() as source_err:
        source = subprocess.Popen(pipe_from, stdout=subprocess.PIPE, stderr=source_err)
        try:
            done = subprocess.run(
                argv,
                stdin=source.stdout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        finally:
            source.stdout.close()
            source.wait()
        source_err.seek(0)
        if source.returncode != 0:
            text = source_err.read().decode("utf-8", "replace")
            return source.returncode, done.stdout, text + done.stderr
    return done.returncode, done.stdout, done.stderr


class Session:
    """One bring-up: every external command passes through `call` (and so through the injected runner)."""

    def __init__(self, cfg: Config, runner, *, log=None):
        self.cfg = cfg
        self.runner = runner
        self.log = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self.step = "start"
        self.known_hosts: str | None = None

    def _guard(self, argv, pipe_from):
        """What leaves the door: no private key text in any command, and only public images or the public tree
        streamed. A violation is a bug in this tool, refused before anything is sent."""
        if any("PRIVATE KEY" in str(arg) for arg in argv):
            raise Refused("secret_refused", "a command carried private key text")
        if pipe_from is None:
            return
        pipe_from = list(pipe_from)
        allowed = [cmd_docker_save(image) for image in self.cfg.images]
        if pipe_from not in allowed and not (
            pipe_from[:-1] == cmd_git_archive("x")[:-1]
            and _COMMIT.fullmatch(pipe_from[-1])
        ):
            raise Refused("upload_refused", shlex.join(pipe_from))

    def call(self, argv, pipe_from=None):
        self._guard(argv, pipe_from)
        if pipe_from is None:
            return self.runner(list(argv))
        return self.runner(list(argv), pipe_from=list(pipe_from))

    def remote(self, command: str, *, reason: str, pipe_from=None) -> str:
        rc, out, err = self.call(ssh(self.cfg, self.known_hosts, command), pipe_from)
        if rc != 0:
            tail = (err or out or "").strip()[-400:]
            raise Refused(reason, f"rc={rc}: {tail}")
        return out

    # The steps, in order. Each reads the box first and changes only what differs.

    def host_key(self):
        rc, out, _ = self.call(cmd_keyscan(self.cfg))
        keys = {
            parts[2]
            for parts in (line.split() for line in out.splitlines())
            if len(parts) >= 3
            and not parts[0].startswith("#")
            and parts[1] == "ssh-ed25519"
        }
        if rc != 0 or len(keys) != 1:
            raise Refused("host_key_unavailable", f"rc={rc}, {len(keys)} ed25519 keys")
        key = keys.pop()
        try:
            seen = host_key_fingerprint(key)
        except ValueError:
            raise Refused("host_key_unavailable", "unreadable key") from None
        if seen != self.cfg.host_key_fingerprint:
            raise Refused("host_key_mismatch", f"the box presents {seen}")
        host = (
            self.cfg.ip if self.cfg.port == 22 else f"[{self.cfg.ip}]:{self.cfg.port}"
        )
        line = f"{host} ssh-ed25519 {key}"
        Path(self.known_hosts).write_text(line + "\n", encoding="utf-8")
        return line

    def shape(self):
        out = self.remote(CMD_SHAPE, reason="shape_unreadable")
        lines = out.split("\n")
        try:
            cpus = int(lines[0].strip())
            mem_kib = int(lines[1].split()[1])
        except (IndexError, ValueError):
            raise Refused("shape_unreadable", out.strip()[-200:]) from None
        if cpus < MIN_CPUS:
            raise Refused("slot_shape_cpus", f"{cpus} logical CPUs < {MIN_CPUS}")
        if mem_kib < MIN_MEM_KIB:
            raise Refused(
                "slot_shape_memory", f"MemTotal {mem_kib} kB < {MIN_MEM_KIB} kB"
            )

    def driver(self):
        cfg = self.cfg
        rc, out, _ = self.call(ssh(cfg, self.known_hosts, CMD_DRIVER_QUERY))
        if rc != 0:
            # No driver, or one that no longer talks to its library (an upgrade waiting for a reboot).
            self.remote(
                cmd_driver_install(cfg.driver_package), reason="driver_install_failed"
            )
            raise Refused(
                "driver_upgrade_needs_reboot",
                f"nvidia-smi failed; {cfg.driver_package} installed: reboot the box, then run this again",
            )
        rows = [
            [f.strip() for f in r.split(",")] for r in out.splitlines() if r.strip()
        ]
        if len(rows) != 1 or len(rows[0]) != 4:
            raise Refused(
                "gpu_count", f"{len(rows)} GPUs reported; exactly one is required"
            )
        name, uuid, _memory, driver = rows[0]
        if name != cfg.device_kind:
            raise Refused("wrong_device_kind", f"{name!r} is not {cfg.device_kind!r}")
        if _version(driver) < _version(cfg.driver_floor):
            self.remote(
                cmd_driver_install(cfg.driver_package), reason="driver_install_failed"
            )
            raise Refused(
                "driver_upgrade_needs_reboot",
                f"driver {driver} < {cfg.driver_floor}; {cfg.driver_package} installed: "
                "reboot the box, then run this again",
            )
        return uuid, driver

    def docker(self):
        cfg = self.cfg
        if (
            self.remote(CMD_DOCKER_VERSION, reason="docker_unreadable").strip()
            != cfg.docker_version
        ):
            self.remote(
                cmd_docker_install(cfg.docker_version), reason="docker_install_failed"
            )
        if not self.remote(CMD_CTK_PRESENT, reason="docker_unreadable").strip():
            self.remote(CMD_TOOLKIT_INSTALL, reason="toolkit_install_failed")
        before = self.remote(CMD_DAEMON_READ, reason="docker_unreadable")
        self.remote(CMD_CTK_CONFIGURE, reason="docker_configure_failed")
        after_ctk = self.remote(CMD_DAEMON_READ, reason="docker_unreadable")
        merged = merge_daemon_json(after_ctk)
        text = daemon_json_text(merged)
        if text != after_ctk:
            self.remote(cmd_daemon_write(text), reason="docker_configure_failed")
        try:
            previous = json.loads(before) if before.strip() else None
        except ValueError:
            previous = None
        if previous != merged:
            self.remote(CMD_DOCKER_RESTART, reason="docker_restart_failed")
        try:
            info = json.loads(self.remote(CMD_DOCKER_INFO, reason="docker_unreadable"))
        except ValueError:
            raise Refused("docker_unreadable", "docker info is not JSON") from None
        if info.get("ServerVersion") != cfg.docker_version:
            raise Refused("docker_version_mismatch", str(info.get("ServerVersion")))
        if "io.containerd.snapshotter.v1" not in json.dumps(info.get("DriverStatus")):
            raise Refused(
                "docker_snapshotter_missing", json.dumps(info.get("DriverStatus"))
            )
        if "nvidia" not in (info.get("Runtimes") or {}):
            raise Refused(
                "docker_nvidia_runtime_missing", "docker info lists no nvidia runtime"
            )

    def lane_user(self):
        if not self.remote(CMD_LANE_UID, reason="lane_user_failed").strip():
            self.remote(CMD_LANE_CREATE, reason="lane_user_failed")
        self.remote(CMD_LANE_GROUP, reason="lane_user_failed")
        lines = self.remote(CMD_LANE_ID, reason="lane_user_failed").splitlines()
        if not lines or lines[0].strip() == "0":
            raise Refused("lane_user_is_root", f"{LANE_USER} has uid 0")
        if len(lines) < 2 or "docker" not in lines[1].split():
            raise Refused("lane_user_not_in_docker", lines[1] if len(lines) > 1 else "")
        line = authorized_keys_line(self.cfg.door_ip, self.cfg.lane_pubkey)
        self.remote(cmd_authorized_keys_write(line), reason="lane_user_failed")
        if (
            self.remote(CMD_AUTHORIZED_KEYS_READ, reason="lane_user_failed")
            != line + "\n"
        ):
            raise Refused(
                "authorized_keys_mismatch", "authorized_keys is not the one line"
            )

    def stage_root(self):
        self.remote(CMD_STAGE_ROOT, reason="stage_root_failed")
        seen = self.remote(CMD_STAGE_ROOT_STAT, reason="stage_root_failed").strip()
        if seen != f"{LANE_USER}:{LANE_USER} 755 directory":
            raise Refused("stage_root_mismatch", seen)

    def images(self):
        for image in self.cfg.images:
            if (
                self.remote(cmd_image_id(image), reason="image_unreadable").strip()
                == image
            ):
                continue
            self.remote(
                CMD_DOCKER_LOAD,
                reason="image_load_failed",
                pipe_from=cmd_docker_save(image),
            )
            seen = self.remote(cmd_image_id(image), reason="image_unreadable").strip()
            if seen != image:
                raise Refused(
                    "image_id_mismatch", f"{image} loaded as {seen or 'nothing'}"
                )

    def tree(self):
        rc, out, err = self.call(cmd_git_head())
        commit = out.strip()
        if rc != 0 or not _COMMIT.fullmatch(commit):
            raise Refused("tree_unreadable", (err or out).strip()[-200:])
        self.remote(cmd_work_dir(self.cfg), reason="tree_ship_failed")
        if (
            self.remote(cmd_tree_present(commit), reason="tree_ship_failed").strip()
            != "present"
        ):
            self.remote(
                cmd_tree_extract(commit),
                reason="tree_ship_failed",
                pipe_from=cmd_git_archive(commit),
            )
        return commit

    def device(self, commit, uuid, driver):
        self.remote(cmd_prepare(self.cfg, commit), reason="device_record_failed")
        try:
            document = json.loads(
                self.remote(CMD_DEVICE_READ, reason="device_record_failed")
            )
        except ValueError:
            raise Refused(
                "device_record_invalid", "host-device.json is not JSON"
            ) from None
        if type(document) is not dict:
            raise Refused("device_record_invalid", "host-device.json is not an object")
        for field, want in (
            ("device_kind", self.cfg.device_kind),
            ("device_uuid", uuid),
            ("driver_version", driver),
        ):
            if document.get(field) != want:
                raise Refused(
                    "device_record_mismatch", f"{field}: {document.get(field)!r}"
                )
        return document, _device_record(document)

    def class_check(self, commit, uuid):
        self.remote(CMD_CLASS_OUT, reason="class_check_failed")
        rc, out, err = self.call(
            ssh(self.cfg, self.known_hosts, cmd_class_check(self.cfg, commit, uuid))
        )
        r_out, raw_output, _ = self.call(
            ssh(self.cfg, self.known_hosts, CMD_CLASS_OUTPUT_READ)
        )
        r_ops, raw_ops, _ = self.call(
            ssh(self.cfg, self.known_hosts, CMD_CLASS_OPS_READ)
        )
        if r_out != 0 or not raw_output.strip():
            raise Refused(
                "class_check_failed", f"rc={rc}: {(err or out).strip()[-400:]}"
            )
        summary = evaluate_class_check(
            raw_output,
            raw_ops if r_ops == 0 else "",
            class_record=self.cfg.class_record,
            class_ops_record=self.cfg.class_ops_record,
            device_kind=self.cfg.device_kind,
            allowlist_v8=_allowlist_v8_digest(),
        )
        if rc != 0:
            raise Refused("class_check_failed", f"rc={rc} although the record passed")
        return (
            summary,
            _sha256(raw_output.encode("utf-8")),
            _sha256(raw_ops.encode("utf-8")),
        )

    def run_step(self, name, function, *args):
        self.step = name
        started = time.monotonic()
        value = function(*args)
        self.log(
            json.dumps(
                {
                    "step": name,
                    "status": "ok",
                    "seconds": round(time.monotonic() - started, 1),
                }
            )
        )
        return value


def box_document(
    cfg, *, host_key, driver, device, device_digest, summary, output_sha, ops_sha, now
):
    docker_host = f"ssh://{LANE_USER}@{cfg.ip}" + (
        "" if cfg.port == 22 else f":{cfg.port}"
    )
    parse_docker_host(docker_host)
    return {
        "schema": BOX_SCHEMA,
        "name": cfg.name,
        "docker_host": docker_host,
        "stage_root": STAGE_ROOT,
        "slot_cpusets": list(SLOT_CPUSETS),
        "device": device,
        "device_digest": device_digest,
        "driver_version": driver,
        "host_key": host_key,
        "images": list(cfg.images),
        "class_check": {
            "case_digests": summary["case_digests"],
            "class_record_sha256": cfg.class_record_sha256,
            "class_ops_record_sha256": cfg.class_ops_record_sha256,
        },
        "check_output_sha256": output_sha,
        "check_ops_record_sha256": ops_sha,
        "admitted_unix": int(now),
    }


def bring_up(cfg: Config, runner, *, now=time.time, log=None) -> dict:
    """Run every step; write the box file only on PASS. Returns the outcome document."""
    started = time.monotonic()

    def refused(step, refusal):
        return {
            "status": "REFUSED",
            "step": step,
            "reason": refusal.reason,
            "detail": refusal.detail,
            "seconds": round(time.monotonic() - started, 1),
        }

    try:
        ready_boxes_dir(cfg.boxes_dir)
    except Refused as refusal:
        return refused("boxes_dir", refusal)
    # A box being (re)brought up is not offered until it passes again.
    remove_box_file(cfg)
    session = Session(cfg, runner, log=log)
    scratch = tempfile.mkdtemp(prefix="gpu-box-up-")
    session.known_hosts = os.path.join(scratch, "known_hosts")
    try:
        host_key = session.run_step("host_key", session.host_key)
        session.run_step("shape", session.shape)
        uuid, driver = session.run_step("driver", session.driver)
        session.run_step("docker", session.docker)
        session.run_step("lane_user", session.lane_user)
        session.run_step("stage_root", session.stage_root)
        session.run_step("images", session.images)
        commit = session.run_step("tree", session.tree)
        device, device_digest = session.run_step(
            "device", session.device, commit, uuid, driver
        )
        summary, output_sha, ops_sha = session.run_step(
            "class_check", session.class_check, commit, uuid
        )
        document = box_document(
            cfg,
            host_key=host_key,
            driver=driver,
            device=device,
            device_digest=device_digest,
            summary=summary,
            output_sha=output_sha,
            ops_sha=ops_sha,
            now=now(),
        )
        session.step = "box_file"
        path = write_box_file(cfg, document)
    except Refused as refusal:
        remove_box_file(cfg)
        return refused(session.step, refusal)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {
        "status": "ADMITTED",
        "box_file": str(path),
        "seconds": round(time.monotonic() - started, 1),
    }


def plan(cfg: Config) -> list[tuple[str, str]]:
    """Every command a run may send, in order, with what is only known on the box as a placeholder."""
    kh, uuid, commit = "<known_hosts>", "<gpu-uuid>", "<HEAD>"

    def remote(step, command, pipe_from=None):
        text = shlex.join(ssh(cfg, kh, command))
        return (step, f"{shlex.join(pipe_from)} | {text}" if pipe_from else text)

    steps = [("host_key", shlex.join(cmd_keyscan(cfg)))]
    steps.append(remote("shape", CMD_SHAPE))
    steps.append(remote("driver", CMD_DRIVER_QUERY))
    steps.append(
        remote(
            "driver (only when older or missing; then stop for a reboot)",
            cmd_driver_install(cfg.driver_package),
        )
    )
    steps.append(remote("docker", CMD_DOCKER_VERSION))
    steps.append(
        remote(
            "docker (only when another version)", cmd_docker_install(cfg.docker_version)
        )
    )
    steps.append(remote("docker", CMD_CTK_PRESENT))
    steps.append(
        remote("docker (only when nvidia-ctk is missing)", CMD_TOOLKIT_INSTALL)
    )
    steps.append(remote("docker", CMD_DAEMON_READ))
    steps.append(remote("docker", CMD_CTK_CONFIGURE))
    steps.append(remote("docker", CMD_DAEMON_READ))
    steps.append(
        remote(
            "docker (only when it differs)", cmd_daemon_write("<merged daemon.json>")
        )
    )
    steps.append(remote("docker (only when it changed)", CMD_DOCKER_RESTART))
    steps.append(remote("docker", CMD_DOCKER_INFO))
    steps.append(remote("lane_user", CMD_LANE_UID))
    steps.append(remote("lane_user (only when missing)", CMD_LANE_CREATE))
    for command in (
        CMD_LANE_GROUP,
        CMD_LANE_ID,
        cmd_authorized_keys_write(authorized_keys_line(cfg.door_ip, cfg.lane_pubkey)),
        CMD_AUTHORIZED_KEYS_READ,
    ):
        steps.append(remote("lane_user", command))
    steps.append(remote("stage_root", CMD_STAGE_ROOT))
    steps.append(remote("stage_root", CMD_STAGE_ROOT_STAT))
    for image in cfg.images:
        steps.append(remote("images", cmd_image_id(image)))
        steps.append(
            remote("images (only when absent)", CMD_DOCKER_LOAD, cmd_docker_save(image))
        )
        steps.append(remote("images", cmd_image_id(image)))
    steps.append(("tree", shlex.join(cmd_git_head())))
    steps.append(remote("tree", cmd_work_dir(cfg)))
    steps.append(remote("tree", cmd_tree_present(commit)))
    steps.append(
        remote(
            "tree (only when absent)", cmd_tree_extract(commit), cmd_git_archive(commit)
        )
    )
    steps.append(remote("device", cmd_prepare(cfg, commit)))
    steps.append(remote("device", CMD_DEVICE_READ))
    steps.append(remote("class_check", CMD_CLASS_OUT))
    steps.append(remote("class_check", cmd_class_check(cfg, commit, uuid)))
    steps.append(remote("class_check", CMD_CLASS_OUTPUT_READ))
    steps.append(remote("class_check", CMD_CLASS_OPS_READ))
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ssh",
        required=True,
        help="the box's admin login, USER@IPV4 (e.g. ubuntu@203.0.113.7)",
    )
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument(
        "--ssh-key",
        help="the operator's private key for the admin login (stays on the door)",
    )
    parser.add_argument("--box-name", required=True)
    parser.add_argument("--provider", required=True, help="a plain token, e.g. lambda")
    parser.add_argument(
        "--device-kind", required=True, help='e.g. "NVIDIA A100-SXM4-40GB"'
    )
    parser.add_argument("--driver-floor", default=DEFAULT_DRIVER_FLOOR)
    parser.add_argument("--driver-package", default=DEFAULT_DRIVER_PACKAGE)
    parser.add_argument("--docker-version", default=DEFAULT_DOCKER_VERSION)
    parser.add_argument(
        "--door-ip", required=True, help="the only address the lane key may log in from"
    )
    parser.add_argument(
        "--lane-pubkey", required=True, help="the lane user's PUBLIC key file (.pub)"
    )
    parser.add_argument(
        "--host-key-fingerprint",
        required=True,
        help="the box's ed25519 host key, SHA256:...",
    )
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        help="a worker image id to load (repeat)",
    )
    parser.add_argument(
        "--jax-image",
        required=True,
        help="the pinned JAX GPU image id the class check runs in",
    )
    parser.add_argument(
        "--class-record", required=True, help="the class's reference class-check JSON"
    )
    parser.add_argument(
        "--class-ops-record",
        required=True,
        help="the class's reference graph GPU ops record",
    )
    parser.add_argument(
        "--boxes-dir", required=True, help="where the door's box files live (0700)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print every command; run none"
    )
    return parser


def main(argv=None, runner=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(args)
    except Refused as refusal:
        print(
            json.dumps(
                {
                    "status": "REFUSED",
                    "step": "arguments",
                    "reason": refusal.reason,
                    "detail": refusal.detail,
                }
            )
        )
        return 2
    if args.dry_run:
        for step, command in plan(cfg):
            print(f"[{step}] {command}")
        return 0
    outcome = bring_up(cfg, runner or subprocess_runner)
    print(json.dumps(outcome, indent=1, sort_keys=True))
    return 0 if outcome["status"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
