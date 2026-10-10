"""GRAPHITE-LAUNCH-PREFLIGHT-01: one command before every Graphite launch.

    python -m carbon.agent_campaign.graphite.preflight \\
        --lane LANE.json --profile PROFILE.json --grant GRANT.json \\
        --root ROOT [--root ROOT ...] [--probe --key-file KEY --code-ref SHA]

Run it before every Graphite launch and after any restart. It checks, and
reports every failure at once (never the first only):

- **the lane:** the signer and Control Center answer over HTTP, and every
  tunnel port accepts a TCP connection (`--lane`, the executor's own file);
- **the keys:** every named key file exists, is a regular file, and is
  owner-only (mode 600). Paths only: no key is read or printed;
- **the revision:** the checkout's HEAD is the profile's `accepted_revision`;
- **the roots:** one distinct controller root per concurrent run, none
  inside another or inside the repository, and no more than the grant's
  `max_concurrency`;
- **the grant:** `permitted_runs x worst_case_run_cost + cleanup_allowance`
  is within `monetary_ceiling`;
- **a real pod probe** (`--probe` only, the one spend): one minimal pod on
  the same offer check and spec a launch uses, confirmed running, then
  terminated and verified gone from the provider's listing.

Each failure says what fixes it; those only the owner can do (a password, a
key copy, a permission change) are listed together under `owner_needs`. Exit
0 only when every check passes.

The lane file (`carbon.graphite.preflight-lane.v1`) names endpoints and key
paths on the executor's host; it is never committed.
"""

from __future__ import annotations

import argparse
import json
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.graphite.preflight.v1"
LANE_SCHEMA = "carbon.graphite.preflight-lane.v1"
OK, FAIL = "OK", "FAIL"
HTTP_TIMEOUT_S = 5
TCP_TIMEOUT_S = 3
#: How long the probe waits for its pod to run, and for it to be gone.
PROBE_RUNNING_S = 600
PROBE_GONE_S = 180


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    #: What fixes it, when it failed.
    fix: str = ""
    #: True when only the owner can do the fix.
    owner: bool = False


@dataclass
class Report:
    checks: list = field(default_factory=list)

    def add(self, *checks):
        self.checks.extend(checks)

    @property
    def ok(self):
        return all(c.status == OK for c in self.checks)

    def document(self):
        return {
            "schema": SCHEMA,
            "ok": self.ok,
            "checks": [asdict(c) for c in self.checks],
            "owner_needs": [
                {"check": c.name, "fix": c.fix}
                for c in self.checks
                if c.status != OK and c.owner
            ],
        }


# -- the lane ----------------------------------------------------------------------------
def _http(name, url, opener):
    try:
        with opener(url, timeout=HTTP_TIMEOUT_S) as response:
            code = getattr(response, "status", 200)
    except (urllib.error.URLError, OSError, ValueError) as failure:
        return Check(name, FAIL, f"no answer from {url}: {type(failure).__name__}")
    if not 200 <= code < 300:
        return Check(name, FAIL, f"{url} answered {code}")
    return Check(name, OK, url)


def _tcp(name, host, port, connect):
    try:
        connect((host, port), TCP_TIMEOUT_S).close()
    except OSError as failure:
        return Check(name, FAIL, f"{host}:{port} refused: {type(failure).__name__}")
    return Check(name, OK, f"{host}:{port}")


def check_lane(lane, *, opener=urllib.request.urlopen, connect=None):
    connect = connect or socket.create_connection
    if type(lane) is not dict or lane.get("schema") != LANE_SCHEMA:
        return [
            Check(
                "lane_file",
                FAIL,
                "not a " + LANE_SCHEMA + " document",
                fix="write the lane file (see the runbook)",
            )
        ]
    out = []
    signer = _http("lane_signer", (lane.get("signer") or {}).get("url", ""), opener)
    if signer.status != OK:
        signer.fix, signer.owner = (
            "start the lane signer (it needs the owner's wallet password)",
            True,
        )
    center = _http(
        "control_center", (lane.get("control_center") or {}).get("url", ""), opener
    )
    if center.status != OK:
        center.fix = "start the lane's Control Center"
    out += [signer, center]
    for tunnel in lane.get("tunnels") or []:
        check = _tcp(
            "tunnel:" + str(tunnel.get("name")),
            tunnel.get("host", "127.0.0.1"),
            int(tunnel.get("port", 0)),
            connect,
        )
        if check.status != OK:
            check.fix = "open the tunnel (restart its forward)"
        out.append(check)
    return out


# -- the keys ----------------------------------------------------------------------------
def check_keys(keys):
    out = []
    for key in keys or []:
        name, path = "key:" + str(key.get("name")), Path(str(key.get("path", "")))
        try:
            info = path.lstat()
        except OSError:
            out.append(
                Check(
                    name,
                    FAIL,
                    f"{path} is missing in this distro",
                    fix=f"copy the key to {path} on this host (mode 600)",
                    owner=True,
                )
            )
            continue
        if not stat.S_ISREG(info.st_mode):
            out.append(
                Check(
                    name,
                    FAIL,
                    f"{path} is not a regular file",
                    fix=f"replace {path} with the key file itself",
                    owner=True,
                )
            )
        elif info.st_mode & 0o077:
            out.append(
                Check(
                    name,
                    FAIL,
                    f"{path} is mode {oct(info.st_mode & 0o777)}",
                    fix=f"chmod 600 {path}",
                    owner=True,
                )
            )
        else:
            out.append(Check(name, OK, f"{path} (mode 600)"))
    return out


# -- the revision -------------------------------------------------------------------------
def head(repository=REPOSITORY, run=subprocess.run):
    out = run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return out if len(out) == 40 else None


def check_revision(profile, checkout):
    accepted = (profile or {}).get("accepted_revision")
    if type(accepted) is not str or len(accepted) != 40:
        return Check(
            "revision",
            FAIL,
            "the profile names no accepted_revision",
            fix="set the profile's accepted_revision",
        )
    if checkout != accepted:
        return Check(
            "revision",
            FAIL,
            f"checkout {checkout} is not the profile's accepted_revision {accepted}",
            fix=f"check out {accepted}, or re-accept the profile at {checkout}",
        )
    return Check("revision", OK, accepted)


# -- the roots and the grant ----------------------------------------------------------------
def check_roots(roots, grant, repository=REPOSITORY):
    resolved = [Path(r).expanduser().resolve() for r in roots]
    problems = []
    if not resolved:
        problems.append("no controller root named")
    if len(set(resolved)) != len(resolved):
        problems.append("two concurrent runs share a controller root")
    for a in resolved:
        if a == repository or repository in a.parents:
            problems.append(f"{a} is inside the repository")
        for b in resolved:
            if a != b and a in b.parents:
                problems.append(f"{b} is inside {a}")
    if grant is not None and len(resolved) > grant.max_concurrency:
        problems.append(
            f"{len(resolved)} concurrent runs exceed the grant's max_concurrency "
            f"{grant.max_concurrency}"
        )
    if problems:
        return Check(
            "controller_roots",
            FAIL,
            "; ".join(problems),
            fix="give every concurrent run its own fresh --root",
        )
    return Check("controller_roots", OK, f"{len(resolved)} distinct roots")


def check_grant(grant):
    needed = grant.worst_case_run_cost * grant.permitted_runs + grant.cleanup_allowance
    if needed > grant.monetary_ceiling:
        return Check(
            "grant_arithmetic",
            FAIL,
            f"{grant.permitted_runs} x {grant.worst_case_run_cost} + "
            f"{grant.cleanup_allowance} = {needed} exceeds {grant.monetary_ceiling}",
            fix="the grant needs the owner's re-approval",
            owner=True,
        )
    return Check(
        "grant_arithmetic",
        OK,
        f"{grant.permitted_runs} x {grant.worst_case_run_cost} + "
        f"{grant.cleanup_allowance} = {needed} <= {grant.monetary_ceiling}",
    )


# -- the pod lane: offer and balance floor ----------------------------------------------------
def check_offer(pods):
    """The live offer against the grant's pod rate ceiling (`pods.economics`
    carries it): a price above it is the owner's decision, before any run."""
    from scripts.dev.exam_design.runpod.operator_compute import ComputeError

    economics = pods.economics
    ceiling = economics["rate_ceiling_usd_per_hr"]
    try:
        [offer] = pods.adapter.offers([economics["gpu"]], gpu_count=1)
    except (ComputeError, ValueError) as failure:
        return Check(
            "pod_offer",
            FAIL,
            f"no offer: {type(failure).__name__}",
            fix="the pod lane cannot see the GPU it launches on",
        )
    if offer.usd_per_hr is None or not offer.stock_status:
        return Check(
            "pod_offer",
            FAIL,
            f"no {economics['gpu']} in stock now",
            fix="wait for stock, or the owner moves the lane's GPU",
            owner=True,
        )
    price = Decimal(str(offer.usd_per_hr))
    if price > ceiling:
        return Check(
            "pod_offer",
            FAIL,
            f"owner decision: offer {price}/h > grant ceiling {ceiling}/h",
            fix=f"the owner approves a pod rate ceiling of at least {price}/h "
            "in the grant (pod_rate_ceiling_usd_per_hr), or waits for a lower offer",
            owner=True,
        )
    return Check("pod_offer", OK, f"offer {price}/h <= grant ceiling {ceiling}/h")


def check_balance_floor(state_dir=None, name=None):
    """The operator's balance-floor file exists in this distro and names a
    floor; never prints it."""
    from scripts.dev.exam_design.runpod import pod_control

    path = Path(state_dir or pod_control.STATE_DIR) / (
        name or pod_control.OPERATOR_CONFIG
    )
    try:
        floor = json.loads(path.read_text()).get("balance_floor_usd")
    except (OSError, ValueError, AttributeError):
        floor = None
    if type(floor) not in (int, float) or floor < 0:
        return Check(
            "balance_floor",
            FAIL,
            f"{path} is missing in this distro or names no balance_floor_usd",
            fix=f"the owner writes balance_floor_usd to {path} on this host",
            owner=True,
        )
    return Check("balance_floor", OK, f"{path} names a floor")


# -- the pod probe ---------------------------------------------------------------------------
def probe_pod(pods, *, clock=time.time, sleep=time.sleep):
    """One minimal pod through `pods` (a `pods.RunPodPods`): the launch's
    own offer check, created, running, terminated and gone from the
    provider's listing. Returns a Check; the pod is always terminated."""
    from scripts.dev.exam_design.runpod.operator_compute import (
        ComputeError,
        PodSpec,
        ProvisionRequest,
        ResourceState,
    )

    economics = pods.economics
    offered = check_offer(pods)
    if offered.status != OK:
        offered.name = "pod_probe"
        return offered
    intent = f"preflight-probe-{int(clock())}"
    spec = PodSpec(
        image=economics["image"],
        gpu_type_id=economics["gpu"],
        gpu_count=1,
        cloud_type="SECURE",
        container_disk_gb=economics["disk_gb"],
        ports=(),
        env={},
        max_rate_usd_per_hr=float(economics["rate_ceiling_usd_per_hr"]),
        storage_usd_per_gb_month=float(economics["disk_usd_per_gb_month"]),
        start_command=("/bin/sh", "-c", "sleep 900"),
        allowed_cuda_versions=tuple(pods.cuda_versions),
    )
    started = clock()
    try:
        resource = pods.service.provision(
            ProvisionRequest(
                tenant="graphite",
                miner="graphite",
                campaign_id=pods.CAMPAIGN,
                intent_id=intent,
                spec=spec,
                deadline_at=started + PROBE_RUNNING_S,
            )
        )
    except ComputeError as failure:
        return Check(
            "pod_probe",
            FAIL,
            f"launch refused: {failure.failed}",
            fix="a real launch would be refused the same way",
        )
    running = False
    try:
        while clock() - started < PROBE_RUNNING_S:
            states = [r.state for r in pods.service.refresh(pods.CAMPAIGN, intent)]
            if ResourceState.RUNNING in states:
                running = True
                break
            sleep(10)
    finally:
        pods.service.terminate(pods.CAMPAIGN, intent, resource.resource_id)
    gone, waited = False, clock()
    while clock() - waited < PROBE_GONE_S:
        listed = {r.resource_id for r in pods.adapter.list_resources()}
        if resource.resource_id not in listed:
            gone = True
            break
        sleep(10)
    if not gone:
        return Check(
            "pod_probe",
            FAIL,
            "the probe pod is still listed after terminate",
            fix="terminate it by hand and check the account",
            owner=True,
        )
    if not running:
        return Check(
            "pod_probe",
            FAIL,
            "the probe pod never reached running",
            fix="the image or GPU lane does not start; nothing ran",
        )
    return Check(
        "pod_probe",
        OK,
        f"created, running after {int(clock() - started)} s, terminated and gone",
    )


# -- the command -------------------------------------------------------------------------
def run(
    args, *, opener=urllib.request.urlopen, connect=None, checkout=None, make_pods=None
):
    from ..grant import SpendingGrant

    report = Report()
    lane = json.loads(Path(args.lane).read_text())
    report.add(*check_lane(lane, opener=opener, connect=connect))
    keys = list(lane.get("keys") or [])
    if args.key_file:
        keys.append({"name": "runpod", "path": args.key_file})
    report.add(*check_keys(keys))
    from carbon.development_session.private_records import private_json

    checkout = checkout or head()
    report.add(check_revision(private_json(Path(args.profile)), checkout))
    grant = SpendingGrant.from_document(json.loads(Path(args.grant).read_text()))
    report.add(check_roots(args.root, grant), check_grant(grant))
    if not args.key_file:
        return report
    # A pod lane: the balance floor and the live offer, at no cost, then the
    # probe pod when asked (GRANT-POD-CEILING-01).
    report.add(check_balance_floor())
    if not report.ok:
        report.add(Check("pod_offer", FAIL, "not read: fix the checks above first"))
        if args.probe:
            report.add(Check("pod_probe", FAIL, "not run: fix the checks above first"))
        return report
    from . import pods as podlib

    pods = (make_pods or podlib.RunPodPods)(
        root=Path(args.root[0]) / "preflight-probe",
        key_file=args.key_file,
        code_ref=args.code_ref or checkout,
        rate_ceiling=grant.pod_rate_ceiling_usd_per_hr,
    )
    report.add(check_offer(pods))
    if args.probe:
        if report.ok:
            report.add(probe_pod(pods))
        else:
            report.add(Check("pod_probe", FAIL, "not run: the offer check failed"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="graphite.preflight")
    parser.add_argument("--lane", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--grant", required=True)
    parser.add_argument(
        "--root", action="append", required=True, help="one per concurrent run"
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="create, check and terminate one real pod (spends)",
    )
    parser.add_argument(
        "--key-file",
        help="the RunPod key's path: checks the balance floor and the live offer "
        "against the grant's pod rate ceiling (no spend), and enables --probe",
    )
    parser.add_argument("--code-ref", help="the pushed commit (for --probe)")
    args = parser.parse_args(argv)
    if args.probe and not (args.key_file and args.code_ref):
        parser.error("--probe needs --key-file and --code-ref")
    report = run(args)
    print(json.dumps(report.document(), indent=1))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
