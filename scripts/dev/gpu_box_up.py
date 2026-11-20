#!/usr/bin/env python3
"""Bring a freshly rented GPU box up as a remote GPU build lane, in two phases run by two people with two keys.

Owner's order: rented A100 boxes are used on demand. A fresh rental is brought up in under 20 minutes and must pass an
automatic per-box class check before it takes work; a box that fails is never used. The owner allowed the door's key
on a Lambda box ONLY as ``carbon-grade``, from the door's address; the door never logs in as the box's admin user.
So the bring-up is two subcommands of this one tool, each a single command, each stopping at its first failure with a
typed reason, each idempotent:

``admin``: Compute Ops runs it from THEIR OWN machine, as the box's admin user (``--user``, default ``ubuntu``) with
THEIR OWN key. It changes the box and writes nothing on the door side (no box file, no door records needed):

  host_key     the box's ed25519 host key equals ``--host-key-fingerprint``; every later ssh pins it
  shape        >= 28 CPUs (``nproc --all``) with CPUs 0-27 online, and >= 7 x 16 GiB + 8 GiB MemTotal (every box
               has the same shape: 7 slots x 4 cores x 16 GiB, cpusets 0-3 ... 24-27; the Lambda A100 40GB has 30)
  driver       exactly one GPU named ``--device-kind``, driver >= ``--driver-floor`` (an older one is upgraded from the
               provider's apt repo and the run stops: ``driver_upgrade_needs_reboot``)
  docker       Docker Engine ``--docker-version`` and containerd ``--containerd-version`` from Docker's apt repo, the
               containerd image store and the nvidia runtime merged into daemon.json, all shown by ``docker info``
  lane_user    ``carbon-grade`` (home /home/carbon-grade, not root, in the docker group), authorized_keys merged:
               ``restrict,from="<door ip>" <lane public key>`` first, then each ``--other-door-ip`` door's line of
               that same form already there (a box may serve two doors); any other line is dropped and counted
  sshd         ``/etc/ssh/sshd_config.d/00-carbon-lanes.conf``: ``MaxStartups 100:30:200`` and ``MaxSessions 64``
               (`SSHD_DROPIN_TEXT`), checked by ``sshd -t``, sshd reloaded, and refused unless ``sshd -T`` shows both:
               the door's lanes open many ssh sessions at once, and the default 10:30:100 refused them under load
               (carbon-a100, 18 Nov 2026 ~01:30Z)
  stage_root   ``/home/carbon`` owned carbon-grade:carbon-grade, mode 0755
  python       a Python >= 3.11 for the device record (`PYTHONS`; Ubuntu 22.04 ships 3.10 only: ``python3.11`` is
               installed from the distribution's own repository when none is present)

It prints a JSON summary (``carbon.gpu-box-admin.v1``, ``"admin": "PASS"``) the operator may copy to the door.

``door``: run on the door as the door user, logging in to the box ONLY as ``carbon-grade`` with the lane key, and
never using sudo there (every door-phase command is checked for it). It re-verifies the admin work READ-ONLY (a
mismatch is ``admin_incomplete:<admin step to re-run>``), then:

  images       each ``--image`` streamed from the door's daemon (``docker save | docker load``) and proved by its id:
               the JAX image first; the others stream in the background during tree, device and class check and are
               joined (``images_rest``) before the door link, so the box file still needs every image proved
  tree         only what the class check reads (`TREE_PATHS`, ``git archive`` of HEAD, which must be reachable from
               origin/main), extracted afresh every run into carbon-grade's own ``~/carbon-box-up/tree-<sha>``
  device       the box's host device record (``carbon_accelerator.py prepare``, which needs no root), fetched back
  class_check  ``gpu_rebuild_class_check.py`` in the JAX GPU image the door's receiver serves (its
               ``--graph-gpu-image-manifest``), on the box's GPU: every case bit-identical and on the GPU, the ops
               record measured against allowlist v8 and bound to this run, every digest equal to the class record's
               (CPU parity fields aside) and the ops record equal to the class's ops record
  door_link    the door's own build link (its generated ssh shim + docker wrapper) finds every admitted image
  watchdog_link  ``<--ssh-boxes-dir>/<name>.conf`` + ``.known_hosts`` written (the pinned key, the lane key), then the
               box's Docker reached exactly as a door watchdog does (`cmd_watchdog_link`: plain ``DOCKER_HOST``, the
               door's own ``~/.ssh/config``, which includes that directory through one receipted line)

The class check's container runs as uid 65532 and writes into a fresh ``~/carbon-box-up/class-check`` of mode 0703:
its owner (carbon-grade) can read and remove what is written there, the container can create files in it, and no
other local user can reach it, since its parent is 0700 (the daemon, not the container, resolves the bind mount).
The door reads each file only when the container's uid owns it, then removes the directory.

Only on PASS are the box file ``<--boxes-dir>/<--box-name>.json`` (schema ``carbon.remote-gpu-build-box.v1``) and,
beside it, the class check's own output (``<name>.class-check.json``, ``<name>.ops-record.json``) written, each
atomically, 0600 in a 0700 directory, the box file last. A run starts by removing those files, and any end but a full
PASS leaves none of them, so a box that is being (re)brought up, or that failed, is never offered. With
``--admin-summary`` the admin phase's JSON must agree with what the door reads (host key, GPU uuid, driver) and its
sha256 is recorded. ``--dry-run`` prints every command a phase would run and runs none.

``--boxes-dir`` is the door's box pool, ``<HOST_ROOT>/remote-gpu-build-boxes.d`` (`remote_gpu_build.BOXES_DIR`; HOST_ROOT
is the door's accelerators root): the door reads it again at every build, so the box joins the pool with no restart.
Draining a box is removing its box file (running builds finish); then it may be released.

**Every value deciding PASS comes from the box; a box or provider that lies or replays another box's output can
pass. PASS is an engineering admission check, not security qualification; per-build re-reads in the lane and the
door's own determinism checks remain the guard.**

What goes to the box: the lane's PUBLIC key, the public Carbon tree, public worker images and daemon.json. Nothing
else (no private key, no agent forwarding). The tool never reboots a box and never touches the door's own daemon
beyond ``docker save``. A PASS is a per-box class check, not scientific or security qualification.

    # Compute Ops, from their own machine, as the box's admin user with their own key:
    python3 -I scripts/dev/gpu_box_up.py admin --ip 203.0.113.7 --host-key-fingerprint SHA256:... \\
        --device-kind "NVIDIA A100-SXM4-40GB" --door-ip 198.51.100.2 --lane-pubkey lane.pub > admin.json
    # On the door, as the door user, logging in as carbon-grade with the lane key:
    python3 -I scripts/dev/gpu_box_up.py door --ip 203.0.113.7 --host-key-fingerprint SHA256:... \\
        --box-name a100-1 --provider lambda --device-kind "NVIDIA A100-SXM4-40GB" --door-ip 198.51.100.2 \\
        --lane-pubkey lane.pub --ssh-key ~/.ssh/carbon-lane --jax-image sha256:... --image sha256:... \\
        --graph-gpu-image-manifest jax-gpu-image.json --class-record a100-class-check.json \\
        --class-ops-record a100-ops-record.json --boxes-dir <HOST_ROOT>/remote-gpu-build-boxes.d --admin-summary admin.json
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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.reconstruction.remote_lane import parse_docker_host

BOX_SCHEMA = "carbon.remote-gpu-build-box.v1"
ADMIN_SCHEMA = "carbon.gpu-box-admin.v1"
CLASS_CHECK_SCHEMA = "carbon.gpu-rebuild.class-check.v1"
OPS_SCHEMA = "carbon.graph-gpu-ops.v1"
LANE_USER = "carbon-grade"
LANE_HOME = f"/home/{LANE_USER}"
DEFAULT_ADMIN_USER = "ubuntu"
STAGE_ROOT = "/home/carbon"
#: The door phase's own working directory on the box, carbon-grade's and 0700: the tree, the host record, the
#: class-check output.
BOX_WORK = f"{LANE_HOME}/carbon-box-up"
HOST_ROOT = f"{BOX_WORK}/host-root"
CLASS_OUT = f"{BOX_WORK}/class-check"
#: Exactly what the class check (and ``carbon_accelerator.py prepare``) import or read, found by running every child
#: rebuild from an archive of only these paths: the package, the two scripts, and the public evidence files the
#: launch versions' TRAIN material is assembled from. Nothing else of the repository goes to a rented box.
TREE_PATHS = (
    "carbon",
    "scripts/dev/gpu_rebuild_class_check.py",
    "scripts/dev/carbon_accelerator.py",
    "docs/development/evidence/f08-near-limit-public-20261020/ladder-observed.json",
    "docs/development/evidence/f08-near-limit-public-20261020/rr07-pod-environment.json",
    "docs/development/evidence/f08-near-limit-public-20261020/ladder-actions.json",
    "docs/development/evidence/f02-cold-pack-20261020/rr04-judgement.json",
    "docs/development/evidence/f02-cold-pack-20261020/rr04-convergence-ledger.jsonl",
    "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json",
    "docs/development/evidence/track-b-replay/motor-counted-v2.json",
    "docs/development/evidence/motor-pools-v1/practice.jsonl",
    "docs/development/evidence/motor-pilot-v1/records.jsonl",
    "docs/development/evidence/motor-decision-counted-v2/completion.json",
    "docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json",
    "docs/development/evidence/track-b-replay/ai-cooling-counted-v1.json",
    "docs/development/evidence/ai-cooling-counted-v1/completion.json",
)
#: The provider the owner accepted the A100 40GB build class on (OWNER-A100-40GB-BUILD-CLASS-01: "the Lambda 1x A100
#: 40GB SXM4"). Another provider is a new owner decision, not an operator flag.
ACCEPTED_PROVIDERS = ("lambda",)
#: A case's CPU parity run. A lane box never runs a CPU build: `remote_gpu_build.eligible` requires an accelerator
#: (carbon/reconstruction/remote_gpu_build.py:469) and `remote_gpu_build.op` yields None - the door's own daemon - for
#: anything not eligible (:617). These fields are therefore not compared with the class record.
CPU_FIELDS = frozenset({"cpu_state_digest", "parity_vs_cpu", "cpu_error"})
#: Every box has the same shape: 7 slots x 4 cores (owner, 17 Nov 2026), 16 GiB RAM per slot, plus headroom for the
#: host (the Lambda A100 40GB: 30 vCPUs, so 2 left for it). "Cores" are
#: LOGICAL CPUs (cpuset ids as `nproc --all` and /sys/devices/system/cpu/online count them; on a cloud VM, vCPUs,
#: which may be hyperthreads of fewer physical cores).
SLOT_CPUSETS = ("0-3", "4-7", "8-11", "12-15", "16-19", "20-23", "24-27")
MIN_CPUS = 28
MIN_MEM_KIB = (len(SLOT_CPUSETS) * 16 + 8) * 1024 * 1024
WORKER_UID = "65532"
WORKER_USER = f"{WORKER_UID}:{WORKER_UID}"
WORKER_PYTHON = "/opt/carbon-worker/bin/python"
CLASS_CHECK_STEPS = 512
DEFAULT_DRIVER_FLOOR = "580.65.06"
DEFAULT_DRIVER_PACKAGE = "nvidia-driver-580-server"
DEFAULT_DOCKER_VERSION = "29.1.3"
#: GPUYard's containerd (containerd.io 2.4.2): image ids on the containerd store must match the door's.
DEFAULT_CONTAINERD_VERSION = "2.4.2"

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


def _no_constant(name):
    raise ValueError(f"{name} is not JSON")


def _json(text, reason: str, what: str):
    """Strict JSON from the box (no NaN or Infinity), or a typed refusal; never a traceback."""
    try:
        return json.loads(text, parse_constant=_no_constant)
    except (TypeError, ValueError, RecursionError):
        raise Refused(reason, f"{what} is not strict JSON") from None


def _json_object(text, reason: str, what: str) -> dict:
    value = _json(text, reason, what)
    if type(value) is not dict:
        raise Refused(reason, f"{what} is not a JSON object")
    return value


# -- configuration ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """One phase's arguments. ``user`` is who the tool logs in as: the admin user (admin phase) or carbon-grade
    (door phase). The door-only fields stay empty for the admin phase."""

    phase: str
    user: str
    ip: str
    port: int
    ssh_key: str | None
    device_kind: str
    driver_floor: str
    driver_package: str
    docker_version: str
    containerd_version: str
    door_ip: str
    lane_pubkey: str
    host_key_fingerprint: str
    #: the OTHER doors whose lane-key line may stay on this box (``--other-door-ip``; V2, 17 Nov 2026: a configured list,
    #: never "any restrict line already there")
    other_door_ips: tuple = ()
    name: str = ""
    provider: str = ""
    images: tuple[str, ...] = ()
    jax_image: str = ""
    boxes_dir: Path | None = None
    #: the door user's per-box ssh files for its watchdogs (`write_box_ssh_files`)
    ssh_boxes_dir: Path | None = None
    class_record_digests: dict | None = None
    class_record: dict | None = None
    class_record_sha256: str = ""
    class_ops_record: dict | None = None
    class_ops_record_sha256: str = ""
    admin_summary: dict | None = None
    admin_summary_sha256: str | None = None


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
    """The lane user's only authorized_keys line: the door's address only, and ``restrict`` (OpenSSH >= 7.2: no
    forwarding of any kind, no pty, no ~/.ssh/rc, and any future restriction by default). The lane needs none of them:
    ``docker system dial-stdio`` and the input mirror's tar stream are plain non-pty commands.
    """
    return f'restrict,from="{door_ip}" {pubkey}'


#: A door's lane-key line: ``restrict``, ONE IPv4 door address, an ed25519 key and an optional plain comment. A box may
#: serve more than one door (the 116 door and carbon-door, Lead 17 Nov 2026): each door's line stays; nothing else may.
_DOOR_KEY_LINE = re.compile(
    r'restrict,from="(\d{1,3}(?:\.\d{1,3}){3})" ssh-ed25519 [A-Za-z0-9+/]{68}(?: [A-Za-z0-9._@-]{1,64})?'
)


def _other_door_line(raw: str, other_door_ips) -> bool:
    """Whether ``raw`` is a lane-key line of one of the CONFIGURED other doors (`_DOOR_KEY_LINE`, its from= address in
    ``other_door_ips``)."""
    match = _DOOR_KEY_LINE.fullmatch(raw)
    return match is not None and match.group(1) in other_door_ips


def merged_authorized_keys(current: str, line: str, other_door_ips=()) -> tuple:
    """``(text, dropped)``: the lane user's authorized_keys after the admin phase, this door's ``line`` first, then the
    lane-key line of each CONFIGURED other door already there (`_other_door_line`), each once, in order; and how many
    other lines were dropped (any key not restricted to one configured door address, V2 17 Nov 2026).
    """
    lines, dropped = [line], 0
    for raw in current.splitlines():
        raw = raw.strip()
        if not raw or raw in lines:
            continue
        if _other_door_line(raw, other_door_ips):
            lines.append(raw)
        else:
            dropped += 1
    return "\n".join(lines) + "\n", dropped


def authorized_keys_ok(text: str, line: str, other_door_ips=()) -> bool:
    """Whether the lane user's authorized_keys is exactly what the admin phase writes (`merged_authorized_keys`): this
    door's ``line`` first (whatever key type and comment its configuration accepted), then only other doors' lane-key
    lines (`_DOOR_KEY_LINE`), each once."""
    if not text.endswith("\n"):
        return False
    lines = text[:-1].split("\n")
    return (
        lines[0] == line
        and len(set(lines)) == len(lines)
        and all(_other_door_line(each, other_door_ips) for each in lines[1:])
    )


def _version(text: str) -> tuple[int, ...]:
    if not _VERSION.fullmatch(text):
        raise Refused("driver_version_unreadable", text)
    return tuple(int(part) for part in text.split("."))


def _load_json_file(path: str, reason: str) -> tuple[dict, str]:
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise Refused(reason, f"cannot read {path}") from None
    return _json_object(raw, reason, path), _sha256(raw)


#: A passing admin summary carries exactly these fields (`run_admin`), each of this type.
ADMIN_SUMMARY_FIELDS = {
    "schema": str,
    "admin": str,
    "box_ip": str,
    "port": int,
    "host_key": str,
    "device_kind": str,
    "device_uuid": str,
    "driver_version": str,
    "docker_version": str,
    "containerd_version": str,
    "shape": dict,
    "lane_user": str,
    "stage_root": str,
    "seconds": (int, float),
}


def check_admin_summary(summary: dict) -> None:
    """A passing admin summary of exactly `ADMIN_SUMMARY_FIELDS` (no field missing, none extra, every type right); what
    each field says is compared with the box in the door phase (`Session.door_admin_summary`).
    """
    if set(summary) != set(ADMIN_SUMMARY_FIELDS):
        raise Refused("admin_summary_invalid", "not exactly the admin summary's fields")
    for field, kind in ADMIN_SUMMARY_FIELDS.items():
        if type(summary[field]) is bool or not isinstance(summary[field], kind):
            raise Refused("admin_summary_invalid", f"{field}: wrong type")
    if summary["schema"] != ADMIN_SCHEMA or summary["admin"] != "PASS":
        raise Refused("admin_summary_invalid", "not a passing admin summary")


def _graph_gpu_image(path: str) -> str:
    """The image id the door's receiver serves the graph GPU lane from: read with the receiver's own reader
    (`docker_runtime.load_image_identity`, as `direct_receiver` does), and a JAX GPU worker.
    """
    from carbon.development_session.gpu_practice import gpu_image_backend
    from carbon.reconstruction.worker.docker_runtime import load_image_identity
    from carbon.reconstruction.worker.model import WorkerFailure

    try:
        identity = load_image_identity(Path(path))
    except WorkerFailure:
        raise Refused(
            "graph_gpu_image_manifest_invalid", f"cannot read {path}"
        ) from None
    if gpu_image_backend(identity) != "jax":
        raise Refused(
            "graph_gpu_image_not_jax", "the manifest is not the JAX GPU worker"
        )
    return identity.image_id


def _common(args, *, user: str) -> dict:
    """The arguments both phases share, checked."""
    try:
        if ipaddress.ip_address(args.ip).version != 4:
            raise ValueError
        door = str(ipaddress.ip_address(args.door_ip))
    except ValueError:
        raise Refused(
            "bad_argument", "--ip needs an IPv4 address; --door-ip an IP"
        ) from None
    if not 1 <= args.port <= 65535:
        raise Refused("bad_argument", "--port")
    if not _DEVICE_KIND.fullmatch(args.device_kind):
        raise Refused("bad_argument", "--device-kind")
    _version(args.driver_floor)
    if not _VERSION.fullmatch(args.docker_version):
        raise Refused("bad_argument", "--docker-version")
    if not _VERSION.fullmatch(args.containerd_version):
        raise Refused("bad_argument", "--containerd-version")
    package = getattr(args, "driver_package", DEFAULT_DRIVER_PACKAGE)
    if not _PACKAGE.fullmatch(package):
        raise Refused("bad_argument", "--driver-package")
    if not _FINGERPRINT.fullmatch(args.host_key_fingerprint):
        raise Refused("bad_argument", "--host-key-fingerprint must be SHA256:<43>")
    others = []
    for raw in getattr(args, "other_door_ip", None) or ():
        try:
            other = ipaddress.ip_address(raw)
        except ValueError:
            raise Refused(
                "bad_argument", "--other-door-ip needs an IPv4 address"
            ) from None
        if other.version != 4 or str(other) == door or str(other) in others:
            raise Refused("bad_argument", f"--other-door-ip {raw}")
        others.append(str(other))
    try:
        pubkey = public_key_line(Path(args.lane_pubkey).read_text(encoding="utf-8"))
    except OSError:
        raise Refused(
            "lane_pubkey_invalid", f"cannot read {args.lane_pubkey}"
        ) from None
    return {
        "user": user,
        "ip": args.ip,
        "port": args.port,
        "ssh_key": args.ssh_key,
        "device_kind": args.device_kind,
        "driver_floor": args.driver_floor,
        "driver_package": package,
        "docker_version": args.docker_version,
        "containerd_version": args.containerd_version,
        "door_ip": door,
        "other_door_ips": tuple(others),
        "lane_pubkey": pubkey,
        "host_key_fingerprint": args.host_key_fingerprint,
    }


def config_from_args(args) -> Config:
    if args.phase == "admin":
        # The admin phase is the box admin's, never the lane user's: the two phases cannot be confused.
        if args.user == LANE_USER:
            raise Refused(
                "admin_user_is_lane_user",
                f"the admin phase runs as the box's admin user, never {LANE_USER}",
            )
        if not _ADMIN.fullmatch(args.user):
            raise Refused("bad_argument", "--user")
        return Config(phase="admin", **_common(args, user=args.user))
    common = _common(args, user=LANE_USER)
    if not _NAME.fullmatch(args.box_name):
        raise Refused("bad_argument", "--box-name: letters, digits, '-', '_'")
    if args.provider not in ACCEPTED_PROVIDERS:
        raise Refused(
            "provider_not_accepted", f"accepted: {', '.join(ACCEPTED_PROVIDERS)}"
        )
    images = list(dict.fromkeys([args.jax_image, *args.image]))
    for image in images:
        if not _IMAGE_ID.fullmatch(image):
            raise Refused("bad_argument", f"image ids are full sha256 ids: {image}")
    record, record_sha = _load_json_file(args.class_record, "class_record_invalid")
    ops, ops_sha = _load_json_file(args.class_ops_record, "class_ops_record_invalid")
    if record.get("schema") != CLASS_CHECK_SCHEMA:
        raise Refused("class_record_invalid", "not a class-check record")
    if record.get("verdict") != "GPU_REPEATS":
        raise Refused("class_record_not_gpu_repeats", str(record.get("verdict")))
    require_complete_reference(record)
    reference = record_digests(record, "class_record_invalid")
    if ops.get("schema") != OPS_SCHEMA:
        raise Refused("class_ops_record_invalid", "not a graph GPU ops record")
    if _graph_gpu_image(args.graph_gpu_image_manifest) != args.jax_image:
        raise Refused(
            "graph_gpu_image_mismatch",
            "--jax-image is not the image --graph-gpu-image-manifest names",
        )
    summary, summary_sha = None, None
    if args.admin_summary is not None:
        summary, summary_sha = _load_json_file(
            args.admin_summary, "admin_summary_invalid"
        )
        check_admin_summary(summary)
    return Config(
        phase="door",
        **common,
        name=args.box_name,
        provider=args.provider,
        images=tuple(images),
        jax_image=args.jax_image,
        boxes_dir=Path(args.boxes_dir).expanduser(),
        ssh_boxes_dir=Path(args.ssh_boxes_dir).expanduser(),
        class_record_digests=reference,
        class_record=record,
        class_record_sha256=record_sha,
        class_ops_record=ops,
        class_ops_record_sha256=ops_sha,
        admin_summary=summary,
        admin_summary_sha256=summary_sha,
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
    """The one way a command reaches the box: the pinned host key, no agent, no forwarding, as the phase's user.

    Never over a shared connection (``ControlPath=none``, ``ControlMaster=no``): the door's ~/.ssh/config multiplexes
    ssh to lane boxes (GPUYard since 18 Nov 2026 02:21Z), and a reused master would skip this run's login with the lane
    key and its pinned host key, so the door phase could "prove" a login it never made.
    """
    argv = [
        "ssh",
        "-o",
        "ControlPath=none",
        "-o",
        "ControlMaster=no",
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
    return argv + [f"{cfg.user}@{cfg.ip}", "--", command]


# Read-only, no privilege: both phases.
CMD_SHAPE = (
    "nproc --all; cat /sys/devices/system/cpu/online; grep '^MemTotal:' /proc/meminfo"
)
CMD_DRIVER_QUERY = (
    "nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv,noheader"
)
CMD_STAGE_ROOT_STAT = f"stat -c '%U:%G %a %F' {STAGE_ROOT}"
_DOCKER_VERSION_FORMAT = (
    "docker version --format '{{.Server.Version}} {{range .Server.Components}}"
    '{{if eq .Name "containerd"}}{{.Version}}{{end}}{{end}}\' 2>/dev/null || true'
)
_DOCKER_INFO_FORMAT = "docker info --format '{{json .}}'"

# -- admin phase: as the box's admin user, with sudo ------------------------------------------------------------------


def cmd_driver_install(package: str) -> str:
    return sudo_sh(
        "set -eu; export DEBIAN_FRONTEND=noninteractive; apt-get update; "
        f"apt-get install -y {package}"
    )


#: The daemon's version and its containerd's, as the daemon reports them: "<docker> <containerd>".
CMD_DOCKER_VERSION = "sudo -n " + _DOCKER_VERSION_FORMAT


def engine_versions(text: str) -> str:
    """``"<docker> <containerd>"`` from `CMD_DOCKER_VERSION`'s output (a leading ``v`` dropped), or "" if unreadable."""
    parts = text.split()
    if len(parts) != 2:
        return ""
    return f"{parts[0]} {parts[1].removeprefix('v')}"


def cmd_docker_install(version: str, containerd: str) -> str:
    pattern = "^5:" + version.replace(".", r"\.") + "-"
    containerd_pattern = "^" + containerd.replace(".", r"\.") + "-"
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
        f"c=$(apt-cache madison containerd.io | awk '{{print $3}}' | grep -E '{containerd_pattern}' | head -n1); "
        'test -n "$v"; test -n "$c"; '
        "apt-mark unhold docker-ce docker-ce-cli containerd.io >/dev/null 2>&1 || true; "
        'apt-get install -y --allow-downgrades "docker-ce=$v" "docker-ce-cli=$v" "containerd.io=$c"; '
        "apt-mark hold docker-ce docker-ce-cli containerd.io; systemctl enable --now docker"
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
CMD_DOCKER_INFO = "sudo -n " + _DOCKER_INFO_FORMAT


def cmd_daemon_write(text: str) -> str:
    return sudo_sh(
        "set -eu; "
        + write_file_script(DAEMON_JSON, text, mode="0644", owner="root:root")
    )


CMD_LANE_UID = f"id -u {LANE_USER} 2>/dev/null || true"
CMD_LANE_CREATE = f"sudo -n useradd --create-home --home-dir {LANE_HOME} --shell /bin/bash {LANE_USER}"
CMD_LANE_GROUP = f"sudo -n usermod -aG docker {LANE_USER}"
CMD_LANE_ID = (
    f"id -u {LANE_USER}; id -nG {LANE_USER}; getent passwd {LANE_USER} | cut -d: -f6"
)
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
#: Before the write: the lines already there (none on a fresh box), so another door's lane key is kept.
CMD_AUTHORIZED_KEYS_BEFORE = sudo_sh(
    f'f={_LANE_HOME}/.ssh/authorized_keys; if [ -e "$f" ]; then cat "$f"; fi'
)
#: sshd for the door's lanes: one grade or build opens several ssh sessions (docker over ssh, staging), and four
#: slots plus the door's checks at once exceeded the default ``MaxStartups 10:30:100`` (carbon-a100 refused ssh under
#: load, 18 Nov 2026 ~01:30Z; Compute's live fix). ``00-`` sorts first in sshd_config.d, and sshd keeps the first value.
SSHD_DROPIN = "/etc/ssh/sshd_config.d/00-carbon-lanes.conf"
SSHD_DROPIN_TEXT = "MaxStartups 100:30:200\nMaxSessions 64\n"
#: What ``sshd -T`` must print for the drop-in to be in force (lower-case keys, as sshd prints them).
SSHD_EFFECTIVE = {"maxstartups": "100:30:200", "maxsessions": "64"}
CMD_SSHD_READ = sudo_sh(f"cat {SSHD_DROPIN} 2>/dev/null || true")
CMD_SSHD_WRITE = sudo_sh(
    "set -eu; install -d -o root -g root -m 0755 /etc/ssh/sshd_config.d; "
    + write_file_script(SSHD_DROPIN, SSHD_DROPIN_TEXT, mode="0644", owner="root:root")
    + f"; /usr/sbin/sshd -t || {{ rm -f {SSHD_DROPIN}; exit 1; }}"
)
#: Reloaded every run (not only on a write): a run whose reload failed after the write must not leave sshd on the old
#: values with the file already right. A reload keeps open sessions.
CMD_SSHD_RELOAD = sudo_sh("systemctl reload ssh || systemctl reload sshd")
CMD_SSHD_EFFECTIVE = "sudo -n /usr/sbin/sshd -T"
CMD_STAGE_ROOT = (
    f"sudo -n install -d -o {LANE_USER} -g {LANE_USER} -m 0755 {STAGE_ROOT}"
)
#: The interpreters the device record may run with, newest first: Carbon needs Python >= 3.11, and a Lambda Ubuntu
#: 22.04 box has only 3.10 as ``python3`` (TE3, 17 Nov 2026: the first live door phase refused at ``device``).
PYTHONS = ("python3.13", "python3.12", "python3.11")
CMD_PYTHON_FIND = (
    "for p in " + " ".join(PYTHONS) + '; do command -v "$p" && exit 0; done; true'
)
CMD_PYTHON_INSTALL = (
    "sudo -n sh -c 'set -eu; export DEBIAN_FRONTEND=noninteractive; apt-get update; "
    "apt-get install -y python3.11'"
)
_PYTHON_PATH = re.compile(r"/[A-Za-z0-9._/-]{0,200}/python3\.1[1-9]")

# -- door phase: as carbon-grade, never sudo ---------------------------------------------------------------------------

DOOR_DOCKER_VERSION = _DOCKER_VERSION_FORMAT
DOOR_DOCKER_INFO = _DOCKER_INFO_FORMAT
DOOR_WHOAMI = 'id -un; id -u; id -nG; printf "%s\\n" "$HOME"'
DOOR_AUTHORIZED_KEYS_READ = 'cat "$HOME/.ssh/authorized_keys"'
DOOR_DOCKER_LOAD = "docker load"
DOOR_WORK_DIR = f"mkdir -p {BOX_WORK} && chmod 0700 {BOX_WORK}"


def door_image_id(image: str) -> str:
    return f"docker image inspect --format '{{{{.Id}}}}' {image} 2>/dev/null || true"


def cmd_docker_save(image: str) -> list[str]:
    return ["docker", "save", image]


def cmd_git_head() -> list[str]:
    return ["git", "-C", str(ROOT), "rev-parse", "HEAD"]


def cmd_git_on_main(commit: str) -> list[str]:
    return [
        "git",
        "-C",
        str(ROOT),
        "merge-base",
        "--is-ancestor",
        commit,
        "origin/main",
    ]


def cmd_git_archive(commit: str) -> list[str]:
    return [
        "git",
        "-C",
        str(ROOT),
        "archive",
        "--format=tar",
        commit,
        "--",
        *TREE_PATHS,
    ]


def tree_dir(commit: str) -> str:
    return f"{BOX_WORK}/tree-{commit}"


def cmd_tree_extract(commit: str) -> str:
    """Every run extracts afresh (earlier trees, and any partial one, removed first), then swaps the tree in."""
    tree = tree_dir(commit)
    return (
        f"set -eu; rm -rf {BOX_WORK}/tree-*; mkdir -m 0755 {tree}.part; tar -x -C {tree}.part; "
        f"chmod -R a+rX,go-w {tree}.part; mv {tree}.part {tree}"
    )


def cmd_prepare(cfg: Config, commit: str, python: str) -> str:
    return shlex.join(
        [
            python,
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
#: Fresh each run, mode 0703: carbon-grade (owner) reads and removes; the uid-65532 container creates its files; its
#: parent `BOX_WORK` is 0700, so no other local user reaches it.
#: What the container may have left in ``/out`` is removed AS the container's uid (a subdirectory it made, even one it
#: chmod'ed 0000, is not carbon-grade's to remove): every directory made traversable first, then everything unlinked.
_PURGE_PROGRAM = (
    "import os,shutil\n"
    "for d,ds,fs in os.walk('/out'):\n"
    "    for x in ds:\n"
    "        p=os.path.join(d,x)\n"
    "        if not os.path.islink(p): os.chmod(p,0o700)\n"
    "for n in os.listdir('/out'):\n"
    "    p=os.path.join('/out',n)\n"
    "    shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.unlink(p)\n"
)
#: The largest class-check file read back (the receipted records are a few hundred KiB).
CLASS_FILE_MAX_BYTES = 16 * 1024 * 1024


def cmd_class_purge(cfg: Config) -> str:
    """Empty the class-check output dir as the container's uid, in the JAX image, with no network and no GPU."""
    return shlex.join(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            WORKER_USER,
            "--network",
            "none",
            "--read-only",
            "-v",
            f"{CLASS_OUT}:/out",
            "--entrypoint",
            WORKER_PYTHON,
            cfg.jax_image,
            "-I",
            "-c",
            _PURGE_PROGRAM,
        ]
    )


def cmd_class_out(cfg: Config) -> str:
    """Fresh each run, mode 0703: carbon-grade (owner) reads and removes; the uid-65532 container creates its files; its
    parent `BOX_WORK` is 0700, so no other local user reaches it. An earlier run's leftovers are purged as the
    container's uid first, so a container-made subdirectory can never wedge later runs.
    """
    return (
        f"set -eu; if [ -d {CLASS_OUT} ] && [ ! -L {CLASS_OUT} ]; then "
        f"{cmd_class_purge(cfg)} >/dev/null 2>&1 || true; fi; "
        f"rm -rf {CLASS_OUT}; mkdir -m 0703 {CLASS_OUT}"
    )


def cmd_class_clean(cfg: Config) -> str:
    """Best effort after every class check: purge as the container's uid, then remove the directory."""
    return f"{cmd_class_purge(cfg)} >/dev/null 2>&1; rm -rf {CLASS_OUT}"


def _read_worker_file(name: str) -> str:
    """Read a class-check file only when it is a REGULAR file (never a symlink, FIFO or device: ``find`` without ``-L``
    tests the path itself) owned by the container's uid (nothing planted before the run), at most
    `CLASS_FILE_MAX_BYTES`, with a time limit. The container has exited (``docker run`` returned) before this runs.
    """
    path = f"{CLASS_OUT}/{name}"
    return (
        f"set -eu; p={path}; "
        f'test -n "$(find "$p" -maxdepth 0 -type f -user {WORKER_UID} -size -{CLASS_FILE_MAX_BYTES}c)"; '
        f'timeout 30 head -c {CLASS_FILE_MAX_BYTES} -- "$p"'
    )


CMD_CLASS_OUTPUT_READ = _read_worker_file("class-check.json")
CMD_CLASS_OPS_READ = _read_worker_file("ops-record.json")


def cmd_class_check(cfg: Config, commit: str, uuid: str) -> str:
    """The receipted class-check runner's container, on this box's one GPU, started by carbon-grade (docker group).
    ``--entrypoint`` replaces the worker image's admission entrypoint by its own Python; ``TMPDIR`` points into the
    tmpfs (the root is read-only)."""
    return shlex.join(
        [
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
    value = (
        _json_object(text, "daemon_json_invalid", "daemon.json") if text.strip() else {}
    )
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


def cpu_list(text: str) -> set:
    """``/sys/devices/system/cpu/online`` (``0-29`` or ``0-15,32-47``) as a set of CPU numbers, or ValueError."""
    cpus: set = set()
    for part in text.split(","):
        low, _, high = part.partition("-")
        first, last = int(low), int(high or low)
        if last < first:
            raise ValueError(text)
        cpus.update(range(first, last + 1))
    return cpus


def case_id(case: dict) -> str:
    return f"{case.get('kind')}:{case.get('key')}/{case.get('arch')}"


def record_digests(record: dict, reason: str) -> dict:
    """Every digest a class-check record carries, by case id (and rebuild index): each case's ``*_digest`` fields and
    each rebuild's, except the CPU parity run's (`CPU_FIELDS`). A missing key on either side is a difference.
    """
    cases = record.get("cases")
    if type(cases) is not list or not cases:
        raise Refused(reason, "no cases")
    digests: dict = {}
    for case in cases:
        if type(case) is not dict or case_id(case) in digests:
            raise Refused(reason, "malformed or repeated case")
        name = case_id(case)
        digests[name] = "case"
        for key, value in case.items():
            if key.endswith("_digest") and key not in CPU_FIELDS:
                digests[f"{name} {key}"] = value
        rebuilds = case.get("rebuilds")
        if type(rebuilds) is not list:
            raise Refused(reason, f"{name}: rebuilds")
        digests[f"{name} rebuilds"] = len(rebuilds)
        for index, rebuild in enumerate(rebuilds):
            if type(rebuild) is not dict:
                raise Refused(reason, f"{name}: rebuild {index}")
            for key, value in rebuild.items():
                if key.endswith("_digest"):
                    digests[f"{name} rebuilds[{index}].{key}"] = value
    return digests


def require_complete_reference(record: dict) -> None:
    """Validator-2 (17 Nov): the reference class record must be COMPLETE, since `record_digests` compares symmetrically
    and an empty field on both sides would match. Every case is bit-identical and on the GPU with a sha256
    ``state_digest``, and has at least one rebuild, every rebuild carrying sha256 ``state_digest`` and
    ``predictions_digest``; the record's ``all_on_gpu`` and ``all_bit_identical`` are true.
    """
    reason = "class_record_incomplete"
    if (
        record.get("all_on_gpu") is not True
        or record.get("all_bit_identical") is not True
    ):
        raise Refused(reason, "all_on_gpu / all_bit_identical")
    cases = record.get("cases")
    if type(cases) is not list or not cases:
        raise Refused(reason, "no cases")
    for case in cases:
        if type(case) is not dict:
            raise Refused(reason, "a case is not an object")
        name = case_id(case)
        if case.get("bit_identical") is not True or case.get("ran_on_gpu") is not True:
            raise Refused(reason, f"{name}: bit_identical / ran_on_gpu")
        if type(case.get("state_digest")) is not str or not _IMAGE_ID.fullmatch(
            case["state_digest"]
        ):
            raise Refused(reason, f"{name}: state_digest")
        rebuilds = case.get("rebuilds")
        if type(rebuilds) is not list or not rebuilds:
            raise Refused(reason, f"{name}: no rebuilds")
        for index, rebuild in enumerate(rebuilds):
            for key in ("state_digest", "predictions_digest"):
                value = rebuild.get(key) if type(rebuild) is dict else None
                if type(value) is not str or not _IMAGE_ID.fullmatch(value):
                    raise Refused(reason, f"{name}: rebuilds[{index}].{key}")


def _gpu_name(row) -> str | None:
    """The first field of an ``nvidia-smi --format=csv,noheader`` row: the device name, exactly."""
    return row.split(",")[0].strip() if type(row) is str else None


def evaluate_class_check(
    raw_output: str,
    raw_ops: str,
    *,
    class_record: dict,
    class_ops_record: dict,
    device_kind: str,
    allowlist_v8: str,
) -> dict:
    """PASS (the per-case state digests) or Refused, never a traceback. PASS = every case bit-identical and on the
    GPU, on exactly this device class; the ops record measured against allowlist v8 and bound to this very output;
    every digest equal to the class record's (`record_digests`); the ops record equal to the class's ops record (all
    but its ``class_record_digest``, which names the run that wrote it)."""
    try:
        return _evaluate(
            raw_output,
            raw_ops,
            class_record=class_record,
            class_ops_record=class_ops_record,
            device_kind=device_kind,
            allowlist_v8=allowlist_v8,
        )
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as error:
        raise Refused(
            "class_check_output_invalid", f"{type(error).__name__}: {error}"[:300]
        ) from None


def _evaluate(
    raw_output, raw_ops, *, class_record, class_ops_record, device_kind, allowlist_v8
):
    invalid = "class_check_output_invalid"
    record = _json_object(raw_output, invalid, "class-check.json")
    if record.get("schema") != CLASS_CHECK_SCHEMA:
        raise Refused(invalid, "not a class-check record")
    digests = record_digests(record, invalid)
    cases = record["cases"]
    repeated_not = [case_id(c) for c in cases if c.get("bit_identical") is not True]
    if repeated_not:
        raise Refused("class_check_not_bit_identical", ", ".join(repeated_not))
    off_gpu = [case_id(c) for c in cases if c.get("ran_on_gpu") is not True]
    if off_gpu or record.get("all_on_gpu") is not True:
        raise Refused("class_check_not_on_gpu", ", ".join(off_gpu))
    if record.get("verdict") != "GPU_REPEATS":
        raise Refused("class_check_verdict", str(record.get("verdict")))
    smi = record.get("nvidia_smi")
    rows = smi.get("gpus") if type(smi) is dict else None
    if (
        type(rows) is not list
        or not rows
        or any(_gpu_name(row) != device_kind for row in rows)
    ):
        raise Refused("class_check_wrong_device", str(rows)[:300])
    ops = _json_object(raw_ops, invalid, "ops-record.json")
    if ops.get("schema") != OPS_SCHEMA:
        raise Refused(invalid, "not a graph GPU ops record")
    if ops.get("allowlist_digest") != allowlist_v8:
        raise Refused("class_check_not_allowlist_v8", str(ops.get("allowlist_digest")))
    # gpu_rebuild_class_check.ops_record binds the record it was derived from by this digest.
    if ops.get("class_record_digest") != _sha256(
        json.dumps(record, sort_keys=True).encode()
    ):
        raise Refused("class_check_ops_record_unbound", "ops record names another run")
    reference = record_digests(class_record, "class_record_invalid")
    if digests != reference:
        differ = sorted(
            k
            for k in set(digests) | set(reference)
            if digests.get(k, "<missing>") != reference.get(k, "<missing>")
        )
        raise Refused("class_check_digest_mismatch", ", ".join(differ[:12]))

    def comparable(value):
        return _canonical(
            {k: v for k, v in value.items() if k != "class_record_digest"}
        )

    if comparable(ops) != comparable(class_ops_record):
        raise Refused("class_check_ops_mismatch", "ops record differs from the class's")
    return {
        "case_digests": {case_id(c): c["state_digest"] for c in cases},
    }


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

    try:
        digest = _sha256(_canonical(document))
        require_host_device(HostDeviceRecord(document, digest), GPU_PROFILE)
    except (WorkerFailure, TypeError, ValueError, AttributeError):
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


def box_files(cfg: Config) -> tuple[Path, Path, Path]:
    """The box file and, beside it, the class check's own output and ops record."""
    return (
        box_path(cfg),
        cfg.boxes_dir / f"{cfg.name}.class-check.json",
        cfg.boxes_dir / f"{cfg.name}.ops-record.json",
    )


def remove_box_files(cfg: Config) -> None:
    for path in box_files(cfg):
        if os.path.lexists(path):
            os.unlink(path)


def write_private(directory: Path, path: Path, body: bytes) -> Path:
    """Atomic and EXCLUSIVE: a 0600 temp file in the same directory, fsynced, then hard-linked to the name, which fails
    if the name exists (another run's file is never replaced; this run removed its own at the start).
    """
    fd, part = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(part, 0o600)
        try:
            os.link(part, path)
        except FileExistsError:
            raise Refused(
                "box_file_exists", f"{path.name} appeared during the run"
            ) from None
    finally:
        if os.path.lexists(part):
            os.unlink(part)
    handle = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)
    return path


def write_box_files(cfg: Config, document: dict, raw_output: str, raw_ops: str) -> Path:
    """The class check's output and ops record first, the box file (the admission) last."""
    path, output_path, ops_path = box_files(cfg)
    write_private(cfg.boxes_dir, output_path, raw_output.encode("utf-8"))
    write_private(cfg.boxes_dir, ops_path, raw_ops.encode("utf-8"))
    body = json.dumps(document, indent=1, sort_keys=True) + "\n"
    return write_private(cfg.boxes_dir, path, body.encode("utf-8"))


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
    """One phase's run: every external command passes through `call` (and so through the injected runner)."""

    def __init__(self, cfg: Config, runner, *, log=None):
        self.cfg = cfg
        self.runner = runner
        self.log = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self.step = "start"
        #: the box's Python >= 3.11 (`_python_seen`), found by the python step before the device record needs it
        self.python = None
        self.known_hosts: str | None = None

    def _guard(self, argv, pipe_from):
        """What leaves this machine, refused before anything is sent (a violation is a bug in this tool): no private
        key text in any command; in the door phase no sudo on the box, and only public images or the public tree
        streamed; in the admin phase nothing streamed at all."""
        if any("PRIVATE KEY" in str(arg) for arg in argv):
            raise Refused("secret_refused", "a command carried private key text")
        if (
            self.cfg.phase == "door"
            and argv
            and argv[0] == "ssh"
            and "sudo" in argv[-1]
        ):
            raise Refused(
                "door_sudo_refused", "the door phase never uses sudo on the box"
            )
        if pipe_from is None:
            return
        pipe_from = list(pipe_from)
        if self.cfg.phase != "door":
            raise Refused("upload_refused", shlex.join(pipe_from))
        allowed = [cmd_docker_save(image) for image in self.cfg.images]
        commit = pipe_from[5] if len(pipe_from) > 5 else ""
        if pipe_from not in allowed and not (
            _COMMIT.fullmatch(commit) and pipe_from == cmd_git_archive(commit)
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

    def run_step(self, name, function, *args):
        self.step = name
        started = time.monotonic()
        try:
            value = function(*args)
        except Refused:
            raise
        except (TypeError, ValueError, KeyError, AttributeError, IndexError) as error:
            # Whatever the box printed, a malformed answer is a typed refusal, never a traceback.
            raise Refused(
                f"{name}_output_invalid", f"{type(error).__name__}: {error}"[:300]
            ) from None
        self.log(
            json.dumps(
                {
                    "phase": self.cfg.phase,
                    "step": name,
                    "status": "ok",
                    "seconds": round(time.monotonic() - started, 1),
                }
            )
        )
        return value

    def verify(self, name, function, *args):
        """A door-phase re-check of the admin phase's work: any refusal names the admin step to re-run."""
        try:
            return self.run_step(name, function, *args)
        except Refused as refusal:
            raise Refused(
                f"admin_incomplete:{name}", f"{refusal.reason}: {refusal.detail}"
            ) from None

    # -- shared steps (read-only) --------------------------------------------------------------------------------------

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

    def shape(self) -> dict:
        out = self.remote(CMD_SHAPE, reason="shape_unreadable")
        lines = out.splitlines()
        try:
            cpus = int(lines[0].strip())
            online = lines[1].strip()
            online_set = cpu_list(online)
            mem_kib = int(lines[2].split()[1])
        except (IndexError, ValueError):
            raise Refused("shape_unreadable", out.strip()[-200:]) from None
        if cpus < MIN_CPUS:
            raise Refused("slot_shape_cpus", f"{cpus} CPUs < {MIN_CPUS}")
        if not set(range(MIN_CPUS)) <= online_set:
            raise Refused(
                "slot_cpus_offline", f"CPUs 0-{MIN_CPUS - 1} are not all online"
            )
        if mem_kib < MIN_MEM_KIB:
            raise Refused(
                "slot_shape_memory", f"MemTotal {mem_kib} kB < {MIN_MEM_KIB} kB"
            )
        return {"cpus": cpus, "online": online, "mem_total_kib": mem_kib}

    def read_driver(self):
        """``(uuid, driver)`` of the box's one GPU of exactly ``--device-kind``, or None when nvidia-smi fails."""
        cfg = self.cfg
        rc, out, _ = self.call(ssh(cfg, self.known_hosts, CMD_DRIVER_QUERY))
        if rc != 0:
            return None
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
        return uuid, driver

    def _below_floor(self, driver: str) -> bool:
        return _version(driver) < _version(self.cfg.driver_floor)

    def docker_problem(self, info_command: str, version_command: str):
        """``(reason, detail)`` when the daemon does not show the pinned docker and containerd versions, the containerd
        snapshotter and the nvidia runtime; None when it does."""
        info = _json_object(
            self.remote(info_command, reason="docker_unreadable"),
            "docker_unreadable",
            "docker info",
        )
        if info.get("ServerVersion") != self.cfg.docker_version:
            return "docker_version_mismatch", str(info.get("ServerVersion"))
        engine = engine_versions(
            self.remote(version_command, reason="docker_unreadable")
        )
        if engine != self._engine():
            return "containerd_version_mismatch", engine or "unreadable"
        if "io.containerd.snapshotter.v1" not in json.dumps(info.get("DriverStatus")):
            return "docker_snapshotter_missing", json.dumps(info.get("DriverStatus"))
        runtimes = info.get("Runtimes")
        if type(runtimes) is not dict or "nvidia" not in runtimes:
            return (
                "docker_nvidia_runtime_missing",
                "docker info lists no nvidia runtime",
            )
        return None

    def _engine(self) -> str:
        return f"{self.cfg.docker_version} {self.cfg.containerd_version}"

    def _stage_root_seen(self):
        seen = self.remote(CMD_STAGE_ROOT_STAT, reason="stage_root_failed").strip()
        if seen != f"{LANE_USER}:{LANE_USER} 755 directory":
            raise Refused("stage_root_mismatch", seen)

    # -- admin phase (as the box's admin user) -------------------------------------------------------------------------

    def driver(self):
        cfg = self.cfg
        seen = self.read_driver()
        if seen is None or self._below_floor(seen[1]):
            # No driver, one below the floor, or one that no longer talks to its library (an upgrade waiting for a
            # reboot): install the series and stop. The tool never reboots a box and never loops.
            self.remote(
                cmd_driver_install(cfg.driver_package), reason="driver_install_failed"
            )
            what = (
                "nvidia-smi failed"
                if seen is None
                else f"driver {seen[1]} < {cfg.driver_floor}"
            )
            raise Refused(
                "driver_upgrade_needs_reboot",
                f"{what}; {cfg.driver_package} installed: reboot the box, then run the admin phase again",
            )
        return seen

    def docker(self):
        cfg = self.cfg
        if (
            engine_versions(self.remote(CMD_DOCKER_VERSION, reason="docker_unreadable"))
            != self._engine()
        ):
            self.remote(
                cmd_docker_install(cfg.docker_version, cfg.containerd_version),
                reason="docker_install_failed",
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
        restarted = previous != merged
        if restarted:
            self.remote(CMD_DOCKER_RESTART, reason="docker_restart_failed")
        problem = self.docker_problem(CMD_DOCKER_INFO, CMD_DOCKER_VERSION)
        if problem and not restarted:
            # daemon.json is already right but the daemon does not show it (an earlier run's restart failed, or
            # someone changed it by hand): restart once rather than wedge every later run.
            self.remote(CMD_DOCKER_RESTART, reason="docker_restart_failed")
            problem = self.docker_problem(CMD_DOCKER_INFO, CMD_DOCKER_VERSION)
        if problem:
            raise Refused(*problem)
        return self._engine().split()

    def lane_user(self):
        if not self.remote(CMD_LANE_UID, reason="lane_user_failed").strip():
            self.remote(CMD_LANE_CREATE, reason="lane_user_failed")
        self.remote(CMD_LANE_GROUP, reason="lane_user_failed")
        lines = self.remote(CMD_LANE_ID, reason="lane_user_failed").splitlines()
        if not lines or lines[0].strip() == "0":
            raise Refused("lane_user_is_root", f"{LANE_USER} has uid 0")
        if len(lines) < 2 or "docker" not in lines[1].split():
            raise Refused("lane_user_not_in_docker", lines[1] if len(lines) > 1 else "")
        if len(lines) < 3 or lines[2].strip() != LANE_HOME:
            raise Refused("lane_home_mismatch", lines[2] if len(lines) > 2 else "")
        line = authorized_keys_line(self.cfg.door_ip, self.cfg.lane_pubkey)
        before = self.remote(CMD_AUTHORIZED_KEYS_BEFORE, reason="lane_user_failed")
        wanted, dropped = merged_authorized_keys(before, line, self.cfg.other_door_ips)
        if dropped:
            self.log(
                json.dumps(
                    {
                        "phase": "admin",
                        "step": "lane_user",
                        "dropped_authorized_keys_lines": dropped,
                    }
                )
            )
        # merged, never a plain replace: a configured other door's lane key on this box stays
        self.remote(cmd_authorized_keys_write(wanted[:-1]), reason="lane_user_failed")
        if self.remote(CMD_AUTHORIZED_KEYS_READ, reason="lane_user_failed") != wanted:
            raise Refused(
                "authorized_keys_mismatch",
                "authorized_keys is not this door's line plus other doors' lane keys",
            )

    def sshd(self):
        if self.remote(CMD_SSHD_READ, reason="sshd_failed") != SSHD_DROPIN_TEXT:
            self.remote(CMD_SSHD_WRITE, reason="sshd_failed")
        self.remote(CMD_SSHD_RELOAD, reason="sshd_failed")
        seen = {}
        for line in self.remote(CMD_SSHD_EFFECTIVE, reason="sshd_failed").splitlines():
            key, _, value = line.strip().partition(" ")
            if key in SSHD_EFFECTIVE:
                seen[key] = value.strip()
        if seen != SSHD_EFFECTIVE:
            raise Refused("sshd_limits_not_in_force", json.dumps(seen, sort_keys=True))
        return SSHD_DROPIN

    def stage_root(self):
        self.remote(CMD_STAGE_ROOT, reason="stage_root_failed")
        self._stage_root_seen()

    def _python_seen(self):
        """The newest Python >= 3.11 on the box (`PYTHONS`), by its absolute path, or Refused."""
        lines = self.remote(CMD_PYTHON_FIND, reason="python_failed").split()
        found = lines[0] if lines else ""
        if not _PYTHON_PATH.fullmatch(found):
            raise Refused("python_missing", f"no {' / '.join(PYTHONS)} on the box")
        self.python = found
        return found

    def python_ready(self):
        try:
            return self._python_seen()
        except Refused:
            self.remote(CMD_PYTHON_INSTALL, reason="python_install_failed")
            return self._python_seen()

    # -- door phase (as carbon-grade, read-only re-checks first) -------------------------------------------------------

    def door_lane_user(self):
        """Logged in as carbon-grade with the lane key: who we are, and our own authorized_keys."""
        lines = self.remote(DOOR_WHOAMI, reason="lane_login_failed").splitlines()
        if len(lines) < 4:
            raise Refused("lane_user_unreadable", " / ".join(lines))
        user, uid, groups, home = (part.strip() for part in lines[:4])
        if user != LANE_USER:
            raise Refused("lane_user_mismatch", user)
        if uid == "0":
            raise Refused("lane_user_is_root", f"{LANE_USER} has uid 0")
        if "docker" not in groups.split():
            raise Refused("lane_user_not_in_docker", groups)
        if home != LANE_HOME:
            raise Refused("lane_home_mismatch", home)
        line = authorized_keys_line(self.cfg.door_ip, self.cfg.lane_pubkey)
        if not authorized_keys_ok(
            self.remote(DOOR_AUTHORIZED_KEYS_READ, reason="lane_user_failed"),
            line,
            self.cfg.other_door_ips,
        ):
            raise Refused(
                "authorized_keys_mismatch",
                "authorized_keys is not this door's line plus other doors' lane keys",
            )

    def door_link(self, host_key):
        """The door's own build link (`door_link_files`, no hand-made ssh config) reaches the box's Docker and finds
        every admitted image, or Refused: live 116, 18 Nov 2026, the replacement A100 passed every check over this
        phase's own ssh and was ADMITTED at 15:01Z, while the door's link got "Permission denied (publickey)" and no
        build ran for three hours."""
        directory = tempfile.mkdtemp(prefix="gpu-box-link-")
        try:
            try:
                wrapper = door_link_files(self.cfg, host_key, directory)
            except Exception as error:  # noqa: BLE001 - unwritable link refuses
                raise Refused(
                    "door_link_failed", f"{type(error).__name__}: {error}"[:300]
                ) from None
            rc, out, err = self.call(cmd_door_link(wrapper, self.cfg))
            seen = out.split()
            wanted = list(self.cfg.images)
            if rc != 0 or seen != wanted:
                tail = (err or out or "").strip()[-300:]
                raise Refused("door_link_failed", f"rc={rc}: {tail}")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def watchdog_link(self, host_key):
        """The door's watchdogs reach the box (`cmd_watchdog_link`) through its per-box ssh files, or Refused: no box
        is admitted whose containers the door could not see or stop."""
        try:
            write_box_ssh_files(self.cfg, host_key)
        except (OSError, Refused) as error:
            raise Refused(
                "watchdog_link_failed", f"{type(error).__name__}: {error}"[:300]
            ) from None
        rc, out, err = self.call(cmd_watchdog_link(self.cfg))
        if rc != 0 or not out.strip():
            tail = (err or out or "").strip()[-300:]
            raise Refused(
                "watchdog_link_failed",
                f"rc={rc}: {tail} (the door's ~/.ssh/config needs "
                f"'Include {self.cfg.ssh_boxes_dir}/*.conf' before its first Host block)",
            )

    def door_driver(self):
        seen = self.read_driver()
        if seen is None:
            raise Refused("driver_unreadable", "nvidia-smi failed")
        if self._below_floor(seen[1]):
            raise Refused(
                "driver_below_floor", f"driver {seen[1]} < {self.cfg.driver_floor}"
            )
        return seen

    def door_docker(self):
        problem = self.docker_problem(DOOR_DOCKER_INFO, DOOR_DOCKER_VERSION)
        if problem:
            raise Refused(*problem)

    def door_stage_root(self):
        self._stage_root_seen()

    def door_python(self):
        return self._python_seen()

    def door_admin_summary(self, host_key, uuid, driver, shape):
        """The admin phase's own summary, when the operator brought it: EVERY field it states must describe the box the
        door reads (or the versions and names the door requires)."""
        summary, cfg = self.cfg.admin_summary, self.cfg
        for field, want in (
            ("box_ip", cfg.ip),
            ("port", cfg.port),
            ("host_key", host_key),
            ("device_kind", cfg.device_kind),
            ("device_uuid", uuid),
            ("driver_version", driver),
            ("docker_version", cfg.docker_version),
            ("containerd_version", cfg.containerd_version),
            ("shape", shape),
            ("lane_user", LANE_USER),
            ("stage_root", STAGE_ROOT),
        ):
            if summary.get(field) != want:
                raise Refused(
                    "admin_summary_mismatch", f"{field}: {summary.get(field)!r}"
                )

    def images(self, only=None):
        """Load each of ``only`` (default: every ``--image``) on the box unless it is there already, proved by its id."""
        for image in self.cfg.images if only is None else only:
            if (
                self.remote(door_image_id(image), reason="image_unreadable").strip()
                == image
            ):
                continue
            self.remote(
                DOOR_DOCKER_LOAD,
                reason="image_load_failed",
                pipe_from=cmd_docker_save(image),
            )
            seen = self.remote(door_image_id(image), reason="image_unreadable").strip()
            if seen != image:
                raise Refused(
                    "image_id_mismatch", f"{image} loaded as {seen or 'nothing'}"
                )

    def tree(self):
        rc, out, err = self.call(cmd_git_head())
        commit = out.strip()
        if rc != 0 or not _COMMIT.fullmatch(commit):
            raise Refused("tree_unreadable", (err or out).strip()[-200:])
        # Unpushed local commits never leave the door.
        rc, _, err = self.call(cmd_git_on_main(commit))
        if rc != 0:
            raise Refused(
                "tree_not_on_origin_main",
                f"{commit} is not reachable from origin/main (rc={rc}: {err.strip()[-200:]})",
            )
        self.remote(DOOR_WORK_DIR, reason="tree_ship_failed")
        self.remote(
            cmd_tree_extract(commit),
            reason="tree_ship_failed",
            pipe_from=cmd_git_archive(commit),
        )
        return commit

    def device(self, commit, uuid, driver):
        self.remote(
            cmd_prepare(self.cfg, commit, self.python), reason="device_record_failed"
        )
        document = _json_object(
            self.remote(CMD_DEVICE_READ, reason="device_record_failed"),
            "device_record_invalid",
            "host-device.json",
        )
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
        self.remote(cmd_class_out(self.cfg), reason="class_check_failed")
        try:
            rc, out, err = self.call(
                ssh(
                    self.cfg,
                    self.known_hosts,
                    cmd_class_check(self.cfg, commit, uuid),
                )
            )
            r_out, raw_output, _ = self.call(
                ssh(self.cfg, self.known_hosts, CMD_CLASS_OUTPUT_READ)
            )
            r_ops, raw_ops, _ = self.call(
                ssh(self.cfg, self.known_hosts, CMD_CLASS_OPS_READ)
            )
        finally:
            # best effort: the next run recreates it from nothing anyway
            self.call(ssh(self.cfg, self.known_hosts, cmd_class_clean(self.cfg)))
        if r_out != 0 or not raw_output.strip():
            raise Refused(
                "class_check_failed", f"rc={rc}: {(err or out).strip()[-400:]}"
            )
        raw_ops = raw_ops if r_ops == 0 else ""
        summary = evaluate_class_check(
            raw_output,
            raw_ops,
            class_record=self.cfg.class_record,
            class_ops_record=self.cfg.class_ops_record,
            device_kind=self.cfg.device_kind,
            allowlist_v8=_allowlist_v8_digest(),
        )
        if rc != 0:
            raise Refused("class_check_failed", f"rc={rc} although the record passed")
        return summary, raw_output, raw_ops


def _known_hosts_scratch():
    """A private temporary directory for the pinned known_hosts file of this run (removed at the end)."""
    scratch = tempfile.mkdtemp(prefix="gpu-box-up-")
    return scratch, os.path.join(scratch, "known_hosts")


def run_admin(cfg: Config, runner, *, log=None) -> dict:
    """The admin phase. Changes the box; writes nothing on the door side. Returns the summary document."""
    started = time.monotonic()
    session = Session(cfg, runner, log=log)
    scratch, session.known_hosts = _known_hosts_scratch()
    try:
        host_key = session.run_step("host_key", session.host_key)
        shape = session.run_step("shape", session.shape)
        uuid, driver = session.run_step("driver", session.driver)
        docker, containerd = session.run_step("docker", session.docker)
        session.run_step("lane_user", session.lane_user)
        session.run_step("sshd", session.sshd)
        session.run_step("stage_root", session.stage_root)
        session.run_step("python", session.python_ready)
    except Refused as refusal:
        return {
            "schema": ADMIN_SCHEMA,
            "admin": "REFUSED",
            "box_ip": cfg.ip,
            "step": session.step,
            "reason": refusal.reason,
            "detail": refusal.detail,
            "seconds": round(time.monotonic() - started, 1),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {
        "schema": ADMIN_SCHEMA,
        "admin": "PASS",
        "box_ip": cfg.ip,
        "port": cfg.port,
        "host_key": host_key,
        "device_kind": cfg.device_kind,
        "device_uuid": uuid,
        "driver_version": driver,
        "docker_version": docker,
        "containerd_version": containerd,
        "shape": shape,
        "lane_user": LANE_USER,
        "stage_root": STAGE_ROOT,
        "seconds": round(time.monotonic() - started, 1),
    }


def box_ssh_key(cfg) -> str | None:
    """The lane key's absolute path as the box file names it (``ssh_key``), or None when the phase has no key."""
    return os.path.abspath(os.path.expanduser(cfg.ssh_key)) if cfg.ssh_key else None


def door_link_files(cfg, host_key: str, directory: str) -> str:
    """The door's OWN build link for this box, written into ``directory`` by `remote_gpu_build`'s generators: its pinned
    ``known_hosts``, its ``bin/ssh`` shim (`pinned_ssh_options`: the pinned key strictly and the key the box file will
    name) and its ``docker`` wrapper. Returns the wrapper's path. The same text the door writes at a box's first op, so
    what passes here is the link every build will use.
    """
    from types import SimpleNamespace

    from carbon.reconstruction import remote_gpu_build as rgb

    lane = SimpleNamespace(
        lane_dir=directory, spec=SimpleNamespace(ssh_key=box_ssh_key(cfg))
    )
    bin_dir = os.path.join(directory, "bin")
    os.makedirs(bin_dir, mode=0o700, exist_ok=True)
    ssh_binary = shutil.which("ssh") or "/usr/bin/ssh"
    docker_binary = shutil.which("docker") or "/usr/bin/docker"
    texts = {
        os.path.join(directory, "known_hosts"): (host_key + "\n", 0o600),
        os.path.join(bin_dir, "ssh"): (rgb.ssh_shim_text(lane, ssh_binary), 0o500),
        os.path.join(directory, "docker"): (
            rgb.wrapper_text(
                f"ssh://{cfg.user}@{cfg.ip}",
                os.environ.get("HOME", "/"),
                docker_binary,
                bin_dir,
            ),
            0o500,
        ),
    }
    for path, (text, mode) in texts.items():
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path, mode)
    return os.path.join(directory, "docker")


def cmd_door_link(wrapper: str, cfg) -> list[str]:
    """Every admitted image, by full id, through the door's own wrapper (``image inspect``: ``docker images`` hides
    untagged ids on a containerd store)."""
    return [wrapper, "image", "inspect", "--format", "{{.Id}}", *cfg.images]


#: The door's watchdogs and reapers reach a box's Docker as the door user with only ``PATH``, ``DOCKER_HOST`` and
#: ``HOME`` (`carbon.reconstruction.remote_lane.docker_environment`): their ssh reads the door's OWN ``~/.ssh/config``,
#: not the build link's pinned shim. That file reads one ``<box>.conf`` per box from here through ONE line placed once
#: (V2 receipt), before its first Host block: ``Include ~/.ssh/config.d/carbon-boxes/*.conf``. Live 116, 20 Nov 2026:
#: the first autoscaled A100 built fine, but its 7 watchdogs got "Host key verification failed" on every poll (no Host
#: block for its address), so none could see or stop its containers. `gpu_pool_autoscale` removes the files at release.
DEFAULT_SSH_BOXES_DIR = "~/.ssh/config.d/carbon-boxes"
WATCHDOG_PATH = "/usr/local/bin:/usr/bin:/bin"


def box_docker_host(cfg) -> str:
    return f"ssh://{LANE_USER}@{cfg.ip}" + ("" if cfg.port == 22 else f":{cfg.port}")


def box_ssh_files(cfg) -> tuple[Path, Path]:
    """The box's ssh config block and the pinned host key it names."""
    return (
        cfg.ssh_boxes_dir / f"{cfg.name}.conf",
        cfg.ssh_boxes_dir / f"{cfg.name}.known_hosts",
    )


def box_ssh_conf_text(cfg, known_hosts: Path) -> str:
    """The build link's settings (`pinned_ssh_options`): the pinned host key strictly, the lane key alone."""
    lines = [
        f"# {cfg.name}: written by gpu_box_up door at admission; gpu_pool_autoscale removes it at release",
        f"Host {cfg.ip}",
        f"  User {LANE_USER}",
    ]
    if cfg.port != 22:
        lines.append(f"  Port {cfg.port}")
    key = box_ssh_key(cfg)
    if key:
        lines += [f"  IdentityFile {key}", "  IdentitiesOnly yes"]
    lines += [
        f"  UserKnownHostsFile {known_hosts}",
        "  StrictHostKeyChecking yes",
        "  ForwardAgent no",
        "  ForwardX11 no",
        "  ClearAllForwardings yes",
    ]
    return "\n".join(lines) + "\n"


def _replace_private(path: Path, text: str) -> None:
    fd, part = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(part, 0o600)
        os.replace(part, path)
    finally:
        if os.path.lexists(part):
            os.unlink(part)


def write_box_ssh_files(cfg, host_key: str) -> None:
    """This box's ``<name>.known_hosts`` (the pinned key line) and ``<name>.conf`` (0600, each replaced atomically).
    Another box's files naming the same address go first: ssh takes the FIRST matching Host block, and a provider
    recycles addresses."""
    directory = ready_boxes_dir(cfg.ssh_boxes_dir)
    conf, known = box_ssh_files(cfg)
    host = f"Host {cfg.ip}\n"
    for other in sorted(directory.glob("*.conf")):
        if other != conf and host in other.read_text(encoding="utf-8"):
            other.unlink()
            other.with_suffix(".known_hosts").unlink(missing_ok=True)
    _replace_private(known, host_key + "\n")
    _replace_private(conf, box_ssh_conf_text(cfg, known))


def remove_box_ssh_files(cfg) -> None:
    for path in box_ssh_files(cfg):
        if os.path.lexists(path):
            os.unlink(path)


def cmd_watchdog_link(cfg) -> list[str]:
    """The box's Docker exactly as a door watchdog reaches it (`remote_lane.docker_environment`)."""
    return [
        "env",
        "-i",
        f"PATH={WATCHDOG_PATH}",
        f"DOCKER_HOST={box_docker_host(cfg)}",
        f"HOME={os.environ.get('HOME', '/')}",
        "docker",
        "version",
        "--format",
        "{{.Server.Version}}",
    ]


def box_document(
    cfg,
    *,
    host_key,
    driver,
    device,
    device_digest,
    summary,
    raw_output,
    raw_ops,
    commit,
    now,
):
    docker_host = box_docker_host(cfg)
    parse_docker_host(docker_host)
    document = {
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
        "tree_commit": commit,
        "class_check_image_id": cfg.jax_image,
        "class_check": {
            "case_digests": summary["case_digests"],
            "class_record_sha256": cfg.class_record_sha256,
            "class_ops_record_sha256": cfg.class_ops_record_sha256,
        },
        "check_output_sha256": _sha256(raw_output.encode("utf-8")),
        "check_ops_record_sha256": _sha256(raw_ops.encode("utf-8")),
        "admitted_unix": int(now),
    }
    if cfg.admin_summary_sha256 is not None:
        document["admin_summary_sha256"] = cfg.admin_summary_sha256
    if cfg.ssh_key:
        # the door's lane key that passed every check above: the door's builds use exactly it (`pinned_ssh_options`)
        document["ssh_key"] = box_ssh_key(cfg)
    return document


def bring_up(cfg: Config, runner, *, now=time.time, log=None) -> dict:
    """The door phase: re-verify the admin work read-only, then images, tree, device and class check as carbon-grade;
    write the box file only on PASS. Returns the outcome document."""
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
    # A box being (re)brought up is not offered until it passes again. Its ssh files stay while it is re-checked
    # (a watchdog of a build still running on it needs them); a run that wrote them for a new box removes them.
    remove_box_files(cfg)
    had_ssh_files = os.path.lexists(box_ssh_files(cfg)[0])
    session = Session(cfg, runner, log=log)
    scratch, session.known_hosts = _known_hosts_scratch()
    admitted = False
    background = ThreadPoolExecutor(max_workers=1)
    try:
        host_key = session.run_step("host_key", session.host_key)
        session.verify("lane_user", session.door_lane_user)
        shape = session.verify("shape", session.shape)
        uuid, driver = session.verify("driver", session.door_driver)
        session.verify("docker", session.door_docker)
        session.verify("stage_root", session.door_stage_root)
        session.verify("python", session.door_python)
        if cfg.admin_summary is not None:
            session.run_step(
                "admin_summary",
                session.door_admin_summary,
                host_key,
                uuid,
                driver,
                shape,
            )
        # The class check needs only the JAX image: it lands first, and the other images (the 3.4 GB torch image,
        # ~230 s over the door's link) stream in the background meanwhile; every image is proved by its id and joined
        # before the door link and the box file, so nothing is admitted earlier (Lead + owner, 19 Nov 2026: faster
        # bring-up; the door->box link, not compression, is the limit: the saved images are already compressed).
        session.run_step("images", session.images, [cfg.jax_image])
        rest = [image for image in cfg.images if image != cfg.jax_image]
        streaming = background.submit(session.images, rest)
        commit = session.run_step("tree", session.tree)
        device, device_digest = session.run_step(
            "device", session.device, commit, uuid, driver
        )
        summary, raw_output, raw_ops = session.run_step(
            "class_check", session.class_check, commit, uuid
        )
        session.run_step("images_rest", streaming.result)
        session.run_step("door_link", session.door_link, host_key)
        session.run_step("watchdog_link", session.watchdog_link, host_key)
        document = box_document(
            cfg,
            host_key=host_key,
            driver=driver,
            device=device,
            device_digest=device_digest,
            summary=summary,
            raw_output=raw_output,
            raw_ops=raw_ops,
            commit=commit,
            now=now(),
        )
        session.step = "box_file"
        path = write_box_files(cfg, document, raw_output, raw_ops)
        admitted = True
    except Refused as refusal:
        return refused(session.step, refusal)
    finally:
        # a background image stream still running after an earlier refusal ends before this run does
        background.shutdown(wait=True)
        # any end but a full PASS (a refusal, an OSError, an interrupt) leaves none of the three files
        if not admitted:
            remove_box_files(cfg)
            if not had_ssh_files:
                remove_box_ssh_files(cfg)
        shutil.rmtree(scratch, ignore_errors=True)
    return {
        "status": "ADMITTED",
        "box_file": str(path),
        "seconds": round(time.monotonic() - started, 1),
    }


def _planner(cfg: Config):
    kh = "<known_hosts>"

    def remote(step, command, pipe_from=None):
        text = shlex.join(ssh(cfg, kh, command))
        return (step, f"{shlex.join(pipe_from)} | {text}" if pipe_from else text)

    return remote


def plan_admin(cfg: Config) -> list[tuple[str, str]]:
    """Every command the admin phase may send, in order."""
    remote = _planner(cfg)
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
            "docker (only when another version)",
            cmd_docker_install(cfg.docker_version, cfg.containerd_version),
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
    steps.append(remote("docker", CMD_DOCKER_VERSION))
    steps.append(
        remote("docker (only when docker info does not show it)", CMD_DOCKER_RESTART)
    )
    steps.append(remote("lane_user", CMD_LANE_UID))
    steps.append(remote("lane_user (only when missing)", CMD_LANE_CREATE))
    for command in (
        CMD_LANE_GROUP,
        CMD_LANE_ID,
        CMD_AUTHORIZED_KEYS_BEFORE,
        cmd_authorized_keys_write(
            authorized_keys_line(cfg.door_ip, cfg.lane_pubkey)
            + "\n<the --other-door-ip doors' restrict,from= lane-key lines already there>"
        ),
        CMD_AUTHORIZED_KEYS_READ,
    ):
        steps.append(remote("lane_user", command))
    steps.append(remote("sshd", CMD_SSHD_READ))
    steps.append(remote("sshd (only when it differs)", CMD_SSHD_WRITE))
    steps.append(remote("sshd", CMD_SSHD_RELOAD))
    steps.append(remote("sshd", CMD_SSHD_EFFECTIVE))
    steps.append(remote("stage_root", CMD_STAGE_ROOT))
    steps.append(remote("stage_root", CMD_STAGE_ROOT_STAT))
    steps.append(remote("python", CMD_PYTHON_FIND))
    steps.append(remote("python (only when none is present)", CMD_PYTHON_INSTALL))
    steps.append(remote("python (only when none is present)", CMD_PYTHON_FIND))
    return steps


def plan_door(cfg: Config) -> list[tuple[str, str]]:
    """Every command the door phase may send, in order, with what is only known on the box as a placeholder."""
    remote = _planner(cfg)
    uuid, commit = "<gpu-uuid>", "<HEAD>"
    steps = [("host_key", shlex.join(cmd_keyscan(cfg)))]
    steps.append(remote("lane_user (verify)", DOOR_WHOAMI))
    steps.append(remote("lane_user (verify)", DOOR_AUTHORIZED_KEYS_READ))
    steps.append(remote("shape (verify)", CMD_SHAPE))
    steps.append(remote("driver (verify)", CMD_DRIVER_QUERY))
    steps.append(remote("docker (verify)", DOOR_DOCKER_INFO))
    steps.append(remote("docker (verify)", DOOR_DOCKER_VERSION))
    steps.append(remote("stage_root (verify)", CMD_STAGE_ROOT_STAT))
    steps.append(remote("python (verify)", CMD_PYTHON_FIND))
    for image in cfg.images:
        steps.append(remote("images", door_image_id(image)))
        steps.append(
            remote(
                "images (only when absent)", DOOR_DOCKER_LOAD, cmd_docker_save(image)
            )
        )
        steps.append(remote("images", door_image_id(image)))
    steps.append(("tree", shlex.join(cmd_git_head())))
    steps.append(("tree", shlex.join(cmd_git_on_main(commit))))
    steps.append(remote("tree", DOOR_WORK_DIR))
    steps.append(remote("tree", cmd_tree_extract(commit), cmd_git_archive(commit)))
    steps.append(remote("device", cmd_prepare(cfg, commit, "<python>")))
    steps.append(remote("device", CMD_DEVICE_READ))
    steps.append(remote("class_check", cmd_class_out(cfg)))
    steps.append(remote("class_check", cmd_class_check(cfg, commit, uuid)))
    steps.append(remote("class_check", CMD_CLASS_OUTPUT_READ))
    steps.append(remote("class_check", CMD_CLASS_OPS_READ))
    steps.append(remote("class_check", cmd_class_clean(cfg)))
    steps.append(("door_link", shlex.join(cmd_door_link("<link>/docker", cfg))))
    steps.append(("watchdog_link", shlex.join(cmd_watchdog_link(cfg))))
    return steps


def _box_arguments(parser):
    """What both phases need to reach and recognise the box."""
    parser.add_argument("--ip", required=True, help="the box's IPv4 address")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument(
        "--host-key-fingerprint",
        required=True,
        help="the box's ed25519 host key, SHA256:... (from the provider's console)",
    )
    parser.add_argument(
        "--device-kind", required=True, help='e.g. "NVIDIA A100-SXM4-40GB"'
    )
    parser.add_argument("--driver-floor", default=DEFAULT_DRIVER_FLOOR)
    parser.add_argument("--docker-version", default=DEFAULT_DOCKER_VERSION)
    parser.add_argument("--containerd-version", default=DEFAULT_CONTAINERD_VERSION)
    parser.add_argument(
        "--door-ip", required=True, help="the only address the lane key may log in from"
    )
    parser.add_argument(
        "--lane-pubkey", required=True, help="the lane user's PUBLIC key file (.pub)"
    )
    parser.add_argument(
        "--other-door-ip",
        action="append",
        default=[],
        help="another door that uses this box (repeat): its restrict,from= lane-key line is kept; any other is dropped",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print every command; run none"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    phases = parser.add_subparsers(dest="phase", required=True)

    admin = phases.add_parser(
        "admin",
        help="Compute Ops, from their own machine, as the box's admin user with their own key",
    )
    _box_arguments(admin)
    admin.add_argument(
        "--user",
        default=DEFAULT_ADMIN_USER,
        help=f"the box's admin user (default {DEFAULT_ADMIN_USER}; never {LANE_USER})",
    )
    admin.add_argument(
        "--ssh-key", help="the admin's private key (stays on their machine)"
    )
    admin.add_argument("--driver-package", default=DEFAULT_DRIVER_PACKAGE)

    door = phases.add_parser(
        "door",
        help=f"on the door, as the door user, logging in to the box as {LANE_USER}",
    )
    _box_arguments(door)
    door.add_argument("--ssh-key", help="the lane's private key (stays on the door)")
    door.add_argument("--box-name", required=True)
    door.add_argument(
        "--provider",
        required=True,
        help=f"the box's provider; accepted: {', '.join(ACCEPTED_PROVIDERS)}",
    )
    door.add_argument(
        "--image",
        action="append",
        default=[],
        help="a worker image id to load (repeat)",
    )
    door.add_argument(
        "--jax-image",
        required=True,
        help="the pinned JAX GPU image id the class check runs in",
    )
    door.add_argument(
        "--graph-gpu-image-manifest",
        required=True,
        help="the receiver's graph GPU image manifest; its image id must equal --jax-image",
    )
    door.add_argument(
        "--class-record", required=True, help="the class's reference class-check JSON"
    )
    door.add_argument(
        "--class-ops-record",
        required=True,
        help="the class's reference graph GPU ops record",
    )
    door.add_argument(
        "--boxes-dir", required=True, help="where the door's box files live (0700)"
    )
    door.add_argument(
        "--ssh-boxes-dir",
        default=DEFAULT_SSH_BOXES_DIR,
        help="the door user's per-box ssh config files (0700), read by its ~/.ssh/config through one Include line",
    )
    door.add_argument(
        "--admin-summary",
        help="the admin phase's JSON (optional): it must agree with what the door reads",
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
                    "phase": args.phase,
                    "step": "arguments",
                    "reason": refusal.reason,
                    "detail": refusal.detail,
                }
            )
        )
        return 2
    if args.dry_run:
        for step, command in (plan_admin if cfg.phase == "admin" else plan_door)(cfg):
            print(f"[{step}] {command}")
        return 0
    if cfg.phase == "admin":
        outcome = run_admin(cfg, runner or subprocess_runner)
        print(json.dumps(outcome, indent=1, sort_keys=True))
        return 0 if outcome["admin"] == "PASS" else 1
    outcome = bring_up(cfg, runner or subprocess_runner)
    print(json.dumps(outcome, indent=1, sort_keys=True))
    return 0 if outcome["status"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
