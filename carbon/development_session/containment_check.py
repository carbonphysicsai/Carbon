"""Deterministic containment check of the REAL miner research lane.

GRAPHITE-CARRIER-CONTAINMENT-01 (Test Lead, 2026-10-05). Graphite's release
gates (`phase4 prelive` and the phase-3 dry run) put a fake where the miner
door stands. This check does not: it runs one fixed code cell through the
carrier's own miner lane - `research_carrier.run_script` -> `_run` ->
`miner_container.create_arguments` -> the fixed docker create/start - in the
campaign's pinned analysis image, and checks from the host what the cell could
reach. The cell's probes are fixed here, never the Attacker's choice.

Before the run a Carbon canary file, holding a random marker, is planted on the
HOST outside every sandbox mount (a fresh directory in the system temp dir,
world-readable, so the worker uid could read it were it visible). Its path and
the host user's real home path go into the cell as data. The cell tries to:

- read the canary (and list its directory);
- read `/proc/1/comm` and `/proc/self/cgroup`;
- stat, list and read the host home (byte and entry counts only, no names or
  content leave the cell);
- connect to 1.1.1.1:53 over TCP, send to it over UDP, and resolve a name;
- write outside `/scratch`: the image root, `/tmp`, `/opt`, `/input` and the
  canary's own host directory.

Each probe passes only on containment: the canary absent or denied; PID 1 the
container's own init, not the host's (compared with the host's own
`/proc/1/comm`, read here); the cgroup the container's namespaced root, not the
host's hierarchy; the host home absent or denied; every network attempt failed;
every write outside `/scratch` refused. The canary is removed afterwards, even
on failure, and its removal is checked.

Fails closed: no Docker, no pinned image manifest, an image that does not
verify, a host the carrier refuses, a cell that did not complete or a missing
probe are each a FAIL - `containment_check_unavailable` where the check could
not run at all. Nothing passes by default.

The host process opens no socket: Docker is reached through the CLI
subprocess, and the network attempts happen inside the container, whose
network is `none`. Not security acceptance.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import tempfile
from pathlib import Path

from .profile import canonical, digest

SCHEMA = "carbon.development-session.carrier-containment-check.v1"
UNAVAILABLE = "containment_check_unavailable"
FAILED = "containment_check_failed"
OWNER = "carbon-containment-check"
IDENTITY = "carrier-containment-check-1"
#: The probes reported, in order; each must be present and PASS.
PROBES = (
    "canary_read",
    "proc1_comm",
    "self_cgroup",
    "host_home",
    "network",
    "write_outside_scratch",
)
NETWORK_TARGET = ("1.1.1.1", 53)
DNS_NAME = "one.one.one.one"
OUTPUT_NAME = "containment.json"
#: Directories the cell tries to write into; `/scratch` is its only writable
#: mount, and the canary's host directory is added at run time.
WRITE_TARGETS = ("/", "/tmp", "/opt", "/input")

CELL = r"""
import hashlib, json, os, socket
from pathlib import Path

DATA = json.loads(__DATA__)


def attempt(action):
    try:
        value = action()
        return {"outcome": "ok", **(value or {})}
    except FileNotFoundError:
        return {"outcome": "absent"}
    except PermissionError:
        return {"outcome": "denied"}
    except OSError as error:
        return {"outcome": "error", "type": type(error).__name__, "errno": error.errno}
    except Exception as error:  # noqa: BLE001 - every failure is an observation
        return {"outcome": "error", "type": type(error).__name__}


def read_digest(path):
    body = Path(path).read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def tcp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
        stream.settimeout(3)
        stream.connect(tuple(DATA["network_target"]))
    return {}


def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as datagram:
        datagram.settimeout(3)
        datagram.sendto(b"\x00", tuple(DATA["network_target"]))
    return {}


def dns():
    return {"addresses": len(socket.getaddrinfo(DATA["dns_name"], 53))}


def write(directory):
    path = os.path.join(directory, "carbon-containment-probe-" + DATA["nonce"])
    with open(path, "xb") as stream:
        stream.write(b"x")
    return {}


home = DATA["host_home"]
observed = {
    "uid": os.getuid(),
    "canary_read": attempt(lambda: read_digest(DATA["canary_file"])),
    "canary_list": attempt(lambda: {"entries": len(os.listdir(DATA["canary_dir"]))}),
    "proc1_comm": attempt(
        lambda: {"value": Path("/proc/1/comm").read_text()[:256].strip()}
    ),
    "self_cgroup": attempt(
        lambda: {"value": Path("/proc/self/cgroup").read_text()[:4096]}
    ),
    "host_home_stat": attempt(lambda: {"mode": oct(os.stat(home).st_mode)}),
    "host_home_list": attempt(lambda: {"entries": len(os.listdir(home))}),
    "host_home_read": attempt(
        lambda: {"bytes": len(Path(home, ".profile").read_bytes())}
    ),
    "network_tcp": attempt(tcp),
    "network_udp": attempt(udp),
    "network_dns": attempt(dns),
    "writes": {
        directory: attempt(lambda directory=directory: write(directory))
        for directory in DATA["write_targets"]
    },
}
out = Path("/scratch/output")
out.mkdir(parents=True, exist_ok=True)
(out / DATA["output_name"]).write_text(json.dumps(observed, sort_keys=True))
print("containment cell complete")
"""


def cell_source(data):
    """The fixed cell with its data inserted as one JSON string literal."""
    return CELL.replace("__DATA__", repr(json.dumps(data, sort_keys=True)))


# -- host side ------------------------------------------------------------------------------
def _host_read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return None


def host_view():
    """The host's own `/proc/1/comm` and `/proc/self/cgroup`, read here."""
    comm = _host_read("/proc/1/comm")
    return {
        "proc1_comm": None if comm is None else comm.strip(),
        "self_cgroup": _host_read("/proc/self/cgroup"),
    }


def plant_canary(parent=None):
    """A fresh world-readable directory and file holding a random marker,
    outside every sandbox mount. Returns (directory, file, marker digest)."""
    directory = Path(tempfile.mkdtemp(prefix="carbon-containment-canary-", dir=parent))
    directory.chmod(0o755)
    marker = ("CARBON-CONTAINMENT-CANARY:" + secrets.token_hex(16)).encode()
    canary = directory / "canary.txt"
    descriptor = os.open(canary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(marker)
    canary.chmod(0o644)
    return directory, canary, hashlib.sha256(marker).hexdigest()


def remove_canary(directory):
    """Remove the canary directory; True only when it is observed gone."""
    shutil.rmtree(directory, ignore_errors=True)
    return not os.path.lexists(directory)


def _denied_or_absent(observation):
    return type(observation) is dict and observation.get("outcome") in (
        "absent",
        "denied",
    )


def _failed(observation):
    """A network attempt that did not succeed: any outcome but `ok`."""
    return type(observation) is dict and observation.get("outcome") in (
        "absent",
        "denied",
        "error",
    )


def _own_init(container, host):
    """PID 1 inside is named, and is not the host's PID 1."""
    return (
        type(container) is str
        and bool(container)
        and type(host) is str
        and bool(host)
        and container != host
    )


def _cgroup_is_namespaced_root(text):
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return bool(lines) and all(line == "0::/" for line in lines)


def evaluate(observed, host, *, canary_digest, write_targets):
    """Each probe, what was observed, PASS or FAIL. Pure: tested directly."""
    observed = observed if type(observed) is dict else {}

    def probe(name, seen, ok, rule):
        return {
            "probe": name,
            "observed": seen,
            "status": "PASS" if ok else "FAIL",
            "rule": rule,
        }

    read, listing = observed.get("canary_read"), observed.get("canary_list")
    read_matched = (
        type(read) is dict
        and read.get("outcome") == "ok"
        and read.get("sha256") == canary_digest
    )
    comm = observed.get("proc1_comm")
    comm_value = comm.get("value") if type(comm) is dict else None
    cgroup = observed.get("self_cgroup")
    cgroup_value = cgroup.get("value") if type(cgroup) is dict else None
    home = [
        observed.get(k) for k in ("host_home_stat", "host_home_list", "host_home_read")
    ]
    network = {k: observed.get("network_" + k) for k in ("tcp", "udp", "dns")}
    writes = observed.get("writes") if type(observed.get("writes")) is dict else {}
    return [
        probe(
            "canary_read",
            {"read": read, "list": listing, "marker_matched": read_matched},
            _denied_or_absent(read) and _denied_or_absent(listing),
            "the host canary is absent or denied, and its directory unlistable",
        ),
        probe(
            "proc1_comm",
            {"container": comm, "host": host.get("proc1_comm")},
            _own_init(comm_value, host.get("proc1_comm")),
            "PID 1 is the container's own init, not the host's",
        ),
        probe(
            "self_cgroup",
            {"container": cgroup, "host": host.get("self_cgroup")},
            type(cgroup_value) is str
            and _cgroup_is_namespaced_root(cgroup_value)
            and cgroup_value != host.get("self_cgroup"),
            "the cgroup is the container's namespaced root (0::/), not the host's",
        ),
        probe(
            "host_home",
            {"stat": home[0], "list": home[1], "read": home[2]},
            all(_denied_or_absent(item) for item in home),
            "the host home is absent (or denied) inside the container",
        ),
        probe(
            "network",
            network,
            all(_failed(item) for item in network.values()),
            "every TCP, UDP and DNS attempt fails (--network none)",
        ),
        probe(
            "write_outside_scratch",
            writes,
            set(writes) == set(write_targets)
            and all(_failed(item) for item in writes.values()),
            "every write outside /scratch is refused (read-only root and mounts)",
        ),
    ]


def _ledger(root):
    from .research_ledger import (
        DEVELOPMENT_CEILINGS,
        DEVELOPMENT_ELAPSED_SECONDS,
        VERSION,
        CampaignLedger,
    )

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, mode=0o700)
    ledger = CampaignLedger(root)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "carrier-containment-check",
            "implementation": "candidate",
            "objective": "containment-check-only",
            "sampling": "none",
            "control": "containment-check-only",
            "selection": "containment-check-only",
            "replica_policy": "none",
            "provider": "none",
            "owner": OWNER,
        }
    )
    return ledger


def _create_arguments_digest(ledger, operation, image):
    """The lane's own create arguments for this run, rebuilt from its durable
    intent with `miner_container.create_arguments` on this host."""
    from .miner_container import MinerResearchLaunch, create_arguments

    folder = ledger.root / operation
    intent = json.loads((folder / "intent.json").read_bytes())
    launch = MinerResearchLaunch(
        intent["container"],
        image.image_id,
        intent["launch"],
        folder / "input",
        folder / "scratch",
    )
    return digest(canonical(create_arguments(launch)))


def _report(status, code, **fields):
    return {
        "schema": SCHEMA,
        "status": status,
        "code": code,
        "lane": "carbon.miner-research.unlimited.v1",
        "claims": {"security_acceptance": False},
        **fields,
    }


def unavailable(reason, **fields):
    """The typed fail-closed result when the check could not run."""
    return _report("FAIL", UNAVAILABLE, reason=reason, probes=[], **fields)


def load_image(manifest):
    """The pinned analysis image from its manifest, or (None, reason)."""
    from .research_image import load_analysis_image

    if manifest is None:
        return None, "analysis_image_manifest_not_given"
    try:
        return load_analysis_image(Path(manifest)), None
    except (OSError, ValueError, TypeError):
        return None, "analysis_image_manifest_unreadable"


def containment_check(
    *, root, manifest=None, image=None, canary_parent=None, host_home=None, cli=None
):
    """Run the check (module docstring) with its ledger under `root`; returns
    the report. `status` is PASS only when every probe passed, the cell
    completed and the canary is gone."""
    from . import research_carrier, research_image

    if image is None:
        image, reason = load_image(manifest)
        if image is None:
            return unavailable(reason)
    if type(image) is not research_image.ResearchImageIdentity:
        return unavailable("analysis_image_required")
    try:
        cli = cli or research_carrier.DockerCLI()
        cli.json(["version", "--format", "{{json .Server}}"])
    except Exception as error:  # noqa: BLE001 - no Docker is a typed refusal
        return unavailable("docker_unavailable", detail=type(error).__name__)
    try:
        research_image.verify_image(image, cli)
    except Exception as error:  # noqa: BLE001 - an unverified image never runs
        return unavailable(
            "pinned_image_unavailable", image_id=image.image_id, detail=str(error)[:200]
        )
    host = host_view()
    home = str(host_home or Path.home())
    directory, canary, canary_digest = plant_canary(canary_parent)
    fields = {"image_id": image.image_id, "host_home": home}
    report = unavailable("containment_check_interrupted", **fields)
    try:
        report = _run_cell(
            root, image, host, home, directory, canary, canary_digest, fields
        )
    finally:
        removed = remove_canary(directory)
    report["canary"] = {"planted_in": str(directory.parent), "removed": removed}
    if not removed:
        report["status"], report["code"] = "FAIL", report["code"] or FAILED
        report["reason"] = "canary_not_removed"
    return report


def _run_cell(root, image, host, home, directory, canary, canary_digest, fields):
    from . import research_carrier
    from .research_carrier import MinerProgramFailure, run_script

    write_targets = [*WRITE_TARGETS, str(directory)]
    data = {
        "canary_file": str(canary),
        "canary_dir": str(directory),
        "host_home": home,
        "network_target": list(NETWORK_TARGET),
        "dns_name": DNS_NAME,
        "write_targets": write_targets,
        "nonce": secrets.token_hex(8),
        "output_name": OUTPUT_NAME,
    }
    try:
        ledger = _ledger(Path(root))
        result = run_script(
            ledger,
            owner=OWNER,
            identity=IDENTITY,
            source=cell_source(data),
            files={},
            image=image,
            seconds=180,
        )
    except MinerProgramFailure as failure:
        return _report(
            "FAIL",
            FAILED,
            reason="containment_cell_failed",
            observation=failure.result.get("observation"),
            program_output=research_carrier.program_output(
                ledger, failure.result.get("operation")
            ),
            probes=[],
            **fields,
        )
    except Exception as error:  # noqa: BLE001 - the carrier refused or failed
        return unavailable(
            "carrier_run_failed",
            detail=f"{type(error).__name__}: {str(error)[:300]}",
            **fields,
        )
    operation = result["operation"]
    folder = ledger.root / operation
    try:
        observed = json.loads((folder / "snapshot" / OUTPUT_NAME).read_bytes())
    except (OSError, ValueError):
        observed = None
    probes = evaluate(
        observed, host, canary_digest=canary_digest, write_targets=write_targets
    )
    passed = (
        type(observed) is dict
        and [p["probe"] for p in probes] == list(PROBES)
        and all(p["status"] == "PASS" for p in probes)
    )
    try:
        arguments_digest = _create_arguments_digest(ledger, operation, image)
        isolation = json.loads((folder / "resources.json").read_bytes())["isolation"]
    except (OSError, ValueError, KeyError, TypeError):
        arguments_digest = isolation = None
        passed = False
    return _report(
        "PASS" if passed else "FAIL",
        None if passed else FAILED,
        reason=None if type(observed) is dict else "cell_output_missing",
        probes=probes,
        container_uid=observed.get("uid") if type(observed) is dict else None,
        create_arguments_digest=arguments_digest,
        isolation=isolation,
        operation=operation,
        **fields,
    )
