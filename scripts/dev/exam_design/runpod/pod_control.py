"""Operator commands for exam-design pods: one A40 at a time, bounded and accounted.

    python -m scripts.dev.exam_design.runpod.pod_control status
    python -m scripts.dev.exam_design.runpod.pod_control dispatch PHASE --plan PATH --minutes N [--ref SHA]
    python -m scripts.dev.exam_design.runpod.pod_control poll          # pod status page
    python -m scripts.dev.exam_design.runpod.pod_control fetch DEST    # results tarball, verified
    python -m scripts.dev.exam_design.runpod.pod_control terminate     # only the recorded pod; verified
    python -m scripts.dev.exam_design.runpod.pod_control reconcile     # after an interruption

The API key is read from ``~/.runpod/api_key`` (mode 600) and never printed,
logged or placed on a command line. The active pod id is written to
``~/.runpod/exam_design_active_pod`` the moment the create call returns, and
every lifecycle event is appended to the campaign ledger in the repository.

Refusals, all before any spend: a pod already exists; the A40 Secure rate is
above ``MAX_RATE``; the account balance would fall below ``BALANCE_FLOOR``; or
the ledger's committed spend plus this pod's full-deadline cost plus the
cleanup reserve would exceed the campaign ceiling.
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
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
EVID = os.path.join(REPO, "docs/development/evidence/exam-design-2026-09-24")
LEDGER = os.path.join(EVID, "accounting/ledger.jsonl")
STATE_DIR = os.path.expanduser("~/.runpod")
ACTIVE = os.path.join(STATE_DIR, "exam_design_active_pod")
TOKEN_FILE = os.path.join(STATE_DIR, "exam_design_token")

IMAGE = ("ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:"
         "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940")
GPU = "NVIDIA A40"
MAX_RATE = 0.49
CEILING_USD = 20.0
BALANCE_FLOOR = 2.0
CLEANUP_RESERVE_USD = 0.25
DISK_GB = 20
DISK_USD_PER_GB_MONTH = 0.10  # container disk, observed list price (TWO_HOST_STUDY_QUOTE.md)
CA_ROOTS = [
    "ISRG_Root_X1", "ISRG_Root_X2", "GTS_Root_R1", "GTS_Root_R2", "GTS_Root_R3", "GTS_Root_R4",
    "GlobalSign_Root_CA", "GlobalSign_Root_CA_-_R3", "GlobalSign_Root_CA_-_R6", "GlobalSign_Root_E46",
    "GlobalSign_Root_R46", "DigiCert_Global_Root_CA", "DigiCert_Global_Root_G2", "DigiCert_Global_Root_G3",
    "DigiCert_High_Assurance_EV_Root_CA", "DigiCert_TLS_RSA4096_Root_G5", "USERTrust_ECC_Certification_Authority",
    "USERTrust_RSA_Certification_Authority", "Sectigo_Public_Server_Authentication_Root_E46",
    "Sectigo_Public_Server_Authentication_Root_R46", "Amazon_Root_CA_1", "Amazon_Root_CA_2", "Amazon_Root_CA_3",
    "Amazon_Root_CA_4", "SSL.com_TLS_RSA_Root_CA_2022", "SSL.com_TLS_ECC_Root_CA_2022",
    "SSL.com_Root_Certification_Authority_RSA", "SSL.com_Root_Certification_Authority_ECC",
    "Starfield_Root_Certificate_Authority_-_G2", "Baltimore_CyberTrust_Root",
]


def _key() -> str:
    return open(os.path.join(STATE_DIR, "api_key")).read().strip()


def _req(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Authorization": "Bearer " + _key(), "Content-Type": "application/json",
         "User-Agent": "carbon-exam-design/1"} | (headers or {})
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
    except Exception:
        return code, raw.decode(errors="replace")


def gql(query: str) -> dict:
    _, raw = _req("POST", "https://api.runpod.io/graphql", {"query": query})
    return json.loads(raw)


def account() -> dict:
    return gql("query { myself { clientBalance currentSpendPerHr spendLimit } }")["data"]["myself"]


def a40_price(cuda: str) -> tuple[float | None, str | None]:
    d = gql('query { gpuTypes(input:{id:"%s"}) { lowestPrice(input:{gpuCount:1, secureCloud:true, cudaVersion:"%s"})'
            ' { uninterruptablePrice stockStatus } } }' % (GPU, cuda))
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
            pods[r["pod_id"]] = {"rate": r["rate"], "start": r["created_epoch"], "deadline": r["deadline_epoch"]}
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
        data = subprocess.run(["git", "-C", REPO, "show", f"{ref}:{p}"], capture_output=True, check=True).stdout
        out[p] = hashlib.sha256(data).hexdigest()
    return out


def ca_bundle_gz_b64() -> str:
    pem = "".join(open(f"/etc/ssl/certs/{n}.pem").read() for n in CA_ROOTS if os.path.exists(f"/etc/ssl/certs/{n}.pem"))
    return base64.b64encode(gzip.compress(pem.encode(), 9)).decode()


def pods() -> list:
    code, body = rest("GET", "/pods")
    if code != 200:
        raise SystemExit(f"cannot list pods: {code} {body}")
    return body


def cmd_start(a) -> None:
    acct = account()
    cap = min(CEILING_USD, acct["clientBalance"] - BALANCE_FLOOR)
    if any(r["event"] == "campaign_start" for r in ledger_rows()):
        raise SystemExit("campaign already started; the cap is fixed at start")
    ledger("campaign_start", balance_usd=acct["clientBalance"], cap_usd=round(cap, 4),
           rule="min(USD 20, balance - USD 2); no top-up, no billing change")
    ledger("connectivity_test", pod_id="d69n88ih5wkx3i", cost_usd=0.011,
           note="bounded connectivity test before the campaign; counted against the cap conservatively")
    print(json.dumps({"balance": acct["clientBalance"], "cap_usd": round(cap, 4)}))


def cmd_status(a) -> None:
    acct = account()
    print(json.dumps({"balance_usd": acct["clientBalance"], "spend_per_hr": acct["currentSpendPerHr"],
                      "pods": [{"id": p["id"], "name": p.get("name"), "status": p.get("desiredStatus")} for p in pods()],
                      "active_file": open(ACTIVE).read().strip() if os.path.exists(ACTIVE) else None,
                      "committed_spend_usd": round(committed_spend(), 4), "cap_usd": campaign_cap()}, indent=1))


def cmd_dispatch(a) -> None:
    if os.path.exists(ACTIVE):
        raise SystemExit(f"refusing: an active pod is recorded ({open(ACTIVE).read().strip()}); reconcile first")
    existing = pods()
    if existing:
        raise SystemExit(f"refusing: {len(existing)} pod(s) already exist; one A40 at a time")
    cuda_ok = []
    for cuda in ("13.0",):  # the REST create schema accepts CUDA versions up to 13.0; keeps the host line fixed
        price, stock = a40_price(cuda)
        if price is not None and price <= MAX_RATE and stock:
            cuda_ok.append(cuda)
    if not cuda_ok:
        raise SystemExit(f"refusing: no {GPU} Secure pod at <= USD {MAX_RATE}/hr on CUDA 13.0 right now")
    rate = MAX_RATE
    acct = account()
    minutes = float(a.minutes)
    pod_cost = minutes / 60 * (rate + DISK_GB * DISK_USD_PER_GB_MONTH / 730)
    spent = committed_spend()
    cap = campaign_cap()
    if spent + pod_cost + CLEANUP_RESERVE_USD > cap:
        raise SystemExit(f"refusing: committed {spent:.3f} + pod {pod_cost:.3f} + reserve > cap {cap:.2f}")
    if acct["clientBalance"] - pod_cost < BALANCE_FLOOR:
        raise SystemExit("refusing: balance would fall below the floor")
    ref = a.ref or subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    paths = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", ref, "scripts/dev/exam_design"],
                           capture_output=True, text=True, check=True).stdout.split()
    paths += [a.plan] if a.plan else []
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
        tracked = set(subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", ref], capture_output=True,
                                     text=True, check=True).stdout.split())
        paths += sorted({p for p in walk(json.load(open(os.path.join(REPO, a.plan)))) if p in tracked} - set(paths))
    manifest = code_manifest(ref, paths)
    token = secrets.token_urlsafe(24)
    old = os.umask(0o077)
    open(TOKEN_FILE, "w").write(token)
    os.umask(old)
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
            for line in open(path):
                r = json.loads(line)
                if r.get("status") == "OK":
                    keys.add(f'{r["case_id"]}{"/R" if r.get("refined") else ""}')
        phase_cfg["skip_case_keys"] = sorted(keys)
    env = {"PROBE_TOKEN": token, "PROBE_DEADLINE": str(int(deadline + 60)), "PROBE_CA_GZ_B64": ca_bundle_gz_b64(),
           "CODE_REF": ref, "CODE_MANIFEST": json.dumps(manifest, separators=(",", ":")), "PHASE": a.phase,
           "PHASE_CONFIG": json.dumps(phase_cfg)}
    if a.private_key_name:
        from scripts.dev.exam_design import private_cases

        env["PRIVATE_KEY"] = private_cases.key_hex(a.private_key_name)
    if a.overlay:
        # "name=path,name=path" or a bare path (named after the phase)
        items = [x.split("=", 1) if "=" in x else [a.phase, x] for x in a.overlay.split(",")]
        env["OVERLAYS"] = json.dumps({k: v for k, v in items})
    if a.jax_platform:
        # The pinned study image selects the CPU backend unless told otherwise (found when a photonic child
        # reported devices ["cpu:0"] on an A40); GPU work must name the platform explicitly.
        env["JAX_PLATFORMS"] = a.jax_platform
    if a.pinned_xla:
        env |= {"XLA_FLAGS": "--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true "
                             "--xla_gpu_autotune_level=0", "NVIDIA_TF32_OVERRIDE": "0",
                "CUBLAS_WORKSPACE_CONFIG": ":4096:8", "JAX_DEFAULT_MATMUL_PRECISION": "highest",
                "JAX_ENABLE_COMPILATION_CACHE": "false", "XLA_PYTHON_CLIENT_PREALLOCATE": "false"}
    boot = open(os.path.join(os.path.dirname(__file__), "bootstrap.py")).read()
    body = {"name": f"carbon-exam-design-{a.phase}", "imageName": IMAGE, "computeType": "GPU", "cloudType": "SECURE",
            "interruptible": False, "gpuTypeIds": [GPU], "gpuCount": 1, "allowedCudaVersions": cuda_ok,
            "containerDiskInGb": DISK_GB, "volumeInGb": 0, "ports": ["8000/http"],
            "dockerEntrypoint": ["/opt/carbon-worker/bin/python"], "dockerStartCmd": ["-I", "-c", boot], "env": env}
    if a.vcpu:
        body["vcpuCount"] = a.vcpu
    ledger("dispatch_requested", phase=a.phase, plan=a.plan, ref=ref, minutes=minutes, balance_usd=acct["clientBalance"],
           committed_before_usd=round(spent, 4), cuda=cuda_ok)
    code, resp = rest("POST", "/pods", body)
    pod_id = resp.get("id") if isinstance(resp, dict) else None
    if not pod_id:
        # Ambiguous or failed create: reconcile before any further request.
        after = pods()
        ledger("create_failed", http=code, response=str(resp)[:300], pods_after=[p["id"] for p in after])
        raise SystemExit(f"create failed ({code}); pods now: {[p['id'] for p in after]} - reconcile before retrying")
    open(ACTIVE, "w").write(pod_id)
    rate_actual = float(resp.get("costPerHr") or rate)
    ledger("created", pod_id=pod_id, phase=a.phase, rate=rate_actual, created_epoch=created_req,
           deadline_epoch=deadline, machine_id=resp.get("machineId"), image=resp.get("imageName"), ref=ref,
           code_manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest())
    subprocess.Popen([sys.executable, "-m", "scripts.dev.exam_design.runpod.pod_control", "watchdog", pod_id,
                      str(int(deadline))], cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    if rate_actual > MAX_RATE:
        print(f"rate {rate_actual} > {MAX_RATE}: terminating immediately")
        _terminate(pod_id)
        return
    print(json.dumps({"pod_id": pod_id, "rate": rate_actual, "deadline_utc": time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(deadline)), "ref": ref, "files": len(manifest)}))


def _proxy(path: str, timeout=60):
    pod = open(ACTIVE).read().strip()
    token = open(TOKEN_FILE).read().strip()
    r = urllib.request.Request(f"https://{pod}-8000.proxy.runpod.net{path}", headers={"X-Probe-Token": token, "User-Agent": "carbon-exam-design/1"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return 0, repr(e).encode()


def cmd_poll(a) -> None:
    code, body = _proxy("/status")
    print(code, body.decode(errors="replace")[:3000])


def cmd_fetch(a) -> None:
    code, body = _proxy("/out.tar.gz", timeout=600)
    if code != 200:
        raise SystemExit(f"fetch failed: {code}")
    sha = hashlib.sha256(body).hexdigest()
    os.makedirs(a.dest, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.name.startswith("/") or ".." in m.name.split("/") or not (m.isfile() or m.isdir()):
                raise SystemExit(f"refusing unsafe tar member {m.name}")
        tf.extractall(a.dest)
    pod = open(ACTIVE).read().strip()
    ledger("exported", pod_id=pod, dest=os.path.relpath(a.dest, REPO), bytes=len(body), sha256=sha)
    print(json.dumps({"bytes": len(body), "sha256": sha, "dest": a.dest}))


def _terminate(pod_id: str) -> bool:
    ledger("terminate_requested", pod_id=pod_id)
    for _ in range(6):
        code, body = rest("DELETE", f"/pods/{pod_id}")
        c2, b2 = rest("GET", f"/pods/{pod_id}")
        if c2 == 404:
            ledger("terminated_verified", pod_id=pod_id, verified_epoch=time.time())
            if os.path.exists(ACTIVE) and open(ACTIVE).read().strip() == pod_id:
                os.remove(ACTIVE)
            return True
        time.sleep(10)
    ledger("terminate_unverified", pod_id=pod_id)
    return False


def cmd_terminate(a) -> None:
    pod_id = a.pod or open(ACTIVE).read().strip()
    ok = _terminate(pod_id)
    print(json.dumps({"pod_id": pod_id, "terminated": ok, "pods_now": [p["id"] for p in pods()],
                      "committed_spend_usd": round(committed_spend(), 4)}))


def cmd_watchdog(a) -> None:
    pod_id, deadline = a.pod, float(a.deadline)
    while time.time() < deadline:
        if not os.path.exists(ACTIVE) or open(ACTIVE).read().strip() != pod_id:
            return  # terminated by the operator
        time.sleep(10)
    ledger("watchdog_deadline", pod_id=pod_id)
    _terminate(pod_id)


def cmd_reconcile(a) -> None:
    live = pods()
    rec = open(ACTIVE).read().strip() if os.path.exists(ACTIVE) else None
    print(json.dumps({"recorded_active": rec, "live_pods": [{"id": p["id"], "name": p.get("name")} for p in live]}))
    if rec and rec not in [p["id"] for p in live]:
        ledger("terminated_verified", pod_id=rec, verified_epoch=time.time(), note="found absent at reconcile")
        os.remove(ACTIVE)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
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
    d.add_argument("--private-key-name", help="key for the plan's encrypted private jobs (never printed)")
    d.add_argument("--max-workers", type=int)
    d.add_argument("--jax-platform", help="e.g. cuda; the image defaults JAX to CPU")
    d.add_argument("--skip-from", nargs="*", help="records.jsonl files whose OK cases are skipped (resume)")
    sub.add_parser("poll")
    f = sub.add_parser("fetch")
    f.add_argument("dest")
    t = sub.add_parser("terminate")
    t.add_argument("--pod")
    w = sub.add_parser("watchdog")
    w.add_argument("pod")
    w.add_argument("deadline")
    sub.add_parser("reconcile")
    a = ap.parse_args(argv)
    {"start": cmd_start, "status": cmd_status, "dispatch": cmd_dispatch, "poll": cmd_poll, "fetch": cmd_fetch,
     "terminate": cmd_terminate, "watchdog": cmd_watchdog, "reconcile": cmd_reconcile}[a.cmd](a)


if __name__ == "__main__":
    main()
