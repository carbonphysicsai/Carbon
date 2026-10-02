"""Operator commands for exam-design pods: bounded and accounted A40 pods.

    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] start [--cap-usd X]
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] status
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] dispatch PHASE --plan PATH --minutes N \
        [--ref SHA] [--ship carbon ...] [--max-pods N]
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] poll [--pod ID]
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] fetch DEST [--pod ID] [--tar]
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] terminate [--pod ID]
    python -m scripts.dev.exam_design.runpod.pod_control [--campaign C] reconcile

Campaigns (``CAMPAIGNS``) each have their own ledger, local state and hard
limits. ``exam-design`` (the default) is the 2026-09-24 campaign: one pod at a
time under its USD 20 ceiling. ``ev4`` is EV4 and the Problem-C optimizer
(owner approval 2026-10-01): up to 3 pods in parallel under a USD 15 cap.

The API key is read from ``~/.runpod/api_key`` (mode 600) and never printed,
logged or placed on a command line. Each active pod id is recorded locally the
moment the create call returns, and every lifecycle event is appended to the
campaign ledger in the repository.

Refusals, all before any spend: the campaign's pod allowance (``--max-pods``,
never above the campaign's hard limit) is used up, counting both recorded and
live pods; the A40 Secure rate is above ``MAX_RATE``; the account balance
would fall below ``BALANCE_FLOOR``; the dispatch ref is not on a remote branch
(the pod fetches code from GitHub at that commit); or the ledger's committed
spend (every live pod counted to its full deadline) plus this pod's
full-deadline cost plus the cleanup reserve would exceed the campaign cap.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
STATE_DIR = os.path.expanduser("~/.runpod")
#: Per-campaign evidence directory, local state, hard pod limit and ceiling.
CAMPAIGNS = {
    "exam-design": {
        "evidence": "docs/development/evidence/exam-design-2026-09-24",
        "active": "exam_design_active_pod",  # one pod: a single file
        "token": "exam_design_token",
        "max_pods": 1,
        "ceiling_usd": 20.0,
        "name": "carbon-exam-design",
    },
    "ev4": {
        "evidence": "docs/development/evidence/ev4-2026-10-01",
        "active": "ev4_active_pods",  # a directory: one file per pod (its token)
        "token": None,
        "max_pods": 3,
        "ceiling_usd": 15.0,
        "name": "carbon-ev4",
    },
}
CAMPAIGN = "exam-design"
EVID = os.path.join(REPO, CAMPAIGNS[CAMPAIGN]["evidence"])
LEDGER = os.path.join(EVID, "accounting/ledger.jsonl")
ACTIVE = os.path.join(STATE_DIR, CAMPAIGNS[CAMPAIGN]["active"])
TOKEN_FILE = os.path.join(STATE_DIR, CAMPAIGNS[CAMPAIGN]["token"])
#: A manifest larger than this travels gzipped (CODE_MANIFEST_GZ_B64).
MANIFEST_GZ_ABOVE = 16_000


def use_campaign(name: str) -> None:
    """Point the ledger, local state and limits at one campaign."""
    global CAMPAIGN, EVID, LEDGER, ACTIVE, TOKEN_FILE, CEILING_USD
    spec = CAMPAIGNS[name]
    CAMPAIGN = name
    EVID = os.path.join(REPO, spec["evidence"])
    LEDGER = os.path.join(EVID, "accounting/ledger.jsonl")
    ACTIVE = os.path.join(STATE_DIR, spec["active"])
    TOKEN_FILE = os.path.join(STATE_DIR, spec["token"]) if spec["token"] else None
    CEILING_USD = spec["ceiling_usd"]


def _multi() -> bool:
    return CAMPAIGNS[CAMPAIGN]["token"] is None


def active_pods() -> list[str]:
    """Pods this campaign recorded as active (created, not verified gone)."""
    if _multi():
        return sorted(os.listdir(ACTIVE)) if os.path.isdir(ACTIVE) else []
    return [Path(ACTIVE).read_text().strip()] if os.path.exists(ACTIVE) else []


def _write_private(path: str, text: str) -> None:
    old = os.umask(0o077)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Path(path).write_text(text)
    finally:
        os.umask(old)


def record_active(pod_id: str, token: str) -> None:
    if _multi():
        _write_private(os.path.join(ACTIVE, pod_id), token)
    else:
        _write_private(TOKEN_FILE, token)
        Path(ACTIVE).write_text(pod_id)


def clear_active(pod_id: str) -> None:
    if _multi():
        path = os.path.join(ACTIVE, pod_id)
        if os.path.exists(path):
            os.remove(path)
    elif os.path.exists(ACTIVE) and Path(ACTIVE).read_text().strip() == pod_id:
        os.remove(ACTIVE)


def token_for(pod_id: str) -> str:
    if _multi():
        return Path(os.path.join(ACTIVE, pod_id)).read_text().strip()
    return Path(TOKEN_FILE).read_text().strip()


def pick_pod(pod: str | None) -> str:
    """The pod a command acts on: the named one, or the only active one."""
    live = active_pods()
    if pod:
        if pod not in live:
            raise SystemExit(f"refusing: {pod} is not an active pod of {CAMPAIGN}")
        return pod
    if len(live) != 1:
        raise SystemExit(f"name the pod with --pod; active: {live}")
    return live[0]


IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:"
    "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
)
GPU = "NVIDIA A40"
MAX_RATE = 0.49
CEILING_USD = 20.0
BALANCE_FLOOR = 2.0
CLEANUP_RESERVE_USD = 0.25
DISK_GB = 20
DISK_USD_PER_GB_MONTH = (
    0.10  # container disk, observed list price (TWO_HOST_STUDY_QUOTE.md)
)
CA_ROOTS = [
    "ISRG_Root_X1",
    "ISRG_Root_X2",
    "GTS_Root_R1",
    "GTS_Root_R2",
    "GTS_Root_R3",
    "GTS_Root_R4",
    "GlobalSign_Root_CA",
    "GlobalSign_Root_CA_-_R3",
    "GlobalSign_Root_CA_-_R6",
    "GlobalSign_Root_E46",
    "GlobalSign_Root_R46",
    "DigiCert_Global_Root_CA",
    "DigiCert_Global_Root_G2",
    "DigiCert_Global_Root_G3",
    "DigiCert_High_Assurance_EV_Root_CA",
    "DigiCert_TLS_RSA4096_Root_G5",
    "USERTrust_ECC_Certification_Authority",
    "USERTrust_RSA_Certification_Authority",
    "Sectigo_Public_Server_Authentication_Root_E46",
    "Sectigo_Public_Server_Authentication_Root_R46",
    "Amazon_Root_CA_1",
    "Amazon_Root_CA_2",
    "Amazon_Root_CA_3",
    "Amazon_Root_CA_4",
    "SSL.com_TLS_RSA_Root_CA_2022",
    "SSL.com_TLS_ECC_Root_CA_2022",
    "SSL.com_Root_Certification_Authority_RSA",
    "SSL.com_Root_Certification_Authority_ECC",
    "Starfield_Root_Certificate_Authority_-_G2",
    "Baltimore_CyberTrust_Root",
]


def _key() -> str:
    return Path(os.path.join(STATE_DIR, "api_key")).read_text().strip()


def _req(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout=60,
):
    data = json.dumps(body).encode() if body is not None else None
    h = {
        "Authorization": "Bearer " + _key(),
        "Content-Type": "application/json",
        "User-Agent": "carbon-exam-design/1",
    } | (headers or {})
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def rest(method: str, path: str, body=None):
    code, raw = _req(method, "https://rest.runpod.io/v1" + path, body)
    try:
        return code, json.loads(raw or b"null")
    except Exception:  # noqa: BLE001 -- failure is typed
        return code, raw.decode(errors="replace")


def gql(query: str) -> dict:
    _, raw = _req("POST", "https://api.runpod.io/graphql", {"query": query})
    return json.loads(raw)


def account() -> dict:
    return gql("query { myself { clientBalance currentSpendPerHr spendLimit } }")[
        "data"
    ]["myself"]


def a40_price(cuda: str) -> tuple[float | None, str | None]:
    d = gql(
        'query { gpuTypes(input:{id:"'
        + GPU
        + '"}) { lowestPrice(input:{gpuCount:1, secureCloud:true, cudaVersion:"'
        + cuda
        + '"}) { uninterruptablePrice stockStatus } } }'
    )
    lp = d["data"]["gpuTypes"][0]["lowestPrice"]
    return lp["uninterruptablePrice"], lp["stockStatus"]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ledger(event: str, **kw) -> dict:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    rec = {"utc": now(), "event": event} | kw
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def ledger_rows() -> list[dict]:
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER) if l.strip()]


def committed_spend() -> float:
    """Estimated spend of every pod the ledger knows, finished or not (a live pod counts its full deadline)."""
    pods: dict[str, dict] = {}
    for r in ledger_rows():
        if r["event"] == "created":
            pods[r["pod_id"]] = {
                "rate": r["rate"],
                "start": r["created_epoch"],
                "deadline": r["deadline_epoch"],
            }
        elif r["event"] == "terminated_verified" and r["pod_id"] in pods:
            pods[r["pod_id"]]["end"] = r["verified_epoch"]
        elif r["event"] == "connectivity_test":
            pods[r["pod_id"]] = {"fixed": r["cost_usd"]}
    total = 0.0
    for p in pods.values():
        if "fixed" in p:
            total += p["fixed"]
            continue
        end = p.get("end", max(p["deadline"], time.time()))
        hours = (end - p["start"]) / 3600
        total += hours * (p["rate"] + DISK_GB * DISK_USD_PER_GB_MONTH / 730)
    return total


def campaign_cap() -> float:
    for r in ledger_rows():
        if r["event"] == "campaign_start":
            return r["cap_usd"]
    raise SystemExit("no campaign_start in the ledger; run `start` first")


def code_manifest(ref: str, paths: list[str]) -> dict:
    out = {}
    for p in paths:
        data = subprocess.run(
            ["git", "-C", REPO, "show", f"{ref}:{p}"], capture_output=True, check=True
        ).stdout
        out[p] = hashlib.sha256(data).hexdigest()
    return out


def ca_bundle_gz_b64() -> str:
    pem = "".join(
        Path(f"/etc/ssl/certs/{n}.pem").read_text()
        for n in CA_ROOTS
        if os.path.exists(f"/etc/ssl/certs/{n}.pem")
    )
    return base64.b64encode(gzip.compress(pem.encode(), 9)).decode()


def pods() -> list:
    code, body = rest("GET", "/pods")
    if code != 200:
        raise SystemExit(f"cannot list pods: {code} {body}")
    return body


def start_cap(balance: float, cap_usd: float | None) -> float:
    """The campaign cap: the requested cap, never above the campaign ceiling
    or the balance less the floor."""
    requested = CEILING_USD if cap_usd is None else min(float(cap_usd), CEILING_USD)
    return min(requested, balance - BALANCE_FLOOR)


def cmd_start(a) -> None:
    if any(r["event"] == "campaign_start" for r in ledger_rows()):
        raise SystemExit("campaign already started; the cap is fixed at start")
    acct = account()
    cap = start_cap(acct["clientBalance"], a.cap_usd)
    if CAMPAIGN == "exam-design":
        ledger(
            "campaign_start",
            balance_usd=acct["clientBalance"],
            cap_usd=round(cap, 4),
            rule="min(USD 20, balance - USD 2); no top-up, no billing change",
        )
        ledger(
            "connectivity_test",
            pod_id="d69n88ih5wkx3i",
            cost_usd=0.011,
            note="bounded connectivity test before the campaign; counted against the cap conservatively",
        )
    else:
        ledger(
            "campaign_start",
            campaign=CAMPAIGN,
            balance_usd=acct["clientBalance"],
            cap_usd=round(cap, 4),
            max_pods=CAMPAIGNS[CAMPAIGN]["max_pods"],
            rule=(
                f"min(requested cap, USD {CEILING_USD:g}, balance - USD "
                f"{BALANCE_FLOOR:g}); no top-up, no billing change"
            ),
        )
    print(json.dumps({"balance": acct["clientBalance"], "cap_usd": round(cap, 4)}))


def cmd_status(a) -> None:
    acct = account()
    print(
        json.dumps(
            {
                "balance_usd": acct["clientBalance"],
                "spend_per_hr": acct["currentSpendPerHr"],
                "pods": [
                    {
                        "id": p["id"],
                        "name": p.get("name"),
                        "status": p.get("desiredStatus"),
                    }
                    for p in pods()
                ],
                "campaign": CAMPAIGN,
                "active_pods": active_pods(),
                "committed_spend_usd": round(committed_spend(), 4),
                "cap_usd": campaign_cap(),
            },
            indent=1,
        )
    )


def allowed_pods(requested: int | None) -> int:
    """Pods that may run at once: `--max-pods`, never above the campaign's
    hard limit (one for the exam-design campaign)."""
    return max(1, min(int(requested or 1), CAMPAIGNS[CAMPAIGN]["max_pods"]))


def check_pod_allowance(recorded: list, live: list, allowed: int) -> None:
    if len(recorded) >= allowed:
        raise SystemExit(
            f"refusing: {len(recorded)} active pod(s) recorded {recorded}; "
            f"allowance {allowed}; reconcile or terminate first"
        )
    if len(live) >= allowed:
        raise SystemExit(
            f"refusing: {len(live)} pod(s) already exist on the account; allowance {allowed}"
        )


def check_budget(spent: float, pod_cost: float, cap: float) -> None:
    """Committed spend (live pods to their full deadline) + this pod's
    full-deadline cost + the cleanup reserve must stay within the cap."""
    if spent + pod_cost + CLEANUP_RESERVE_USD > cap:
        raise SystemExit(
            f"refusing: committed {spent:.3f} + pod {pod_cost:.3f} + reserve "
            f"{CLEANUP_RESERVE_USD:.2f} > cap {cap:.2f}"
        )


def pod_cost_usd(minutes: float, rate: float = MAX_RATE) -> float:
    return minutes / 60 * (rate + DISK_GB * DISK_USD_PER_GB_MONTH / 730)


def ship_paths(ref: str, prefixes) -> list[str]:
    """Every tracked file under each prefix at `ref` (a directory such as
    `carbon`, or one file)."""
    out = []
    for prefix in prefixes:
        files = subprocess.run(
            ["git", "-C", REPO, "ls-tree", "-r", "--name-only", ref, "--", prefix],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if not files:
            raise SystemExit(f"refusing: nothing tracked under {prefix} at {ref}")
        out += files
    return out


def manifest_env(manifest: dict) -> dict:
    """The manifest for the pod's environment; gzipped when large."""
    text = json.dumps(manifest, separators=(",", ":"), sort_keys=True)
    if len(text) <= MANIFEST_GZ_ABOVE:
        return {"CODE_MANIFEST": text}
    return {
        "CODE_MANIFEST_GZ_B64": base64.b64encode(
            gzip.compress(text.encode(), 9, mtime=0)
        ).decode()
    }


def ref_is_pushed(ref: str) -> bool:
    """The pod reads code from GitHub at `ref`: it must be on a remote branch."""
    out = subprocess.run(
        ["git", "-C", REPO, "branch", "-r", "--contains", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.returncode == 0 and bool(out.stdout.strip())


def cmd_dispatch(a) -> None:
    allowed = allowed_pods(a.max_pods)
    check_pod_allowance(active_pods(), pods(), allowed)
    cuda_ok = []
    for cuda in (
        "13.0",
    ):  # the REST create schema accepts CUDA versions up to 13.0; keeps the host line fixed
        price, stock = a40_price(cuda)
        if price is not None and price <= MAX_RATE and stock:
            cuda_ok.append(cuda)
    if not cuda_ok:
        raise SystemExit(
            f"refusing: no {GPU} Secure pod at <= USD {MAX_RATE}/hr on CUDA 13.0 right now"
        )
    rate = MAX_RATE
    acct = account()
    minutes = float(a.minutes)
    pod_cost = pod_cost_usd(minutes, rate)
    spent = committed_spend()
    cap = campaign_cap()
    check_budget(spent, pod_cost, cap)
    if acct["clientBalance"] - pod_cost < BALANCE_FLOOR:
        raise SystemExit("refusing: balance would fall below the floor")
    ref = (
        a.ref
        or subprocess.run(
            ["git", "-C", REPO, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    )
    paths = subprocess.run(
        [
            "git",
            "-C",
            REPO,
            "ls-tree",
            "-r",
            "--name-only",
            ref,
            "scripts/dev/exam_design",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not ref_is_pushed(ref):
        raise SystemExit(
            f"refusing: {ref} is on no remote branch; push it first (the pod fetches it)"
        )
    plan_doc = (
        json.loads(Path(os.path.join(REPO, a.plan)).read_text()) if a.plan else {}
    )
    # Whole trees the plan or the operator names (e.g. the `carbon` package).
    paths += ship_paths(ref, [*plan_doc.get("ship", []), *(a.ship or [])])
    paths += [a.plan] if a.plan else []
    paths = list(dict.fromkeys(paths))
    if a.plan:
        # Every repository file the plan names (TRAIN file, inputs, OCV table, slot list, blobs) is shipped and
        # hash-pinned too; a child must never find a referenced path missing on the pod.
        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from walk(v)
            elif isinstance(o, list):
                for v in o:
                    yield from walk(v)
            elif isinstance(o, str) and "/" in o and not o.startswith("/"):
                yield o

        tracked = set(
            subprocess.run(
                ["git", "-C", REPO, "ls-tree", "-r", "--name-only", ref],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
        )
        paths += sorted(
            {
                p
                for p in walk(json.loads(Path(os.path.join(REPO, a.plan)).read_text()))
                if p in tracked
            }
            - set(paths)
        )
    manifest = code_manifest(ref, paths)
    token = secrets.token_urlsafe(24)
    created_req = time.time()
    deadline = created_req + minutes * 60
    phase_cfg = {"plan_path": a.plan} if a.plan else {}
    phase_cfg["stop_admitting_epoch"] = deadline - a.export_minutes * 60
    if a.max_workers:
        phase_cfg["max_workers"] = a.max_workers
    if a.skip_from:
        # Resume: every case already completed OK on an earlier pod is skipped, never paid for twice.
        keys = set()
        for path in a.skip_from:
            for line in open(path):  # noqa: SIM115 -- long-lived handle
                r = json.loads(line)
                if r.get("status") == "OK":
                    keys.add(f'{r["case_id"]}{"/R" if r.get("refined") else ""}')
        phase_cfg["skip_case_keys"] = sorted(keys)
    env = {
        "PROBE_TOKEN": token,
        "PROBE_DEADLINE": str(int(deadline + 60)),
        "PROBE_CA_GZ_B64": ca_bundle_gz_b64(),
        "CODE_REF": ref,
        **manifest_env(manifest),
        "PHASE": a.phase,
        "PHASE_CONFIG": json.dumps(phase_cfg),
    }
    if a.private_key_name:
        from scripts.dev.exam_design import private_cases

        env["PRIVATE_KEY"] = private_cases.key_hex(a.private_key_name)
    if a.overlay:
        # "name=path,name=path" or a bare path (named after the phase)
        items = [
            x.split("=", 1) if "=" in x else [a.phase, x] for x in a.overlay.split(",")
        ]
        env["OVERLAYS"] = json.dumps({k: v for k, v in items})
    if a.jax_platform:
        # The pinned study image selects the CPU backend unless told otherwise (found when a photonic child
        # reported devices ["cpu:0"] on an A40); GPU work must name the platform explicitly.
        env["JAX_PLATFORMS"] = a.jax_platform
    if a.pinned_xla:
        env |= {
            "XLA_FLAGS": "--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true "
            "--xla_gpu_autotune_level=0",
            "NVIDIA_TF32_OVERRIDE": "0",
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
            "JAX_DEFAULT_MATMUL_PRECISION": "highest",
            "JAX_ENABLE_COMPILATION_CACHE": "false",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        }
    boot = Path(os.path.join(os.path.dirname(__file__), "bootstrap.py")).read_text()
    body = {
        "name": f"{CAMPAIGNS[CAMPAIGN]['name']}-{a.phase}",
        "imageName": IMAGE,
        "computeType": "GPU",
        "cloudType": "SECURE",
        "interruptible": False,
        "gpuTypeIds": [GPU],
        "gpuCount": 1,
        "allowedCudaVersions": cuda_ok,
        "containerDiskInGb": DISK_GB,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "dockerEntrypoint": ["/opt/carbon-worker/bin/python"],
        "dockerStartCmd": ["-I", "-c", boot],
        "env": env,
    }
    if a.vcpu:
        body["vcpuCount"] = a.vcpu
    ledger(
        "dispatch_requested",
        campaign=CAMPAIGN,
        max_pods=allowed,
        phase=a.phase,
        plan=a.plan,
        ref=ref,
        minutes=minutes,
        balance_usd=acct["clientBalance"],
        committed_before_usd=round(spent, 4),
        cuda=cuda_ok,
    )
    code, resp = rest("POST", "/pods", body)
    pod_id = resp.get("id") if isinstance(resp, dict) else None
    if not pod_id:
        # Ambiguous or failed create: reconcile before any further request.
        after = pods()
        ledger(
            "create_failed",
            http=code,
            response=str(resp)[:300],
            pods_after=[p["id"] for p in after],
        )
        raise SystemExit(
            f"create failed ({code}); pods now: {[p['id'] for p in after]} - reconcile before retrying"
        )
    record_active(pod_id, token)
    rate_actual = float(resp.get("costPerHr") or rate)
    ledger(
        "created",
        pod_id=pod_id,
        phase=a.phase,
        rate=rate_actual,
        created_epoch=created_req,
        deadline_epoch=deadline,
        machine_id=resp.get("machineId"),
        image=resp.get("imageName"),
        ref=ref,
        code_manifest_sha256=hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest(),
    )
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.dev.exam_design.runpod.pod_control",
            "--campaign",
            CAMPAIGN,
            "watchdog",
            pod_id,
            str(int(deadline)),
        ],
        cwd=REPO,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    if rate_actual > MAX_RATE:
        print(f"rate {rate_actual} > {MAX_RATE}: terminating immediately")
        _terminate(pod_id)
        return
    print(
        json.dumps(
            {
                "pod_id": pod_id,
                "rate": rate_actual,
                "deadline_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(deadline)
                ),
                "ref": ref,
                "files": len(manifest),
            }
        )
    )


def _proxy(path: str, timeout=60, pod: str | None = None):
    pod = pick_pod(pod)
    r = urllib.request.Request(
        f"https://{pod}-8000.proxy.runpod.net{path}",
        headers={"X-Probe-Token": token_for(pod), "User-Agent": "carbon-exam-design/1"},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001 -- failure is typed
        return 0, repr(e).encode()


def cmd_poll(a) -> None:
    code, body = _proxy("/status", pod=a.pod)
    print(code, body.decode(errors="replace")[:3000])


def safe_relpath(rel: str) -> bool:
    parts = rel.split("/")
    return (
        bool(rel)
        and not rel.startswith("/")
        and all(p not in ("", ".", "..") for p in parts)
    )


def fetch_files(listing: list, get, dest: str) -> dict:
    """Download every listed file with `get(path) -> (code, bytes)`, verify its
    size and sha256, and write it under `dest`. Refuses unsafe paths and
    existing files that differ. Returns a summary with the listing digest."""
    total = 0
    for row in listing:
        if not safe_relpath(row["path"]):
            raise SystemExit(f"refusing unsafe path {row['path']!r}")
    for row in listing:
        code, body = get(row["path"])
        if (
            code != 200
            or len(body) != row["size"]
            or hashlib.sha256(body).hexdigest() != row["sha256"]
        ):
            raise SystemExit(f"fetch failed or hash mismatch: {row['path']} ({code})")
        target = os.path.join(dest, *row["path"].split("/"))
        if os.path.exists(target):
            if Path(target).read_bytes() != body:
                raise SystemExit(f"refusing to overwrite a different {target}")
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        Path(target).write_bytes(body)
        total += len(body)
    return {
        "files": len(listing),
        "bytes_written": total,
        "listing_sha256": hashlib.sha256(
            json.dumps(listing, sort_keys=True).encode()
        ).hexdigest(),
    }


def cmd_fetch(a) -> None:
    pod = pick_pod(a.pod)
    if not a.tar:
        # File by file: a large result never travels as one long response.
        code, body = _proxy("/files", pod=pod)
        if code != 200:
            raise SystemExit(f"listing failed: {code}")
        summary = fetch_files(
            json.loads(body),
            lambda rel: _proxy("/file/" + urllib.parse.quote(rel), 600, pod),
            os.path.join(a.dest, "out"),
        )
        ledger("exported", pod_id=pod, dest=os.path.relpath(a.dest, REPO), **summary)
        print(json.dumps(summary | {"dest": a.dest}))
        return
    code, body = _proxy("/out.tar.gz", timeout=600, pod=pod)
    if code != 200:
        raise SystemExit(f"fetch failed: {code}")
    sha = hashlib.sha256(body).hexdigest()
    os.makedirs(a.dest, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
        for m in tf.getmembers():
            if (
                m.name.startswith("/")
                or ".." in m.name.split("/")
                or not (m.isfile() or m.isdir())
            ):
                raise SystemExit(f"refusing unsafe tar member {m.name}")
        tf.extractall(a.dest)
    ledger(
        "exported",
        pod_id=pod,
        dest=os.path.relpath(a.dest, REPO),
        bytes=len(body),
        sha256=sha,
    )
    print(json.dumps({"bytes": len(body), "sha256": sha, "dest": a.dest}))


def _terminate(pod_id: str) -> bool:
    ledger("terminate_requested", pod_id=pod_id)
    for _ in range(6):
        rest("DELETE", f"/pods/{pod_id}")
        c2, _b2 = rest("GET", f"/pods/{pod_id}")
        if c2 == 404:
            ledger("terminated_verified", pod_id=pod_id, verified_epoch=time.time())
            clear_active(pod_id)
            return True
        time.sleep(10)
    ledger("terminate_unverified", pod_id=pod_id)
    return False


def cmd_terminate(a) -> None:
    pod_id = pick_pod(a.pod)
    ok = _terminate(pod_id)
    print(
        json.dumps(
            {
                "pod_id": pod_id,
                "terminated": ok,
                "pods_now": [p["id"] for p in pods()],
                "committed_spend_usd": round(committed_spend(), 4),
            }
        )
    )


def cmd_watchdog(a) -> None:
    pod_id, deadline = a.pod, float(a.deadline)
    while time.time() < deadline:
        if pod_id not in active_pods():
            return  # terminated by the operator
        time.sleep(10)
    ledger("watchdog_deadline", pod_id=pod_id)
    _terminate(pod_id)


def cmd_reconcile(a) -> None:
    live = pods()
    recorded = active_pods()
    print(
        json.dumps(
            {
                "campaign": CAMPAIGN,
                "recorded_active": recorded,
                "live_pods": [{"id": p["id"], "name": p.get("name")} for p in live],
            }
        )
    )
    for rec in recorded:
        if rec not in [p["id"] for p in live]:
            ledger(
                "terminated_verified",
                pod_id=rec,
                verified_epoch=time.time(),
                note="found absent at reconcile",
            )
            clear_active(rec)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", choices=sorted(CAMPAIGNS), default="exam-design")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--cap-usd", type=float, help="never above the campaign ceiling")
    sub.add_parser("status")
    d = sub.add_parser("dispatch")
    d.add_argument("phase")
    d.add_argument("--plan")
    d.add_argument("--minutes", required=True)
    d.add_argument("--export-minutes", type=float, default=5)
    d.add_argument("--ref")
    d.add_argument("--overlay")
    d.add_argument("--pinned-xla", action="store_true")
    d.add_argument("--vcpu", type=int)
    d.add_argument(
        "--private-key-name",
        help="key for the plan's encrypted private jobs (never printed)",
    )
    d.add_argument("--max-workers", type=int)
    d.add_argument("--jax-platform", help="e.g. cuda; the image defaults JAX to CPU")
    d.add_argument(
        "--skip-from",
        nargs="*",
        help="records.jsonl files whose OK cases are skipped (resume)",
    )
    d.add_argument(
        "--ship",
        nargs="*",
        help="tracked trees to ship hash-pinned besides scripts/dev/exam_design",
    )
    d.add_argument(
        "--max-pods",
        type=int,
        default=1,
        help="pods allowed at once, never above the campaign's hard limit",
    )
    p = sub.add_parser("poll")
    p.add_argument("--pod")
    f = sub.add_parser("fetch")
    f.add_argument("dest")
    f.add_argument("--pod")
    f.add_argument("--tar", action="store_true", help="one tarball (small results)")
    t = sub.add_parser("terminate")
    t.add_argument("--pod")
    w = sub.add_parser("watchdog")
    w.add_argument("pod")
    w.add_argument("deadline")
    sub.add_parser("reconcile")
    a = ap.parse_args(argv)
    use_campaign(a.campaign)
    {
        "start": cmd_start,
        "status": cmd_status,
        "dispatch": cmd_dispatch,
        "poll": cmd_poll,
        "fetch": cmd_fetch,
        "terminate": cmd_terminate,
        "watchdog": cmd_watchdog,
        "reconcile": cmd_reconcile,
    }[a.cmd](a)


if __name__ == "__main__":
    main()
