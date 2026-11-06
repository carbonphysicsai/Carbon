"""Weights keep publishing across a chain runtime upgrade when the surface Carbon uses is unchanged (H8, owner 5 Nov).

The chain's runtime upgrades often. Each one used to stop weights: the publisher pinned a runtime SPEC number
(`expected_runtime_spec`) and refused any other until people re-checked and re-pinned it (5 Nov: 486 -> 488, 3.7 h
without weights). The pin is now the USED-SURFACE DIGEST of `runtime_probe`: every call (names, order, raw argument
types), storage value type and runtime API the publish path and the capability snapshot touch, compared with the
pinned SDK's own bindings.

- ONE current BASELINE (``baseline.json``), written on the operator's word by ``baseline``: only for the spec the
  owner's pins name (the operator config's and the standing authorization's ``expected_runtime_spec``) and only when
  the probe says COMPATIBLE_USED_SURFACE. A later ``baseline`` REPLACES it (a reviewed surface change).
- Every cycle `resolve` reads the live spec and the runtime code's own hash (``:code``). The baseline runtime is used
  as is. Any other runtime is accepted when an ACCEPTED receipt for that exact (spec, code hash) was recorded against
  the current baseline digest; else it is probed at once, and accepted only if COMPATIBLE with the baseline's digest
  (a receipt is written and the cycle publishes under it: no gap). Anything else refuses BEFORE any wallet or signing
  (``UNSUPPORTED_RUNTIME_SURFACE``; the harm: a malformed or wrong-meaning extrinsic) and writes ONE alert with the item
  differences, rewritten only when the observed digest changes, cleared when a runtime is accepted.
- An AUTO-accepted runtime stays in use only while the publisher's own read-back (`publisher.reconcile`: LastUpdate past
  the inclusion and the stored row equal to the target) confirms what was published under it: the first miss alerts,
  `STOP_AFTER_MISSES` misses refuse it until a person re-baselines.
- The store is owner-only: a receipt that is a link, another user's, or readable by group/other is refused; every
  receipt names the chain's genesis and must match the publisher's.

The probe's own limit stays in every receipt: names and types are unchanged, the runtime's BEHAVIOUR is not verified;
the capability VALUE checks before signing and the read-back after cover behaviour. Nothing here opens a wallet, signs or
submits.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

RECEIPT_DIR = "runtime-receipts"
BASELINE_NAME = "baseline.json"
ALERT_NAME = "runtime-alert.json"
SCHEMA = "carbon.chain.runtime-acceptance.v2"
ACCEPTED, BASELINE, REFUSED = "ACCEPTED", "BASELINE", "REFUSED"
COMPATIBLE = "COMPATIBLE_USED_SURFACE"
#: The runtime's own Wasm (``:code``): its storage hash names the exact runtime, not only its spec number.
CODE_KEY = "0x3a636f6465"
#: A dispatch published under an auto-accepted runtime that the chain then shows wrong (`publisher.reconcile`).
MISS_STATES = frozenset({"CHAIN_REJECTED", "EXPOSURE_CHANGED"})
MISS_REASONS = frozenset({"STORED_ROW_DIFFERS_FROM_TARGET"})
#: The first miss alerts; this many refuse the runtime until a person re-baselines (Validator-2, 5 Nov 19:07).
STOP_AFTER_MISSES = 2


class RuntimeRefused(Exception):
    """The live runtime is not one this publisher may sign for (closed code)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def stderr_log(event, **fields):
    """One JSON line on stderr per decision (stdout stays the publisher's one result line)."""
    print(
        json.dumps({"event": event, **fields}, sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def store_for(journal) -> Path:
    """The receipt store beside the publication journal."""
    return Path(journal).absolute().parent / RECEIPT_DIR


def _owner_only(path, *, directory):
    """False when absent. Refuses a link, another user's entry or one group/other can read (the rule `load_standing`
    applies to the owner's standing file)."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    kind_ok = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (
        stat.S_ISLNK(info.st_mode)
        or not kind_ok
        or (
            os.name == "posix" and (info.st_uid != os.geteuid() or info.st_mode & 0o077)
        )
    ):
        raise RuntimeRefused("RUNTIME_RECEIPT_NOT_OWNER_ONLY")
    return True


def _write(path, body):
    path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(mode=0o700, parents=True)
    _owner_only(path.parent, directory=True)
    staged = path.with_name(f".{path.name}.{os.getpid()}")
    staged.write_text(json.dumps(body, sort_keys=True, indent=1), encoding="utf-8")
    os.chmod(staged, 0o600)
    os.replace(staged, path)


def _read(path):
    path = Path(path)
    if not _owner_only(path.parent, directory=True) or not _owner_only(
        path, directory=False
    ):
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if type(value) is dict and value.get("schema") == SCHEMA else None


def _receipt_name(spec, code_hash):
    code = str(code_hash)
    return f"{int(spec)}-{code[2:18] if code.startswith('0x') else code[:16]}.json"


def receipt(store, spec, code_hash):
    return _read(Path(store) / _receipt_name(spec, code_hash))


def current_baseline(store):
    return _read(Path(store) / BASELINE_NAME)


def has_baseline(journal) -> bool:
    """Whether an operator-approved baseline exists beside this journal (before one, nothing here runs)."""
    return current_baseline(store_for(journal)) is not None


def _body(
    report, decision, *, genesis_hash, code_hash, baseline_digest=None, reason=None
):
    return {
        "schema": SCHEMA,
        "spec_version": int(report["spec_version"]),
        "code_hash": code_hash,
        "genesis_hash": genesis_hash,
        "decision": decision,
        "probe_status": report["status"],
        "surface_digest": report["surface_digest"],
        "baseline_digest": baseline_digest,
        "differences": report.get("differences", []),
        "context": report.get("context", {}),
        "at_ns": time.time_ns(),
        "reason": reason,
        "claims": {
            "names_and_types_unchanged": report["status"] == COMPATIBLE,
            "runtime_behaviour_verified": False,
        },
    }


def baseline(store, report, *, owner_specs, genesis_hash, code_hash):
    """Record the operator-approved runtime as THE surface every later runtime must match (replaces any earlier one).
    Only the spec every one of the owner's pins names (``owner_specs``: the operator config's and the standing
    authorization's), and only a COMPATIBLE one."""
    if report.get("status") != COMPATIBLE:
        raise RuntimeRefused("BASELINE_NOT_COMPATIBLE")
    if not owner_specs or any(
        int(report["spec_version"]) != int(spec) for spec in owner_specs
    ):
        raise RuntimeRefused("BASELINE_NOT_THE_OWNERS_SPEC")
    body = _body(report, BASELINE, genesis_hash=genesis_hash, code_hash=code_hash)
    _write(Path(store) / BASELINE_NAME, body)
    alert = Path(store) / ALERT_NAME
    if alert.exists():
        alert.unlink()
    return body


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


def _readback_guard(store, journal, known, note):
    """An AUTO-accepted runtime keeps being used only while the chain confirms what was published under it."""
    if journal is None:
        return
    misses = readback_misses(journal, known["spec_version"])
    path = Path(store) / _receipt_name(known["spec_version"], known["code_hash"])
    if misses and not known.get("readback_alerted"):
        _write(path, {**known, "readback_alerted": misses})
        note(
            "operator_alert",
            code="runtime_readback_miss",
            spec_version=known["spec_version"],
            misses=misses,
        )
    if misses >= STOP_AFTER_MISSES:
        raise RuntimeRefused("RUNTIME_READBACK_FAILED")


def decide(store, live_spec, live_code, genesis_hash, probe, *, log=None, journal=None):
    """The spec this cycle may publish under, or `RuntimeRefused` (before any wallet). ``probe`` returns a
    `runtime_probe.compare` report for the live head; it is called only for a runtime with no valid receipt.
    """
    note = log or (lambda *_a, **_k: None)
    base = current_baseline(store)
    if base is None:
        raise RuntimeRefused("RUNTIME_BASELINE_MISSING")
    if base.get("genesis_hash") != genesis_hash:
        raise RuntimeRefused("RUNTIME_BASELINE_OTHER_CHAIN")
    if int(live_spec) == base["spec_version"] and live_code == base["code_hash"]:
        return int(live_spec)
    known = receipt(store, live_spec, live_code)
    if (
        known is not None
        and known["decision"] == ACCEPTED
        and known["baseline_digest"] == base["surface_digest"]
        and known["genesis_hash"] == genesis_hash
        and known["code_hash"] == live_code
    ):
        _readback_guard(store, journal, known, note)
        return int(live_spec)
    report = probe()
    if report is None or int(report.get("spec_version", -1)) != int(live_spec):
        raise RuntimeRefused("RUNTIME_CHANGED_DURING_PROBE")
    alert_path = Path(store) / ALERT_NAME
    if (
        report.get("status") == COMPATIBLE
        and report.get("surface_digest") == base["surface_digest"]
    ):
        _write(
            Path(store) / _receipt_name(live_spec, live_code),
            _body(
                report,
                ACCEPTED,
                genesis_hash=genesis_hash,
                code_hash=live_code,
                baseline_digest=base["surface_digest"],
            ),
        )
        if alert_path.exists():
            alert_path.unlink()  # an accepted runtime clears the alert, so a later change alerts again
        note(
            "runtime_auto_accepted",
            spec_version=int(live_spec),
            code_hash=live_code,
            surface_digest=base["surface_digest"],
        )
        return int(live_spec)
    previous = _read(alert_path)
    if previous is None or previous.get("surface_digest") != report.get(
        "surface_digest"
    ):
        reason = (
            "surface_changed"
            if report.get("status") == COMPATIBLE
            else "incompatible_with_sdk"
        )
        _write(
            alert_path,
            _body(
                report,
                REFUSED,
                genesis_hash=genesis_hash,
                code_hash=live_code,
                baseline_digest=base["surface_digest"],
                reason=reason,
            ),
        )
        note(
            "operator_alert",
            code="runtime_surface_changed",
            spec_version=int(live_spec),
            surface_digest=report.get("surface_digest"),
            baseline_digest=base["surface_digest"],
            differences=len(report.get("differences", [])),
        )
    raise RuntimeRefused("UNSUPPORTED_RUNTIME_SURFACE")


async def live_runtime(endpoint):
    """``(spec_version, code_hash)`` at the finalized head (two reads; nothing signed)."""
    import bittensor as bt

    substrate = bt.RpcSubstrate(endpoint, fallback_endpoints=[], archive_endpoints=[])
    await substrate.connect()
    try:
        raw = substrate.raw
        head = await raw.get_chain_finalised_head()
        version = await raw.rpc_request("state_getRuntimeVersion", [head])
        code_hash = await raw.rpc_request("state_getStorageHash", [CODE_KEY, head])
    finally:
        await substrate.close()
    if type(code_hash) is not str or not code_hash.startswith("0x"):
        raise RuntimeRefused("RUNTIME_CODE_HASH_UNREADABLE")
    return int(version["specVersion"]), code_hash


async def resolve(endpoint, genesis_hash, journal, *, log=stderr_log):
    """`decide` against the live chain (the publish paths call this, after their offline refusals and before any
    wallet, only when a baseline exists). The head is probed only for a runtime with no valid receipt.
    """
    from . import runtime_probe

    store = store_for(journal)
    spec, code_hash = await live_runtime(endpoint)
    reports = []
    base = current_baseline(store)
    if base is not None and not (
        spec == base["spec_version"] and code_hash == base["code_hash"]
    ):
        known = receipt(store, spec, code_hash)
        if known is None or known.get("baseline_digest") != base["surface_digest"]:
            reports.append(await runtime_probe.probe(endpoint, genesis_hash))
    return decide(
        store,
        spec,
        code_hash,
        genesis_hash,
        lambda: reports[0] if reports else None,
        log=log,
        journal=journal,
    )


def main(argv=None):
    """``baseline --config OPERATOR_CONFIG --standing STANDING --journal JOURNAL``: record the live runtime as THE
    accepted surface; only the spec both of the owner's pins name, only when the probe says COMPATIBLE.
    """
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(prog="python -m carbon.chain.runtime_accept")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--config", type=Path, required=True)
    b.add_argument("--standing", type=Path, required=True)
    b.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args(argv)
    from carbon.development_testnet.operator import load_config
    from carbon.rewards.testnet_winner_publication import load_standing

    from . import runtime_probe

    config = load_config(args.config.absolute())
    standing = load_standing(args.standing.absolute(), config.context)

    async def read():
        live = await live_runtime(config.endpoint)
        return live, await runtime_probe.probe(config.endpoint, config.genesis_hash)

    (spec, code_hash), report = asyncio.run(read())
    try:
        if int(report["spec_version"]) != spec:
            raise RuntimeRefused("RUNTIME_CHANGED_DURING_PROBE")
        body = baseline(
            store_for(args.journal),
            report,
            owner_specs=(config.expected_runtime_spec, standing.expected_runtime_spec),
            genesis_hash=config.genesis_hash,
            code_hash=code_hash,
        )
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
                "code_hash": code_hash,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
