"""PUBLIC-DEV-DECISIONS-01 launcher, run by the OWNER on the operator host.

    python -m scripts.dev.battery.public_dev_launch launch --ref SHA
    python -m scripts.dev.battery.public_dev_launch list | weekly | status | results
    python -m scripts.dev.battery.public_dev_launch settle USD

OWNER-PUBLIC-DEV-DECISIONS-GRANT-01 (USD 16) binds the spend. No agent holds the
RunPod key: it is read from KEY_FILE (default `~/.runpod/api_key`) and never
printed.

Launch, in this order, refusing at any step:
1. **Claim** the run in OWNER-TESTNET-WEEKLY-BUDGET-01's host ledger
   (`carbon.agent_campaign.grant_runs`) at the grant's cap. Nothing is created
   unless the ledger accepts.
2. **Build** the create body: the bootstrap, the shipped files'
   sha256 manifest at REF (`ship-files.json`), the CA roots the truth image
   lacks, a fresh probe token and PROBE_DEADLINE = now + HOURS - 6 min.
3. **Check the hard stop** (`check_deadline`). PROBE_DEADLINE must be in the
   body, in the future, within HOURS, and its worst case at the approved rate
   within the cap.
4. **Create** the pod. If no pod id comes back, the reservation is released
   and the raw response kept.
5. **Check the rate.** Any rate other than the approved USD 1.76/h deletes
   the pod at once.

The pod's bootstrap terminates it at PROBE_DEADLINE with RunPod's pod-scoped
key, independently of the owner. `settle` records the actual charge in place
of the reservation.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GRANT_ID = "OWNER-PUBLIC-DEV-DECISIONS-GRANT-01"
CAP_USD, RATE_USD_H = Decimal("16.00"), Decimal("1.76")
HOURS, DEADLINE_MARGIN_S, FETCH_MARGIN_S = 8.75, 360, 1500
QUESTIONS, WORKERS = 240, 30
#: a tag beside the digest: RunPod did not start a pod named by digest alone (pod_control)
IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-determinism-study:d0c19830d095"
    "@sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
)
SHIP_FILE = "docs/development/evidence/public-dev-decisions-01/ship-files.json"
BOOTSTRAP = "scripts/dev/exam_design/runpod/bootstrap.py"
OVERLAY_LOCK = "scripts/dev/exam_design/locks/battery-overlay.lock.json"
SETUP = "nproc; grep -m1 'model name' /proc/cpuinfo; free -g | head -2"
STORE = hashlib.sha256(b"PUBLIC-DEV-DECISIONS-01").hexdigest()[:32]
RUN_KEY = "public-dev-decisions-pod"
#: attempts, each its own ledger key; a failed create releases its reservation, and the
#: launcher refuses a second pod once one exists (pod_id), so at most one pod runs
ATTEMPTS = 3
API = "https://rest.runpod.io/v1"


class Refused(Exception):
    pass


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    ).stdout


def ship_paths(repo, ref):
    paths = json.loads(_git(repo, "show", f"{ref}:{SHIP_FILE}"))
    tracked = set(_git(repo, "ls-tree", "-r", "--name-only", ref).decode().split())
    missing = sorted(set(paths) - tracked)
    if missing:
        raise Refused(f"shipped files not tracked at {ref}: {missing[:3]}")
    return sorted(set(paths))


def ca_bundle_gz_b64():
    """pod_control's CA roots from this host's store."""
    from scripts.dev.exam_design.runpod import pod_control

    pem = "".join(
        Path(f"/etc/ssl/certs/{n}.pem").read_text()
        for n in pod_control.CA_ROOTS
        if os.path.exists(f"/etc/ssl/certs/{n}.pem")
    )
    if not pem:
        raise Refused("no CA roots in /etc/ssl/certs")
    return base64.b64encode(gzip.compress(pem.encode(), 9)).decode()


def build_body(repo, ref, *, now, token, ca, hours=HOURS):
    manifest = {
        p: hashlib.sha256(_git(repo, "show", f"{ref}:{p}")).hexdigest()
        for p in ship_paths(repo, ref)
    }
    text = json.dumps(manifest, separators=(",", ":"), sort_keys=True)
    env = {
        "PROBE_TOKEN": token,
        "PROBE_DEADLINE": str(int(now + hours * 3600 - DEADLINE_MARGIN_S)),
        "PROBE_CA_GZ_B64": ca,
        "CODE_REF": ref,
        "CODE_MANIFEST_GZ_B64": base64.b64encode(
            gzip.compress(text.encode(), 9, mtime=0)
        ).decode(),
        "OVERLAYS": json.dumps({"battery": OVERLAY_LOCK}),
        "PHASE_MODULE": "scripts.dev.battery.public_dev_pod_phase",
        "PHASE": "solve",
        "PDD_WORKERS": str(WORKERS),
        "PDD_QUESTIONS": str(QUESTIONS),
        "PDD_SOLVE_BUDGET_S": str(
            int(hours * 3600 - DEADLINE_MARGIN_S - FETCH_MARGIN_S)
        ),
        "CARBON_BOOT": _git(repo, "show", f"{ref}:{BOOTSTRAP}").decode(),
    }
    return {
        "name": "public-dev-decisions-01", "imageName": IMAGE, "computeType": "CPU", "cloudType": "SECURE",
        "interruptible": False, "cpuFlavorIds": ["cpu5m", "cpu3m"], "cpuFlavorPriority": "custom",
        "vcpuCount": 32, "containerDiskInGb": 40, "volumeInGb": 0, "ports": ["8000/http"],
        "dockerEntrypoint": ["bash", "-c"],
        "dockerStartCmd": ["mkdir -p /tmp/out; { " + SETUP + " ; } > /tmp/out/setup.log 2>&1"
                           " || echo 'SETUP FAILED' >> /tmp/out/setup.log;"
                           ' exec python3 -I -c "$CARBON_BOOT"'],
        "env": env,
    }  # fmt: skip


def check_deadline(body, *, now, hours=HOURS, rate=RATE_USD_H, cap=CAP_USD):
    """The hard stop is in force: returns the worst-case charge, or refuses."""
    raw = (body.get("env") or {}).get("PROBE_DEADLINE")
    try:
        deadline = int(raw)
    except (TypeError, ValueError):
        raise Refused("PROBE_DEADLINE is missing from the create body") from None
    left_h = (deadline - now) / 3600
    if not 0 < left_h <= hours:
        raise Refused(
            f"PROBE_DEADLINE is {left_h:.2f} h away, not within (0, {hours}] h"
        )
    worst = (Decimal(str(left_h)) * rate).quantize(Decimal("0.01"))
    if worst > cap:
        raise Refused(f"worst case USD {worst} exceeds the USD {cap} cap")
    return worst


class Ledger:
    """OWNER-TESTNET-WEEKLY-BUDGET-01's host ledger, for this grant's one run."""

    def __init__(self, key, reserve=CAP_USD):
        from carbon.agent_campaign import grant_runs

        self.g, self.key = grant_runs, key
        self.grant = types.SimpleNamespace(
            grant_id=GRANT_ID,
            currency="USD",
            worst_case_run_cost=str(reserve),
            permitted_runs=ATTEMPTS,
        )

    def claim(self):
        return self.g.claim(self.grant, STORE, self.key)

    def settle(self, usd):
        return self.g.settle(self.grant, STORE, self.key, str(usd))

    def release(self):
        return self.settle("0")

    def weekly(self):
        return self.g.weekly_line(self.g.weekly_report())


def http(method, path, body=None, key_file=None):
    key = (
        Path(key_file or os.environ.get("KEY_FILE", "~/.runpod/api_key"))
        .expanduser()
        .read_text()
        .strip()
    )
    request = urllib.request.Request(
        API + path, data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "User-Agent": "carbon-public-dev/1"},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, response.read().decode(errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors="replace")


def launch(
    repo, ref, out, *, request=http, ledger=None, clock=time.time, ca=None, token=None
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = f"{RUN_KEY}-{int(clock())}"
    (out / "ledger_key").write_text(key + "\n")
    ledger = ledger or Ledger(key)
    ledger.claim()  # refuses (weekly_budget_reached, run_limit_reached) before anything exists
    try:
        now = clock()
        body = build_body(repo, ref, now=now, token=token or secrets.token_urlsafe(24),
                          ca=ca if ca is not None else ca_bundle_gz_b64())  # fmt: skip
        worst = check_deadline(body, now=clock())
    except Exception:
        ledger.release()
        raise
    (out / "body.json").write_text(json.dumps(body, indent=1) + "\n")
    os.chmod(out / "body.json", 0o600)
    (out / "token").write_text(body["env"]["PROBE_TOKEN"] + "\n")
    os.chmod(out / "token", 0o600)
    code, raw = request("POST", "/pods", body)
    (out / "create-response.txt").write_text(f"HTTP {code}\n{raw}\n")
    try:
        pod = json.loads(raw)
    except ValueError:
        pod = {}
    pod_id = pod.get("id") if isinstance(pod, dict) else None
    if not pod_id:
        ledger.release()
        raise Refused(f"create failed: HTTP {code}: {raw[:300]}")
    (out / "pod_id").write_text(pod_id + "\n")
    rate = Decimal(str(pod.get("costPerHr") or "0"))
    if not Decimal(0) < rate <= RATE_USD_H:
        request("DELETE", f"/pods/{pod_id}")
        ledger.settle("0.05")  # at most a minute at a mistaken rate
        raise Refused(
            f"pod {pod_id} came up at USD {rate}/h, not the approved {RATE_USD_H}/h: deleted"
        )
    return {"pod_id": pod_id, "rate_usd_h": str(rate), "worst_case_usd": str(worst),
            "deadline_epoch": int(body["env"]["PROBE_DEADLINE"])}  # fmt: skip


def _probe(out, path):
    pod_id = (Path(out) / "pod_id").read_text().strip()
    token = (Path(out) / "token").read_text().strip()
    request = urllib.request.Request(
        f"https://{pod_id}-8000.proxy.runpod.net{path}",
        headers={"X-Probe-Token": token},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return response.read()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="public_dev_launch")
    parser.add_argument(
        "command", choices=("launch", "list", "weekly", "settle", "status", "results")
    )
    parser.add_argument("value", nargs="?")
    parser.add_argument("--ref")
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--out", default="/home/carbon/runs/pdd/spec")
    args = parser.parse_args(argv)
    if args.command == "launch":
        if (Path(args.out) / "pod_id").exists():
            raise SystemExit(
                "refused: a pod was already created from this spec directory; settle it first"
            )
        print(json.dumps(launch(args.repo, args.ref, args.out)))
    elif args.command == "list":
        code, raw = http("GET", "/pods")
        for pod in json.loads(raw) if code == 200 else []:
            print(
                pod.get("id"),
                pod.get("name"),
                pod.get("desiredStatus"),
                pod.get("costPerHr"),
            )
    elif args.command == "weekly":
        print(Ledger("-").weekly())
    elif args.command == "settle":
        ledger = Ledger((Path(args.out) / "ledger_key").read_text().strip())
        print(ledger.settle(Decimal(args.value)), ledger.weekly())
    elif args.command == "status":
        print(_probe(args.out, "/status").decode())
    else:
        data = _probe(args.out, "/out.tar.gz")
        target = Path(args.out).parent / "out.tar.gz"
        target.write_bytes(data)
        print(target, len(data), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
