"""Every change to a construction contract is recorded (OWNER-CHALLENGE-ADMISSION-01 §6.1).

The owner amended OWNER-CHALLENGE-ADMISSION-01 on 1 October 2026. Widening what
a construction may do no longer needs review in advance, and in exchange every
expansion is recorded: what widened, when, and under which contract version.
When a finding escalates, the state reached can then be reviewed and locked down
coherently. An unrecorded expansion cannot be.

The record is enforced by construction rather than by care. Each Challenge's
construction contract (`capability_registry.CONTRACTS`) has an append-only
sequence of records under `expansions/<challenge>/NNNN.json`. Each record
carries:
- the contract's full pinned document and its digest;
- the date and the contract's version and identity;
- a plain statement of what changed.

`tests/cpu/test_construction_expansion_record.py` fails whenever a contract's
live document differs from its newest record. A widening (or a narrowing) that
was not recorded therefore cannot pass CI, and the failure names the command
that records it:

    python -m carbon.reconstruction.expansion_record record \\
        --challenge <token> --what "<what widened, and why>"

`--what` is a person's or agent's statement. The record does not judge whether
the expansion was wise, and it is not a review. It is the trail the review reads
when a run emits a score-value divergence, a failing trigger or a gate anomaly.
Those escalate on their own (§6.2). Nothing here reaches mainnet, and recording
an expansion qualifies nothing.

Pure data and the standard library: importing this module initializes no
numerical runtime.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path

from carbon.reconstruction.capability_registry import CONTRACTS, contract

RECORD_SCHEMA = "carbon.construction-expansion-record.v1"
AUTHORITY = "OWNER-CHALLENGE-ADMISSION-01 (amended 2026-10-01) section 6.1"
ROOT = Path(__file__).with_name("expansions")
_NAME = re.compile(r"[0-9]{4}\.json")


def digest_of(document) -> str:
    """The contract digest of a document, computed exactly as the registry does."""
    body = json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def records(challenge, root: Path = ROOT) -> list[dict]:
    """A Challenge's records, oldest first."""
    folder = root / challenge
    if not folder.is_dir():
        return []
    names = sorted(p.name for p in folder.iterdir() if _NAME.fullmatch(p.name))
    return [json.loads((folder / n).read_text(encoding="utf-8")) for n in names]


def unrecorded(root: Path = ROOT) -> dict[str, str]:
    """{challenge: why} for every contract whose live state is not its newest record."""
    found = {}
    for token in CONTRACTS:
        history = records(token, root)
        if not history:
            found[token] = "no record exists"
            continue
        live = contract(token)
        newest = history[-1]
        if newest["contract_document"] != live.document():
            found[token] = "the live contract differs from record " + str(
                newest["sequence"]
            ).zfill(4)
        elif newest["contract_digest"] != live.digest:
            found[token] = "the newest record's digest is not the live digest"
    return found


def problems(root: Path = ROOT) -> list[str]:
    """Every way the stored records are not a well-formed append-only trail."""
    found = []
    for token in CONTRACTS:
        history = records(token, root)
        for index, record in enumerate(history):
            label = f"{token}/{index:04d}.json"
            if record.get("schema") != RECORD_SCHEMA:
                found.append(label + ": wrong schema")
                continue
            if record.get("sequence") != index:
                found.append(label + ": sequence is not contiguous from 0")
            if record.get("challenge") != token:
                found.append(label + ": names another challenge")
            document = record.get("contract_document")
            if digest_of(document) != record.get("contract_digest"):
                found.append(label + ": digest does not match its document")
            if type(record.get("what")) is not str or len(record["what"].strip()) < 20:
                found.append(label + ": says too little about what changed")
            try:
                datetime.date.fromisoformat(record.get("recorded_on", ""))
            except (TypeError, ValueError):
                found.append(label + ": recorded_on is not a date")
            if index and record.get("recorded_on", "") < history[index - 1].get(
                "recorded_on", ""
            ):
                found.append(label + ": dated before the record it follows")
            if index and document == history[index - 1].get("contract_document"):
                found.append(label + ": records no change")
    return found


def record(challenge, what, *, root: Path = ROOT, today=None) -> Path:
    """Append the live contract of `challenge` as its next record."""
    live = contract(challenge)
    history = records(challenge, root)
    if history and history[-1]["contract_document"] == live.document():
        raise ValueError("nothing to record: the live contract is already recorded")
    if type(what) is not str or len(what.strip()) < 20:
        raise ValueError("say what widened (or narrowed), and why")
    document = live.document()
    entry = {
        "schema": RECORD_SCHEMA,
        "authority": AUTHORITY,
        "challenge": challenge,
        "sequence": len(history),
        "recorded_on": (
            today or datetime.datetime.now(datetime.UTC).date()
        ).isoformat(),
        "contract_version": live.version,
        "contract_identity": live.identity,
        "catalog_version": live.catalog_version,
        "contract_digest": live.digest,
        "what": what.strip(),
        "contract_document": document,
    }
    if digest_of(document) != live.digest:
        raise RuntimeError("the registry's digest rule changed; update digest_of")
    folder = root / challenge
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{entry['sequence']:04d}.json"
    path.write_text(
        json.dumps(entry, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("record", help="record the live contract of one Challenge")
    add.add_argument("--challenge", required=True, choices=sorted(CONTRACTS))
    add.add_argument("--what", required=True)
    sub.add_parser("check", help="list unrecorded contracts and malformed records")
    args = parser.parse_args(argv)
    if args.command == "record":
        print(record(args.challenge, args.what))
        return 0
    issues = [f"{k}: {v}" for k, v in unrecorded().items()] + problems()
    print("\n".join(issues) if issues else "every construction contract is recorded")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
