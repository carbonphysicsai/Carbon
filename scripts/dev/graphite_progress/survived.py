"""The scope record generator (SURVIVED-RECORD-DEFINITION-01): read-only, append-only.

An item enters scope once it is TESTED (scored and rebuild-proven at its level); attacks then subtract. This module
joins four sources and writes two outputs, all development evidence (the claims block is fixed false):

- the progress ledger and the backfill manifests (`attack-*.json`: triage, `finding_fixes`, optional `reattack`);
- each attacker root's `reports/*/coverage.json` and controller (`findings`, `finding_states`), opened read-only;
- a committed `item_families.json` (which attack families defend which item, and which ledger lines tested it).

Outputs: an append-only `survived-record.jsonl` (outside the repository, beside `progress.jsonl`) and a deterministic,
digest-pinned snapshot (committed, for the register). A record's digest excludes `recorded_at` and `supersedes`, so a
rerun on unchanged evidence appends nothing; changed evidence appends a new record that `supersedes` the last.

The level of a finding's construction is DERIVED from the construction (the unified classifier), never taken from the
session that produced it; a mismatch is kept (`recorded_level`) and flagged. Nothing here carries a balance, an
account id or a spend figure, and nothing says secure, qualified or accepted.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

RECORD_SCHEMA = "carbon.graphite.survived-record.v1"
REMOVAL_SCHEMA = "carbon.graphite.scope-removal.v1"
SNAPSHOT_SCHEMA = "carbon.graphite.survived-snapshot.v1"
LIFECYCLE_POLICY = "carbon.graphite.finding-lifecycle.v2"
CLAIMS = {
    "security_acceptance": False,
    "qualified": False,
    "accepted": False,
    "authority_granted": False,
}
NOT_ATTACKED = "NOT_ATTACKED"
TESTED_ONLY = "TESTED_ONLY"
OPEN_FINDING = "ATTACKED_OPEN_FINDING"
HELD = "ATTACKED_HELD"
ATTEMPTED = "ATTEMPTED_COVERAGE"
UNTRIAGED = "UNTRIAGED"
#: A triage verdict that is an open finding until fixed and re-attacked. ORACLE_GAP and FALSE_POSITIVE are an oracle
#: defect and noise: they keep an item at TESTED_ONLY (no removal) until the re-attack, they are never "open".
OPEN_VERDICTS = frozenset({UNTRIAGED, "REAL_ESCAPE"})
REMOVAL_REASONS = {"REAL_ESCAPE": "REAL_ESCAPE_UNFIXED"}
#: Known reds that are expected, with their cause (the snapshot carries them so no one fixes the wrong thing).
KNOWN_REDS = (
    {
        "id": "R5_ATTACKER",
        "text": (
            "R5 for the attacker role fails by design: attacker_budget reserves six verify pods while Carbon's "
            "verify-pod rebuild is an open seam (carbon_verify_pod_rebuild, NOT_RUN) and the live attacker launches "
            "no pod. It is expected to pass once the rebuild lands; until then it is a known red, not a defect to "
            "fix in the budget."
        ),
        "seam": "carbon_verify_pod_rebuild",
    },
)
_RANK = {ATTEMPTED: 0, "FINDING": 1, "INCONCLUSIVE": 2, "NOT_RUN": 3}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


# -- sources ----------------------------------------------------------------------------------
def load_ledger(path):
    """The progress ledger lines, newest wins per (batch, level)."""
    lines = {}
    for text in Path(path).read_text(encoding="utf-8").splitlines():
        if text.strip():
            row = json.loads(text)
            lines[(row.get("batch"), row.get("level"))] = row
    return list(lines.values())


def load_manifests(directory):
    """`(triage, fixes, reattacks, sources)` over every attack backfill manifest, finding id keyed."""
    triage, fixes, reattack, sources = {}, {}, {}, []
    for path in sorted(Path(directory).glob("attack-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        batch = document.get("batch")
        sources.append({"manifest": path.name, "digest": file_digest(path)})
        for finding_id, verdict in (document.get("triage") or {}).items():
            triage[finding_id] = {
                "verdict": verdict,
                "batch": batch,
                "source": document.get("triage_source"),
            }
        fixes.update(document.get("finding_fixes") or {})
        reattack.update(document.get("reattack") or {})
    return triage, fixes, reattack, sources


def _connect(path):
    return sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)


def _finding_verdict(controller, reference, finding_id):
    """Read registered evidence or refuse before any record can be emitted."""
    try:
        relative = reference["path"]
        if (
            not isinstance(relative, str)
            or "\\" in relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ValueError
        path = controller / relative
        if not path.resolve().is_relative_to(controller.resolve()):
            raise ValueError
        raw = path.read_bytes()
        if reference["sha256"] != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise ValueError
        verdict = json.loads(raw)["verdict"]
        if not isinstance(verdict, dict) or not isinstance(verdict.get("family"), str):
            raise TypeError
        if not verdict["family"].strip():
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError):
        raise ValueError(
            "finding_evidence_unavailable_or_invalid:" + finding_id
        ) from None
    return verdict


def read_attack_root(store):
    """One attacker store read-only: `{reports, findings, repairs}`. Never writes."""
    store = Path(store)
    reports = []
    for path in sorted(store.glob("reports/*/coverage.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        reports.append(
            {
                "ref": f"{store.parent.name}:{path.parent.name}",
                "digest": file_digest(path),
                "document": document,
            }
        )
    findings, repairs = [], []
    controller = store / "controller"
    database = controller / "campaign.sqlite3"
    if database.is_file():
        with _connect(database) as db:
            for finding_id, body in db.execute(
                "SELECT id, body FROM findings ORDER BY ordinal"
            ):
                row = json.loads(body)
                evidence = row.get("evidence") or {}
                verdict = _finding_verdict(controller, evidence, finding_id)
                findings.append(
                    {
                        "finding_id": finding_id,
                        "family": verdict.get("family"),
                        "attempt": verdict.get("attempt"),
                        "authority": verdict.get("authority"),
                        "conditions": list(verdict.get("conditions") or []),
                        "outcome": verdict.get("outcome"),
                        "root": store.parent.name,
                        "evidence_digest": evidence["sha256"],
                    }
                )
            latest, repaired_once = {}, set()
            for seq, finding_id, state, body in db.execute(
                "SELECT seq, finding, state, body FROM finding_states ORDER BY seq"
            ):
                detail = json.loads(body)
                current = {
                    "controller_state": state,
                    "controller_state_seq": seq,
                    "recurred_after_repair": False,
                }
                if state == "REPAIRED":
                    repaired_once.add(finding_id)
                    repairs.append(
                        {
                            "finding_id": finding_id,
                            "root": store.parent.name,
                            "state_seq": seq,
                            "repair_id": detail.get("repair_id"),
                            "rerun": list(detail.get("rerun") or []),
                            "code_ref": detail.get("code_ref"),
                        }
                    )
                elif state == "RECURRED":
                    evidence = detail.get("evidence") or {}
                    verdict = _finding_verdict(controller, evidence, finding_id)
                    current.update(
                        recurred_after_repair=finding_id in repaired_once,
                        recurrence_family=verdict["family"],
                        recurrence_evidence_digest=evidence["sha256"],
                    )
                else:
                    raise ValueError("finding_state_invalid:" + finding_id)
                latest[finding_id] = current
            for finding in findings:
                finding.update(latest.get(finding["finding_id"], {}))
                if (
                    finding.get("controller_state") == "RECURRED"
                    and finding["recurrence_family"] != finding["family"]
                ):
                    raise ValueError(
                        "finding_recurrence_family_mismatch:" + finding["finding_id"]
                    )
    return {"reports": reports, "findings": findings, "repairs": repairs}


# -- derivation -------------------------------------------------------------------------------
def derived_label(strategy):
    """The level label derived from the construction itself (the unified classifier; absent fields are Level 0), or
    None when it cannot be derived."""
    if strategy is None:
        return None
    try:
        from carbon.battery import unified_contract
        from carbon.development_session import unified_construction

        return unified_construction.derive(strategy, unified_contract.contract())[
            "derived_label"
        ]
    except Exception:  # noqa: BLE001 - underivable: keep the recorded level, flagged
        return None


def _family_row(reports, level, family):
    """The best evidence row for one family among the reports at `level`: the most attempts, then the best status."""
    best = None
    for report in reports:
        document = report["document"]
        if document.get("construction_level") != level:
            continue
        row = ((document.get("families") or {}).get("families") or {}).get(family)
        if row is None:
            continue
        stop = document.get("stop_rule_outcome") or {}
        candidate = {
            "status": row.get("status"),
            "attempts": row.get("budget_used") or 0,
            "held": row.get("held") or 0,
            "verified": row.get("verified") or 0,
            "inconclusive_reason": row.get("inconclusive"),
            "not_run_reason": row.get("not_run"),
            "stop": stop.get("status"),
            "k": stop.get("k"),
            "report_ref": report["ref"],
            "report_digest": report["digest"],
        }
        key = (candidate["attempts"], -_RANK.get(candidate["status"], 9))
        if best is None or key > best[0]:
            best = (key, candidate)
    return None if best is None else best[1]


def _scored(item, ledger):
    """The ledger evidence that TESTED the item (scored and rebuilt at its level); None when there is none."""
    refs = []
    for wanted in item.get("scored_ledger") or []:
        for row in ledger:
            if (
                row.get("batch") == wanted["batch"]
                and row.get("level") == wanted["level"]
            ):
                constructor = row.get("constructor") or {}
                share = (constructor.get("bundled_share") or {}).get("value")
                refs.append(
                    {
                        "batch": row["batch"],
                        "level": row["level"],
                        "constructor_runs": constructor.get("runs"),
                        "proposals": constructor.get("proposals"),
                        "bundled_share": share,
                    }
                )
    scored = [
        r
        for r in refs
        if r["constructor_runs"]
        and isinstance(r["bundled_share"], (int, float))
        and r["bundled_share"] > 0
    ]
    return (refs if scored else None), bool(scored)


def _held(row):
    return (
        row["status"] == ATTEMPTED
        and (row["k"] is not None and row["attempts"] >= row["k"])
        and row["held"] >= 1
        and row["stop"] == "DONE"
    )


def _clean_reattack(finding, fix, reattack, family):
    """An explicit post-fix linkage to this finding and this clean report version."""
    return bool(
        isinstance(fix, str)
        and fix.strip()
        and isinstance(reattack, dict)
        and reattack.get("fix_ref") == fix
        and reattack.get("family") == finding["family"]
        and finding.get("evidence_digest")
        and reattack.get("finding_evidence_digest") == finding["evidence_digest"]
        and family["report_ref"]
        and reattack.get("report_ref") == family["report_ref"]
        and reattack.get("report_digest") == family["report_digest"]
        and finding.get("controller_state") != "RECURRED"
        and family["verified"] == 0
        and _held(family)
    )


def build_item(
    item,
    *,
    ledger,
    reports,
    findings,
    triage,
    fixes,
    reattack,
    repairs,
    strategy_of=lambda finding: None,
):
    """The record for one item, or `(None, reason)` when it is not TESTED (not in scope)."""
    refs, tested = _scored(item, ledger)
    if not tested:
        return None, "no scored and rebuild-proven ledger evidence for the item's level"
    level = item["level"]
    families = {}
    for family in item["families"]:
        families[family] = _family_row(reports, level, family) or {
            "status": "NOT_RUN",
            "attempts": 0,
            "held": 0,
            "verified": 0,
            "inconclusive_reason": None,
            "not_run_reason": "no report at this level names the family",
            "stop": None,
            "k": None,
            "report_ref": None,
            "report_digest": None,
        }
    mine = []
    for finding in findings:
        if finding["family"] not in item["families"]:
            continue
        verdict = (triage.get(finding["finding_id"]) or {}).get("verdict", UNTRIAGED)
        strategy = strategy_of(finding)
        label = derived_label(strategy)
        fix = fixes.get(finding["finding_id"])
        re_attack = reattack.get(finding["finding_id"])
        mine.append(
            {
                **finding,
                "triage": verdict,
                "triage_source": (triage.get(finding["finding_id"]) or {}).get(
                    "source"
                ),
                "fix_ref": fix,
                "re_attack_ref": re_attack,
                "clean_reattack": _clean_reattack(
                    finding, fix, re_attack, families[finding["family"]]
                ),
                "repaired": finding.get("controller_state") == "REPAIRED",
                "recorded_level": level,
                "derived_level": label,
                "level_label_mismatch": label is not None and label != level,
            }
        )
    open_findings = [
        f
        for f in mine
        if f["triage"] in OPEN_VERDICTS and not (f["repaired"] or f["clean_reattack"])
    ]
    awaiting_reattack = [
        f for f in mine if f["triage"] == "ORACLE_GAP" and not f["clean_reattack"]
    ]
    reasons = []
    if open_findings:
        status = OPEN_FINDING
        reasons.append("open: " + ", ".join(f["finding_id"] for f in open_findings))
    elif all(
        row["attempts"] == 0 and row["status"] in ("NOT_RUN", "INCONCLUSIVE")
        for row in families.values()
    ):
        status = NOT_ATTACKED
        reasons.append("no mapped family has an attempt")
    else:
        blockers = []
        for name, row in families.items():
            if not _held(row):
                blockers.append(f"{name}: {row['status']}")
        if awaiting_reattack:
            blockers.extend(
                f"{f['finding_id']}: ORACLE_GAP awaiting a re-attack"
                for f in awaiting_reattack
            )
        status = TESTED_ONLY if blockers else HELD
        reasons = blockers or ["every mapped family held at the recorded attack set"]
    stops = sorted({row["k"] for row in families.values() if row["k"] is not None})
    record = {
        "schema": RECORD_SCHEMA,
        "finding_lifecycle_policy": LIFECYCLE_POLICY,
        "item_id": item["item_id"],
        "level": level,
        "level_basis": "descriptive; findings carry a derived level label",
        "construction_family": item["construction_family"],
        "challenge": item["challenge"],
        "entry": {
            "state": "TESTED",
            "evidence": refs,
            "exercise_tag": "level-granular: the ledger records sessions, not which item a scored recipe exercised",
        },
        "attack_set": {
            "coverage_schema": "carbon.graphite.attacker-coverage.v7",
            "k_values": stops,
            "families": sorted(item["families"]),
        },
        "families": {name: families[name] for name in sorted(families)},
        "findings": sorted(mine, key=lambda f: f["finding_id"]),
        "open_finding_count": len(open_findings),
        "repair_attestations": sorted(repairs, key=lambda r: r["finding_id"]),
        "status": status,
        "status_reason": reasons,
        "claims": dict(CLAIMS),
    }
    record["record_digest"] = digest(record)
    return record, None


# -- outputs ----------------------------------------------------------------------------------
def append_records(path, records, *, now):
    """Append the records whose digest is new; each supersedes the item's latest earlier record. Returns the
    appended lines."""
    path = Path(path)
    existing = []
    if path.exists():
        existing = [
            json.loads(t)
            for t in path.read_text(encoding="utf-8").splitlines()
            if t.strip()
        ]
    latest = {}
    for row in existing:
        latest[row["item_id"]] = row
    stamp = now().astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    appended = []
    for record in records:
        before = latest.get(record["item_id"])
        if before is not None and before["record_digest"] == record["record_digest"]:
            continue
        line = {
            **record,
            "recorded_at": stamp,
            "supersedes": None if before is None else before["record_digest"],
            "evidence_version": 1 if before is None else before["evidence_version"] + 1,
        }
        appended.append(line)
    if appended:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for line in appended:
                handle.write(
                    json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n"
                )
    return appended


def snapshot(records, not_entered, sources):
    """The deterministic, digest-pinned snapshot the register reads (no timestamps)."""
    body = {
        "schema": SNAPSHOT_SCHEMA,
        "claims": dict(CLAIMS),
        "sources": sources,
        "records": sorted(records, key=lambda r: r["item_id"]),
        "not_entered": sorted(not_entered, key=lambda r: r["item_id"]),
        "known_reds": list(KNOWN_REDS),
    }
    body["snapshot_digest"] = digest(body)
    return body


def propose_removal(finding_id, records, *, proposed_by, now):
    """A PROPOSED `scope-removal.v1` from one finding, in one step, or `(None, refusal_code)`. Only a triaged
    REAL_ESCAPE is a removal reason; ORACLE_GAP, FALSE_POSITIVE, an untriaged finding, NOT_RUN and INCONCLUSIVE are
    not (a person decides without a finding: OWNER_REMOVAL, from a human record only).
    """
    for record in records:
        for finding in record["findings"]:
            if finding["finding_id"] != finding_id:
                continue
            reason = REMOVAL_REASONS.get(finding["triage"])
            if reason is None:
                return None, "not_a_removal_reason:" + str(finding["triage"])
            if record.get("finding_lifecycle_policy") != LIFECYCLE_POLICY:
                return None, "finding_lifecycle_unverified"
            if finding["repaired"] or finding["clean_reattack"]:
                return None, "finding_resolved"
            if (
                finding.get("controller_state") == "RECURRED"
                and finding.get("recurred_after_repair") is True
            ):
                reason = "ESCAPE_RECURS_AFTER_FIX"
            elif finding["fix_ref"]:
                return None, "fix_awaiting_clean_reattack"
            removal = {
                "schema": REMOVAL_SCHEMA,
                "removal_id": "removal-"
                + digest({"item": record["item_id"], "finding": finding_id})[7:23],
                "item_id": record["item_id"],
                "level": record["level"],
                "construction_family": record["construction_family"],
                "entry_ref": record["record_digest"],
                "justification": [
                    {
                        "finding_id": finding_id,
                        "attack_report_ref": (
                            record["families"].get(finding["family"]) or {}
                        ).get("report_ref"),
                        "family": finding["family"],
                        "attempt": finding["attempt"],
                        "authority": finding["authority"],
                        "conditions": finding["conditions"],
                        "triage": finding["triage"],
                    }
                ],
                "reason_code": reason,
                "reason_text": None,
                "proposed_at": now()
                .astimezone(datetime.UTC)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "proposed_by": proposed_by,
                "decision": {
                    "state": "PROPOSED",
                    "decided_by": None,
                    "decided_at": None,
                    "decision_ref": None,
                },
                "effective_from": None,
                "supersedes": None,
                "restored_by": None,
                "claims": dict(CLAIMS),
            }
            removal["record_digest"] = digest(removal)
            return removal, None
    return None, "finding_not_found"


def attempt_strategies(store):
    """`{(root, attempt): strategy or None}` for the journalled `compile_strategy`-style attempts of one attacker store,
    read-only. An attempt identity that repeats across sessions with different strategies is ambiguous: None.
    """
    from carbon.agent_campaign.attack import analysis

    found = {}
    for run in sorted(Path(store).glob("graphite/runs/*")):
        for attempt in analysis.attempts(run):
            raw = (attempt.arguments or {}).get("strategy_json")
            try:
                strategy = json.loads(raw) if isinstance(raw, str) else None
            except ValueError:
                strategy = None
            found.setdefault((Path(store).parent.name, attempt.identity), []).append(
                strategy
            )
    out = {}
    for key, strategies in found.items():
        distinct = {json.dumps(s, sort_keys=True) for s in strategies}
        out[key] = strategies[0] if len(distinct) == 1 else None
    return out


def generate(
    args, *, strategy_of=None, now=lambda: datetime.datetime.now(datetime.UTC)
):
    items = json.loads(Path(args.items).read_text(encoding="utf-8"))
    ledger = load_ledger(args.ledger)
    triage, fixes, reattack, sources = load_manifests(args.backfill)
    reports, findings, repairs, strategies = [], [], [], {}
    for store in args.attacker_store:
        root = read_attack_root(store)
        reports += root["reports"]
        findings += root["findings"]
        repairs += root["repairs"]
        if strategy_of is None:
            strategies.update(attempt_strategies(store))
    if strategy_of is None:
        strategy_of = lambda finding: strategies.get(
            (finding["root"], finding["attempt"])
        )
    sources = [
        *sources,
        {"ledger": Path(args.ledger).name, "digest": file_digest(args.ledger)},
        {"items": Path(args.items).name, "digest": file_digest(args.items)},
        *({"coverage": r["ref"], "digest": r["digest"]} for r in reports),
    ]
    records, not_entered = [], []
    for item in items["items"]:
        record, why = build_item(
            item,
            ledger=ledger,
            reports=reports,
            findings=findings,
            triage=triage,
            fixes=fixes,
            reattack=reattack,
            repairs=repairs,
            strategy_of=strategy_of,
        )
        if record is None:
            not_entered.append(
                {"item_id": item["item_id"], "level": item["level"], "reason": why}
            )
        else:
            records.append(record)
    appended = []
    if args.out_jsonl:
        appended = append_records(args.out_jsonl, records, now=now)
    shot = snapshot(records, not_entered, sources)
    if args.snapshot_out:
        Path(args.snapshot_out).write_text(
            json.dumps(shot, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return {
        "records": len(records),
        "appended": len(appended),
        "not_entered": len(not_entered),
        "snapshot": shot["snapshot_digest"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dev.graphite_progress.survived", description=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--items", required=True, help="the committed item_families.json")
    gen.add_argument("--ledger", required=True, help="progress.jsonl")
    gen.add_argument(
        "--backfill", required=True, help="the backfill manifests directory"
    )
    gen.add_argument(
        "--attacker-store",
        action="append",
        default=[],
        help="an attacker store (its reports/ and controller/)",
    )
    gen.add_argument(
        "--out-jsonl",
        help="the append-only survived-record.jsonl (outside the repository)",
    )
    gen.add_argument("--snapshot-out", help="the committed, digest-pinned snapshot")
    args = parser.parse_args(argv)
    print(json.dumps(generate(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
