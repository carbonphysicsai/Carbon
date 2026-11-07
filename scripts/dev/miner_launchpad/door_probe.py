"""Synthetic miner client for release rehearsals (mainnet lock-in sheet section 2).

Three modes, one evidence format:

* ``probe`` (steps 5 and 7): read-only GETs, round-robin at ``--rate`` over the
  door's public routes (feed, koth, koth v2, intake info, queue). A baseline
  window runs first; any non-200 there aborts the run before the swap (the
  control failed). The operator then swaps the door and ends the window with a
  ``STOP`` file (or ``--duration-s`` runs out). Standard library only.
* ``probe`` with ``--r13-recipe`` (step 8): the same probe, plus ONE signed
  resubmit built against OLD's snapshot. The operator writes ``R13_ARM`` in the
  evidence directory just before the swap (the probe reads the intake facts
  then) and ``R13_FIRE`` just after it (the probe signs and sends). Pass: NEW
  accepts it.
* ``burst`` + ``merge`` (step 9, R89): one client per source host, each with its
  own test hotkey. ``--role upload`` stages one large synthetic graph document
  chunk by chunk (the receiver's real resumable path); ``--role feedback``
  sends small signed exam-feedback reads at its own rate (no task, no
  allowance). ``merge`` joins the clients' evidence and counts 429/503 per
  client while an upload ran. ``--spoof-header`` adds a forged client-IP header
  to every POST (the RA spoof case).

Signed modes import Carbon and sign through the hotkey's external signer
(``connect_signer``); no key material is read here. They refuse unless the
process is bound to the staging localnet (``CARBON_CHAIN_NETWORK=localnet``),
except R13 with ``--live-door`` (a live-door submit: the owner's words first).

Evidence per run directory: ``requests.jsonl`` (one line per request: time,
route, status, latency, bytes, the body's schema field and sha256, never the
body), ``summary.json``, and ``SHA256SUMS`` over both.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

SCHEMA = "carbon.door-probe.v1"
MERGE_SCHEMA = "carbon.door-probe.burst-merge.v1"
FEED, KOTH, INTAKE, QUEUE = (
    "/carbon/v1/feed/",
    "/carbon/v1/koth/",
    "/carbon/v1/construction/intake",
    "/carbon/v1/queue/",
)
#: The miner agent string (`carbon/miner_agent.py`): Cloudflare refuses urllib's default with 403.
#: Restated so the GET probe stays standard-library only; a test pins it equal.
USER_AGENT_PREFIX = "carbon-miner/"
#: The Q1 gap rule: no stretch over this many seconds without a 200.
GAP_S = 1.0
#: A local resource bound for the probe itself, not a door limit.
MAX_IN_FLIGHT = 16
ACCEPTED_R13 = ("admitted", "same_recipe_already_submitted", "result")
#: Files the operator writes into the evidence directory.
STOP, R13_ARM, R13_FIRE, BASELINE_OK = "STOP", "R13_ARM", "R13_FIRE", "BASELINE_OK"


def utc(t=None):
    stamp = dt.datetime.fromtimestamp(time.time() if t is None else t, dt.UTC)
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def user_agent():
    try:
        from carbon import __version__
    except ImportError:
        __version__ = "probe"
    return f"{USER_AGENT_PREFIX}{__version__} (+https://carbonphysics.ai)"


def routes(challenge, *, queue=True):
    found = [
        ("feed", FEED + challenge),
        ("koth", KOTH + challenge),
        ("koth_v2", KOTH + challenge + "/v2"),
        ("intake", INTAKE),
    ]
    return found + ([("queue", QUEUE + challenge)] if queue else [])


def _schema_of(body):
    try:
        value = json.loads(body)
    except ValueError:
        return None
    schema = value.get("schema") if type(value) is dict else None
    return schema if type(schema) is str and len(schema) <= 128 else None


def fetch(base, path, *, timeout=10.0, agent=None):
    """One GET; the record keeps the body's schema and digest, never the body."""
    request = urllib.request.Request(
        base.rstrip("/") + path, headers={"User-Agent": agent or user_agent()}
    )
    started = time.monotonic()
    status, body, error = None, b"", None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, body = response.status, response.read(4 * 1024 * 1024)
    except urllib.error.HTTPError as refused:
        status, body = refused.code, refused.read(65536)
    except (OSError, ValueError) as failed:
        error = type(failed).__name__
    return {
        "status": status,
        "latency_ms": round((time.monotonic() - started) * 1000.0, 1),
        "bytes": len(body),
        "schema": _schema_of(body) if body else None,
        "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
        "error": error,
    }


class Recorder:
    """Thread-safe requests.jsonl writer plus the counters the summary needs."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.rows = []
        self.handle = self.path.open("a", encoding="utf-8")

    def add(self, row):
        with self.lock:
            self.rows.append(row)
            self.handle.write(json.dumps(row, sort_keys=True) + "\n")
            self.handle.flush()

    def close(self):
        self.handle.close()


def window_stats(rows, start, end, *, gap_s=GAP_S):
    """Counts for one phase: non-200 per route, max latency, gaps without a 200."""
    non_200, statuses, latencies, ok_times = {}, {}, [], []
    for row in rows:
        key = str(row["status"]) if row["status"] is not None else "error"
        statuses[key] = statuses.get(key, 0) + 1
        latencies.append(row["latency_ms"])
        if row["status"] == 200:
            ok_times.append(row["done_s"])
        else:
            non_200[row["route"]] = non_200.get(row["route"], 0) + 1
    gaps, last = [], start
    for t in sorted(ok_times) + [end]:
        if t - last > gap_s:
            gaps.append({"from_utc": utc(last), "seconds": round(t - last, 3)})
        last = max(last, t)
    return {
        "requests": len(rows),
        "statuses": statuses,
        "non_200": non_200,
        "max_latency_ms": max(latencies, default=None),
        "gaps_over_1s": gaps,
        "max_gap_s": max((g["seconds"] for g in gaps), default=0.0),
    }


def run_phase(
    base,
    paths,
    rate,
    duration_s,
    recorder,
    phase,
    *,
    stop=lambda: False,
    get=fetch,
    clock=time.time,
    sleep=time.sleep,
):
    """GET one route per tick, round-robin, at `rate` per second; each tick on
    its own thread so a held request shows as latency, not as a slowed rate."""
    start, rows, threads, i = clock(), [], [], 0
    saturated = 0
    while True:
        now = clock()
        if now - start >= duration_s or stop():
            break
        due = start + i / rate
        if due > now:
            sleep(min(due - now, 0.25))
            continue
        name, path = paths[i % len(paths)]
        i += 1
        threads = [t for t in threads if t.is_alive()]
        if len(threads) >= MAX_IN_FLIGHT:
            saturated += 1
            continue

        def one(name=name, path=path, sent=now):
            row = {"t_utc": utc(sent), "phase": phase, "route": name, **get(base, path)}
            row["done_s"] = clock()
            rows.append(row)
            recorder.add(row)

        thread = threading.Thread(target=one, daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join(30.0)
    end = clock()
    stats = window_stats(rows, start, end)
    stats.update(start_utc=utc(start), end_utc=utc(end), probe_saturated=saturated)
    return stats


def served_limits(release_root):
    """The receiver limits as written in the served code of the release under
    test (never typed here): PEER_BURST, PEER_RATE, IN_FLIGHT from
    carbon/battery/intake.py and the door's local_hop flag."""
    root = Path(release_root)
    intake = root / "carbon" / "battery" / "intake.py"
    door = root / "carbon" / "challenge_validator" / "direct_intake.py"
    found = {}
    tree = ast.parse(intake.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Tuple)
            and isinstance(node.value, ast.Tuple)
        ):
            for target, value in zip(node.targets[0].elts, node.value.elts):
                if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
                    found[target.id] = value.value
    door_text = door.read_text(encoding="utf-8")
    return {
        "peer_burst": found.get("PEER_BURST"),
        "peer_rate_per_s": found.get("PEER_RATE"),
        "in_flight": found.get("IN_FLIGHT"),
        "local_hop_gets_uncharged": "local_hop = True" in door_text,
        "source": {
            str(p.relative_to(root))
            .replace("\\", "/"): hashlib.sha256(p.read_bytes())
            .hexdigest()
            for p in (intake, door)
        },
    }


def seal(out):
    """SHA256SUMS over the run's evidence files; returns its own digest."""
    out = Path(out)
    lines = [
        f"{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}"
        for name in ("requests.jsonl", "summary.json")
        if (out / name).exists()
    ]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hashlib.sha256((out / "SHA256SUMS").read_bytes()).hexdigest()


def _probe_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _write_summary(out, summary):
    (Path(out) / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return seal(out)


# ---------------------------------------------------------------- signed modes


def _carbon(repo):
    """Signed modes need Carbon; under `python3 -I` the repository is not on the
    path, so it is added here, for these modes only."""
    root = str(Path(repo).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def _require_localnet(*, live_door=False):
    network = os.environ.get("CARBON_CHAIN_NETWORK") or "testnet"
    if network != "localnet" and not live_door:
        raise SystemExit(
            "signed modes run on the staging localnet only (CARBON_CHAIN_NETWORK=localnet); "
            "a live-door R13 needs --live-door and the owner's words first"
        )
    return network


def recording_send(recorder, client, *, spoof=None, timeout=30.0):
    """`direct_submission.post`'s contract (status, json) with one row per attempt.
    A dropped connection is recorded and re-raised so the caller's own reset
    handling runs unchanged."""
    from carbon.development_session.direct_submission import SUBMIT_PATH
    from carbon.miner_agent import MINER_HEADERS

    def send(url, body, headers, *, timeout=timeout):
        extra = dict(spoof or {})
        request = urllib.request.Request(
            url.rstrip("/") + SUBMIT_PATH,
            data=body,
            headers={
                **MINER_HEADERS,
                **headers,
                **extra,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started, sent = time.monotonic(), time.time()
        row = {
            "t_utc": utc(sent),
            "client": client,
            "route": "post",
            "bytes": len(body),
        }
        if extra:
            row["spoofed_header"] = extra
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, answer = response.status, json.loads(response.read(65536))
        except urllib.error.HTTPError as refused:
            raw = refused.read(65536) or b"{}"
            try:
                status, answer = refused.code, json.loads(raw)
            except ValueError:
                status, answer = refused.code, {}
        except OSError as failed:
            recorder.add(
                {
                    **row,
                    "status": None,
                    "error": type(getattr(failed, "reason", failed)).__name__,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                    "done_s": time.time(),
                }
            )
            raise
        code = (
            answer.get("code") or answer.get("refused")
            if type(answer) is dict
            else None
        )
        recorder.add(
            {
                **row,
                "status": status,
                "code": code if type(code) is str else None,
                "schema": answer.get("schema") if type(answer) is dict else None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "done_s": time.time(),
                "error": None,
            }
        )
        return status, answer

    return send


def _recipe(path):
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.reconstruction.served_recipe_contract import registered

    recipe = ConstructionRecipe.from_dict(json.loads(Path(path).read_text("utf-8")))
    challenge = recipe.to_dict()["challenge"]
    return recipe, registered(challenge["id"], challenge["version"]).digest


def r13_resubmit(
    door,
    signer,
    *,
    recipe,
    contract_digest,
    receiver,
    context,
    facts_before,
    root,
    send,
):
    """One signed submit whose body names OLD's snapshot (`facts_before`); the
    later status reads use live facts. Returns a closed outcome, never raises a
    refusal."""
    from carbon.development_session import direct_submission as ds

    reads = {"n": 0}

    def read(url):
        reads["n"] += 1
        return facts_before if reads["n"] == 1 else ds.read_intake(url)

    epoch = int(recipe.digest[7:23], 16)
    try:
        ds.submit_and_wait(
            door,
            signer,
            root=root,
            epoch=epoch,
            recipe=recipe,
            contract_digest=contract_digest,
            receiver=receiver,
            context=context,
            read=read,
            send=send,
            wait_s=0,
        )
        return {"outcome": "result", "code": None}
    except ds.DirectConstructionPending:
        return {"outcome": "admitted", "code": None}
    except ds.DirectSameRecipeSubmitted:
        return {"outcome": "same_recipe_already_submitted", "code": None}
    except ds.DirectIntakeRefusal as refused:
        return {"outcome": "refused", "code": refused.code}


def _r13_thread(args, out, recorder, result, done):
    """Wait for R13_ARM (read OLD's facts), then R13_FIRE (sign + send)."""
    try:
        _carbon(args.repo)
        _require_localnet(live_door=args.live_door)
        from carbon.chain.external_signer import connect_signer
        from carbon.development_session.chain_onboarding import carbon_testnet_context
        from carbon.development_session.direct_submission import read_intake

        recipe, contract = _recipe(args.r13_recipe)
        signer = connect_signer(args.hotkey)
        context = carbon_testnet_context()
        while not (out / R13_ARM).exists():
            if done.is_set():
                result["r13"] = {"outcome": "not_armed"}
                return
            time.sleep(0.05)
        facts = read_intake(args.door)
        result["r13"] = {
            "armed_utc": utc(),
            "snapshot_before": (facts.get("snapshot") or {}).get("id"),
        }
        while not (out / R13_FIRE).exists():
            if done.is_set():
                result["r13"]["outcome"] = "not_fired"
                return
            time.sleep(0.05)
        result["r13"]["posted_utc"] = utc()
        result["r13"].update(
            r13_resubmit(
                args.door,
                signer,
                recipe=recipe,
                contract_digest=contract,
                receiver=args.receiver_hotkey,
                context=context,
                facts_before=facts,
                root=out / "r13_ledger",
                send=recording_send(recorder, "r13"),
            )
        )
    # Evidence, not a crash: the summary names the failure type.
    except Exception as failed:  # noqa: BLE001
        result["r13"] = {
            **result.get("r13", {}),
            "outcome": "probe_error",
            "code": type(failed).__name__,
        }


def cmd_probe(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    recorder = Recorder(out / "requests.jsonl")
    paths = routes(args.challenge, queue=not args.no_queue)
    summary = {
        "schema": SCHEMA,
        "mode": "probe",
        "door": args.door,
        "challenge": args.challenge,
        "rate": args.rate,
        "routes": [name for name, _ in paths],
        "probe_sha256": _probe_digest(),
        "limits": served_limits(args.limits_from) if args.limits_from else None,
        "r13": None,
    }
    stop = lambda: (out / STOP).exists()
    baseline = run_phase(
        args.door, paths, args.rate, args.baseline_s, recorder, "baseline", stop=stop
    )
    summary["baseline"] = baseline
    if baseline["non_200"] or baseline["requests"] == 0:
        summary.update(
            verdict="ABORTED_BASELINE",
            start_utc=baseline["start_utc"],
            end_utc=baseline["end_utc"],
        )
        recorder.close()
        print(
            json.dumps(
                {"verdict": "ABORTED_BASELINE", "sums": _write_summary(out, summary)}
            )
        )
        return 3
    (out / BASELINE_OK).write_text(utc() + "\n", encoding="utf-8")
    result, done, worker = {}, threading.Event(), None
    if args.r13_recipe:
        worker = threading.Thread(
            target=_r13_thread, args=(args, out, recorder, result, done), daemon=True
        )
        worker.start()
    window = run_phase(
        args.door, paths, args.rate, args.duration_s, recorder, "window", stop=stop
    )
    done.set()
    if worker is not None:
        worker.join(60.0)
        summary["r13"] = result.get(
            "r13", {"outcome": "probe_error", "code": "no_result"}
        )
    recorder.close()
    r13_ok = summary["r13"] is None or summary["r13"].get("outcome") in ACCEPTED_R13
    passed = not window["non_200"] and not window["gaps_over_1s"] and r13_ok
    summary.update(
        window=window,
        start_utc=baseline["start_utc"],
        end_utc=window["end_utc"],
        requests=baseline["requests"] + window["requests"],
        non_200=window["non_200"],
        max_latency_ms=window["max_latency_ms"],
        gaps_over_1s=window["gaps_over_1s"],
        verdict="PASS" if passed else "FAIL",
    )
    print(
        json.dumps(
            {"verdict": summary["verdict"], "sums": _write_summary(out, summary)}
        )
    )
    return 0 if passed else 1


def synthetic_document(client, size):
    """Deterministic bytes for one upload, named the way the receiver requires
    (`level4-doc-<sha256>.json`); never parsed until a submission names it."""
    body = hashlib.shake_256(("door-probe:" + client).encode()).digest(size)
    return "level4-doc-" + hashlib.sha256(body).hexdigest() + ".json", body


def _wait_until(start_at):
    if start_at:
        target = dt.datetime.fromisoformat(start_at).timestamp()
        while time.time() < target:
            time.sleep(min(0.05, target - time.time()))


def cmd_burst(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    _carbon(args.repo)
    _require_localnet()
    from carbon.chain.external_signer import connect_signer
    from carbon.development_session import direct_source_submission as dss
    from carbon.development_session import direct_submission as ds
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    recorder = Recorder(out / "requests.jsonl")
    recipe, contract = _recipe(args.recipe)
    signer = connect_signer(args.hotkey)
    context = carbon_testnet_context()
    spoof = dict(
        [h.split(":", 1)[0].strip(), h.split(":", 1)[1].strip()]
        for h in args.spoof_header
    )
    send = recording_send(recorder, args.client, spoof=spoof)

    def read(url):
        row = {"t_utc": utc(), "client": args.client, "route": "intake", "error": None}
        started = time.monotonic()
        try:
            facts = ds.read_intake(url)
            row["status"] = 200
            return facts
        except ds.DirectIntakeRateLimit:
            row["status"] = 429
            raise
        except urllib.error.HTTPError as refused:
            row["status"] = refused.code
            raise
        except (OSError, ValueError) as failed:
            row.update(status=None, error=type(failed).__name__)
            raise
        finally:
            row["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
            row["done_s"] = time.time()
            recorder.add(row)

    _wait_until(args.start_at_utc)
    started = time.time()
    outcome = {}
    try:
        if args.role == "upload":
            name, body = synthetic_document(
                args.client + ":" + utc(started), args.upload_bytes
            )
            fingerprint = dss._stage_one(
                args.door,
                signer,
                recipe=recipe,
                contract_digest=contract,
                receiver=args.receiver_hotkey,
                context=context,
                name=name,
                body=body,
                expected_digest=None,
                read=read,
                send=send,
                deadline=dss._transfer_deadline([(name, body)], dss.CHUNK_BYTES),
                pacer=dss._UploadPacer(),
            )
            outcome = {
                "outcome": "uploaded",
                "content_digest": fingerprint,
                "bytes": len(body),
            }
        else:
            n = 0
            while time.time() - started < args.duration_s:
                due = started + n / args.rate
                if due > time.time():
                    time.sleep(due - time.time())
                n += 1
                try:
                    ds.read_exam_feedback(
                        args.door,
                        signer,
                        recipe=recipe,
                        contract_digest=contract,
                        receiver=args.receiver_hotkey,
                        context=context,
                        read=read,
                        send=send,
                    )
                except ds.DirectIntakeRefusal:
                    pass  # each attempt is already a row; the counts tell the story
            outcome = {"outcome": "done", "calls": n}
    except ds.DirectIntakeRefusal as refused:
        outcome = {"outcome": "refused", "code": refused.code}
    ended = time.time()
    recorder.close()
    posts = [r for r in recorder.rows if r["route"] == "post"]
    summary = {
        "schema": SCHEMA,
        "mode": "burst",
        "client": args.client,
        "role": args.role,
        "door": args.door,
        "hotkey": args.hotkey,
        "rate": args.rate if args.role == "feedback" else None,
        "spoofed_header": spoof or None,
        "start_utc": utc(started),
        "end_utc": utc(ended),
        "posts": len(posts),
        "status_429": sum(1 for r in posts if r["status"] == 429),
        "status_503": sum(1 for r in posts if r["status"] == 503),
        "resets": sum(1 for r in posts if r["status"] is None),
        "result": outcome,
        "probe_sha256": _probe_digest(),
    }
    print(json.dumps({"client": args.client, "sums": _write_summary(out, summary)}))
    return 0


def merge(dirs):
    """Per-client 429/503 counts, split by whether an upload client was active."""
    clients = []
    for d in map(Path, dirs):
        summary = json.loads((d / "summary.json").read_text("utf-8"))
        rows = [
            json.loads(line)
            for line in (d / "requests.jsonl").read_text("utf-8").splitlines()
            if line
        ]
        clients.append((summary, [r for r in rows if r.get("route") == "post"]))
    uploads = [
        (
            dt.datetime.fromisoformat(s["start_utc"]).timestamp(),
            dt.datetime.fromisoformat(s["end_utc"]).timestamp(),
            s["client"],
        )
        for s, _ in clients
        if s["role"] == "upload"
    ]
    per_client = {}
    for summary, posts in clients:
        during = [p for p in posts if any(a <= p["done_s"] <= b for a, b, _ in uploads)]
        per_client[summary["client"]] = {
            "role": summary["role"],
            "rate": summary["rate"],
            "posts": len(posts),
            "status_429": summary["status_429"],
            "status_503": summary["status_503"],
            "status_429_during_upload": sum(1 for p in during if p["status"] == 429),
            "spoofed_header": summary["spoofed_header"],
            "result": summary["result"],
        }
    honest = [
        c
        for c in per_client.values()
        if c["role"] == "feedback" and c["rate"] is not None and c["rate"] <= 1.0
    ]
    return {
        "schema": MERGE_SCHEMA,
        "uploads": [
            {"client": c, "start_utc": utc(a), "end_utc": utc(b)} for a, b, c in uploads
        ],
        "clients": per_client,
        # Before the fix this should be True (the test bites); after it, False.
        "honest_client_429_during_upload": any(
            c["status_429_during_upload"] for c in honest
        ),
        "honest_clients_zero_429": (
            all(c["status_429"] == 0 for c in honest) if honest else None
        ),
    }


def cmd_merge(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    merged = merge(args.dirs)
    (out / "summary.json").write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "sums": seal(out),
                **{
                    k: merged[k]
                    for k in (
                        "honest_client_429_during_upload",
                        "honest_clients_zero_429",
                    )
                },
            }
        )
    )
    return 0


def parser():
    top = argparse.ArgumentParser(
        prog="door_probe", description=__doc__.split("\n\n")[0]
    )
    sub = top.add_subparsers(dest="cmd", required=True)
    repo_default = str(Path(__file__).resolve().parents[3])

    p = sub.add_parser(
        "probe", help="read-only GET probe (+ optional R13 signed resubmit)"
    )
    p.add_argument(
        "--door", required=True, help="door base URL (spare, staging or canary)"
    )
    p.add_argument("--challenge", required=True)
    p.add_argument("--rate", type=float, default=2.0)
    p.add_argument("--baseline-s", type=float, default=60.0)
    p.add_argument(
        "--duration-s",
        type=float,
        default=900.0,
        help="window cap; a STOP file ends it sooner",
    )
    p.add_argument("--out", required=True, help="new evidence directory")
    p.add_argument(
        "--no-queue", action="store_true", help="door without the queue route"
    )
    p.add_argument(
        "--limits-from",
        help="checkout of the release under test (reads its served limits)",
    )
    p.add_argument("--r13-recipe", help="recipe JSON for the R13 signed resubmit")
    p.add_argument(
        "--hotkey", help="test hotkey ss58 (R13); its signer must be running"
    )
    p.add_argument(
        "--receiver-hotkey",
        help="the door's receiver hotkey ss58 (R13), pinned by the operator",
    )
    p.add_argument(
        "--live-door",
        action="store_true",
        help="R13 on a live testnet door: owner's words first",
    )
    p.add_argument("--repo", default=repo_default)
    p.set_defaults(run=cmd_probe)

    b = sub.add_parser("burst", help="one R89 client (staging localnet only)")
    b.add_argument("--door", required=True)
    b.add_argument("--client", required=True, help="a short name for this client")
    b.add_argument("--role", choices=("upload", "feedback"), required=True)
    b.add_argument(
        "--recipe", required=True, help="a recipe JSON for the door's Challenge"
    )
    b.add_argument("--hotkey", required=True)
    b.add_argument("--receiver-hotkey", required=True)
    b.add_argument("--rate", type=float, default=0.5, help="feedback calls per second")
    b.add_argument("--duration-s", type=float, default=180.0, help="feedback window")
    b.add_argument("--upload-bytes", type=int, default=1024 * 1024)
    b.add_argument("--start-at-utc", help="ISO time all clients start together")
    b.add_argument(
        "--spoof-header",
        action="append",
        default=[],
        help="'Name: value' added to every POST",
    )
    b.add_argument("--out", required=True)
    b.add_argument("--repo", default=repo_default)
    b.set_defaults(run=cmd_burst)

    m = sub.add_parser("merge", help="join burst clients' evidence")
    m.add_argument("--out", required=True)
    m.add_argument("dirs", nargs="+")
    m.set_defaults(run=cmd_merge)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    if (
        args.cmd == "probe"
        and args.r13_recipe
        and not (args.hotkey and args.receiver_hotkey)
    ):
        raise SystemExit("--r13-recipe needs --hotkey and --receiver-hotkey")
    if getattr(args, "rate", 1.0) <= 0:
        raise SystemExit("--rate must be positive")
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
