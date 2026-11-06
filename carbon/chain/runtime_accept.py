"""Weights keep publishing across a chain runtime upgrade when the surface Carbon uses is unchanged (H8, owner 5 Nov).

The chain's runtime upgrades often. Each one used to stop weights: the publisher pinned a runtime SPEC number
(`expected_runtime_spec`) and refused any other until people re-checked and re-pinned it (5 Nov: 486 -> 488, 3.7 h
without weights). The pin is now the USED-SURFACE DIGEST of `runtime_probe`: every call (names, order, raw argument
types), storage value type and runtime API the publish path and the capability snapshot touch, compared with the
pinned SDK's own bindings.

- An AUTO-accepted spec stays in use only while the chain confirms what was published under it: the publisher's own
  read-back (`publisher.reconcile`: LastUpdate past the inclusion and the stored row equal to the target) is counted
  per spec; the first miss alerts, `STOP_AFTER_MISSES` misses refuse that spec until a person re-baselines.
- A BASELINE receipt is written once, on the operator's word: ``baseline`` probes the head and stores
  ``<receipts>/<spec>.json`` (decision BASELINE; only when the probe says COMPATIBLE_USED_SURFACE).
- Every cycle, `resolve` reads the live spec. A spec with an ACCEPTED or BASELINE receipt is used as is. A NEW spec
  is probed at once: COMPATIBLE and the same surface digest as the baseline -> an ACCEPTED receipt, a journal line,
  and the cycle publishes with the new spec (no gap). Anything else refuses BEFORE any wallet or signing
  (`RuntimeRefused("UNSUPPORTED_RUNTIME_SURFACE")`; the harm: a malformed or wrong-meaning extrinsic) and writes ONE
  alert with the item differences, rewritten only when the observed digest changes.

The probe's own limit stays in every receipt: names and types are unchanged, the runtime's BEHAVIOUR is not verified.
Nothing here opens a wallet, signs or submits.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

RECEIPT_DIR = "runtime-receipts"
ALERT_NAME = "runtime-alert.json"
SCHEMA = "carbon.chain.runtime-acceptance.v1"
ACCEPTED, BASELINE, REFUSED = "ACCEPTED", "BASELINE", "REFUSED"
COMPATIBLE = "COMPATIBLE_USED_SURFACE"


class RuntimeRefused(Exception):
    """The live runtime is not one this publisher may sign for (closed code)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def store_for(journal) -> Path:
    """The receipt store beside the publication journal."""
    return Path(journal).absolute().parent / RECEIPT_DIR


def _write(path, body):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.{os.getpid()}")
    staged.write_text(json.dumps(body, sort_keys=True, indent=1), encoding="utf-8")
    os.chmod(staged, 0o600)
    os.replace(staged, path)


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if type(value) is dict and value.get("schema") == SCHEMA else None


def receipt(store, spec):
    return _read(Path(store) / f"{int(spec)}.json")


def _receipt_body(report, decision, *, reason=None):
    return {
        "schema": SCHEMA,
        "spec_version": report["spec_version"],
        "decision": decision,
        "probe_status": report["status"],
        "surface_digest": report["surface_digest"],
        "differences": report.get("differences", []),
        "context": report.get("context", {}),
        "at_ns": time.time_ns(),
        "reason": reason,
        "claims": {
            "names_and_types_unchanged": True,
            "runtime_behaviour_verified": False,
        },
    }


def baseline(store, report):
    """Record the operator-approved runtime (its probe report) as the surface every later spec must match."""
    if report.get("status") != COMPATIBLE:
        raise RuntimeRefused("BASELINE_NOT_COMPATIBLE")
    body = _receipt_body(report, BASELINE)
    _write(Path(store) / f"{int(report['spec_version'])}.json", body)
    return body


def _baseline_digest(store):
    """The surface digest every accepted spec shares (one, by construction); None before any baseline."""
    digests = set()
    try:
        names = sorted(Path(store).glob("*.json"))
    except OSError:
        return None
    for path in names:
        body = _read(path)
        if body is not None and body["decision"] in (BASELINE, ACCEPTED):
            digests.add(body["surface_digest"])
    if len(digests) > 1:
        raise RuntimeRefused("RUNTIME_RECEIPTS_DISAGREE")
    return next(iter(digests), None)


#: A dispatch published under an auto-accepted spec that the chain then shows wrong (`publisher.reconcile`'s read-back).
MISS_STATES = frozenset({"CHAIN_REJECTED", "EXPOSURE_CHANGED"})
MISS_REASONS = frozenset({"STORED_ROW_DIFFERS_FROM_TARGET"})
#: The first miss alerts; this many stop auto-acceptance of that spec until a person re-baselines (Validator-2 19:07).
STOP_AFTER_MISSES = 2


def readback_misses(journal, spec):
    """How many dispatches made under ``spec`` the chain read-back did not confirm: CHAIN_REJECTED, EXPOSURE_CHANGED, or
    a finalized row whose stored weights differ from the target (`publisher.reconcile`). Read-only; 0 when the journal
    has no dispatch table yet."""
    import sqlite3

    path = Path(journal).absolute()
    if not path.exists():
        return 0
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = db.execute(
                "SELECT document, state, tracking FROM publication_v1"
            ).fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return 0
    misses = 0
    for document, state, tracking in rows:
        try:
            caps = json.loads(document).get("capabilities") or {}
            reason = (json.loads(tracking) or {}).get("reason")
        except (ValueError, AttributeError):
            continue
        if caps.get("spec_version") != int(spec):
            continue
        if state in MISS_STATES or reason in MISS_REASONS:
            misses += 1
    return misses


def _readback_guard(store, journal, spec, note):
    """An AUTO-accepted spec keeps being used only while the chain confirms what was published under it."""
    body = receipt(store, spec)
    if body is None or body["decision"] != ACCEPTED or journal is None:
        return
    misses = readback_misses(journal, spec)
    if misses and not body.get("readback_alerted"):
        _write(Path(store) / f"{int(spec)}.json", {**body, "readback_alerted": misses})
        note(
            "operator_alert",
            code="runtime_readback_miss",
            spec_version=int(spec),
            misses=misses,
        )
    if misses >= STOP_AFTER_MISSES:
        raise RuntimeRefused("RUNTIME_READBACK_FAILED")


def decide(store, live_spec, configured_spec, probe, *, log=None, journal=None):
    """The spec this cycle may publish under, or `RuntimeRefused` (before any wallet).

    ``probe`` is a callable returning a `runtime_probe.compare` report for the live head (called only for a spec
    with no receipt). ``configured_spec`` is the operator's/owner's pinned number: used as is before any baseline
    exists (the old behaviour), so nothing changes until the owner records one.
    """
    note = log or (lambda *_a, **_k: None)
    known = receipt(store, live_spec)
    if known is not None and known["decision"] in (BASELINE, ACCEPTED):
        _readback_guard(store, journal, live_spec, note)
        return int(live_spec)
    base = _baseline_digest(store)
    if base is None:
        if live_spec == configured_spec:
            return int(live_spec)
        raise RuntimeRefused("RUNTIME_BASELINE_MISSING")
    report = probe()
    if int(report.get("spec_version", -1)) != int(live_spec):
        raise RuntimeRefused("RUNTIME_CHANGED_DURING_PROBE")
    if report.get("status") == COMPATIBLE and report.get("surface_digest") == base:
        _write(Path(store) / f"{int(live_spec)}.json", _receipt_body(report, ACCEPTED))
        note(
            "runtime_auto_accepted",
            spec_version=int(live_spec),
            surface_digest=base,
        )
        return int(live_spec)
    alert_path = Path(store) / ALERT_NAME
    previous = _read(alert_path)
    if previous is None or previous.get("surface_digest") != report.get(
        "surface_digest"
    ):
        _write(
            alert_path,
            _receipt_body(
                report,
                REFUSED,
                reason=(
                    "surface_changed"
                    if report.get("status") == COMPATIBLE
                    else "incompatible_with_sdk"
                ),
            )
            | {"baseline_digest": base},
        )
        note(
            "operator_alert",
            code="runtime_surface_changed",
            spec_version=int(live_spec),
            surface_digest=report.get("surface_digest"),
            baseline_digest=base,
            differences=len(report.get("differences", [])),
        )
    raise RuntimeRefused("UNSUPPORTED_RUNTIME_SURFACE")


async def live_spec(endpoint):
    """The finalized head's runtime spec version (one read; nothing signed)."""
    import bittensor as bt

    substrate = bt.RpcSubstrate(endpoint, fallback_endpoints=[], archive_endpoints=[])
    await substrate.connect()
    try:
        raw = substrate.raw
        head = await raw.get_chain_finalised_head()
        version = await raw.rpc_request("state_getRuntimeVersion", [head])
    finally:
        await substrate.close()
    return int(version["specVersion"])


def has_baseline(journal) -> bool:
    """Whether an operator-approved baseline exists beside this journal (before one, nothing here runs)."""
    return _baseline_digest(store_for(journal)) is not None


async def resolve(endpoint, genesis_hash, configured_spec, journal, *, log=None):
    """`decide` against the live chain (the publish paths call this before any issuer or wallet). The head is
    probed only for a new spec with no receipt once a baseline exists."""
    from . import runtime_probe

    store = store_for(journal)
    if _baseline_digest(store) is None:
        # no baseline yet: exactly the old behaviour (the configured pin decides in the publisher); no chain read
        return int(configured_spec)
    spec = await live_spec(endpoint)
    known = receipt(store, spec)
    report = None
    if not (known and known["decision"] in (BASELINE, ACCEPTED)) and _baseline_digest(
        store
    ):
        report = await runtime_probe.probe(endpoint, genesis_hash)
    return decide(
        store, spec, configured_spec, lambda: report, log=log, journal=journal
    )


def main(argv=None):
    """``baseline --config OPERATOR_CONFIG --journal JOURNAL``: record the live runtime as the accepted surface."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(prog="python -m carbon.chain.runtime_accept")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--config", type=Path, required=True)
    b.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args(argv)
    from carbon.development_testnet.operator import load_config

    from . import runtime_probe

    config = load_config(args.config.absolute())
    report = asyncio.run(runtime_probe.probe(config.endpoint, config.genesis_hash))
    try:
        body = baseline(store_for(args.journal), report)
    except RuntimeRefused as refused:
        print(
            json.dumps(
                {
                    "state": "REFUSED",
                    "code": refused.code,
                    "status": report.get("status"),
                }
            )
        )
        return 3
    print(
        json.dumps(
            {
                "state": BASELINE,
                "spec_version": body["spec_version"],
                "surface_digest": body["surface_digest"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
