"""Read-only provenance lookup for an existing phase-4 attack finding.

Only the final specimen bundle is written. The controller, iteration log and
tool journal are read as recorded; no provider, miner path, oracle or solver is
called. This command does not decide whether the finding is a real escape.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from carbon.agent_campaign.attack import analysis, verify

_SPECIMEN = re.compile(r"specimen-[0-9a-f]{16}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class RemintRefused(ValueError):
    """A closed, operator-readable reason; never prints source material."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class NonSessionFinding:
    """A named older finding, never a session verdict or redacted evidence."""

    code: str
    outcome: str = "EXCLUDED_NON_SESSION_FINDING"


def _non_session_finding(evidence):
    """Recognise the two pre-session-verdict formats by their own fields."""
    source, role = evidence.get("source"), evidence.get("role")
    if (
        source == "family_report"
        and role in ("trained_control", "held_out_control")
        and evidence.get("outcome") == "WRONGLY_REFUSED"
        and isinstance(evidence.get("family"), str)
        and isinstance(evidence.get("control"), str)
        and isinstance(evidence.get("control_identity"), str)
        and _DIGEST.fullmatch(evidence["control_identity"])
    ):
        return NonSessionFinding("finding_non_session_control_v1")
    if (
        source in ("deterministic_baseline", "copy_probe")
        and role in ("attack", "control")
        and isinstance(evidence.get("family"), str)
        and isinstance(evidence.get("attempt"), str)
        and isinstance(evidence.get("evidence_digest"), str)
        and _DIGEST.fullmatch(evidence["evidence_digest"])
    ):
        return NonSessionFinding("finding_non_session_engine_v1")
    return None


def _finding_verdict(controller, db, finding_id):
    row = db.execute("SELECT body FROM findings WHERE id=?", (finding_id,)).fetchone()
    if row is None:
        raise RemintRefused("finding_missing_from_campaign")
    try:
        finding = json.loads(row[0])
        if finding["id"] != finding_id:
            raise ValueError("id")
        ref = finding["evidence"]
        sha = ref["sha256"]
        if not isinstance(sha, str) or not _DIGEST.fullmatch(sha):
            raise ValueError("digest")
        name = sha.removeprefix("sha256:") + ".bin"
        if ref["path"] != "evidence/" + name:
            raise ValueError("path")
        path = controller / "evidence" / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("file")
        body = path.read_bytes()
        if "sha256:" + hashlib.sha256(body).hexdigest() != sha:
            raise ValueError("bytes")
        evidence = json.loads(body)
    except (KeyError, TypeError, ValueError, OSError):
        raise RemintRefused("finding_evidence_unreadable_or_changed") from None
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != verify.FINDING_SCHEMA
        or evidence.get("condition") != finding["condition"]
    ):
        raise RemintRefused("finding_verdict_malformed")
    if evidence.get("redacted") == "protected_material":
        return None
    if "verdict" not in evidence:
        older = _non_session_finding(evidence)
        if older is not None:
            return older
        raise RemintRefused("finding_verdict_malformed")
    verdict = evidence.get("verdict")
    if not isinstance(verdict, dict) or finding["condition"] not in (
        verdict.get("conditions") or ()
    ):
        raise RemintRefused("finding_verdict_malformed")
    return verdict


def _entries(store):
    path = store / "iteration-log.jsonl"
    if not path.is_file() or path.is_symlink():
        raise RemintRefused("iteration_log_missing")
    try:
        entries = [json.loads(line) for line in path.read_bytes().splitlines()]
    except (OSError, ValueError):
        raise RemintRefused("iteration_log_malformed") from None
    if not entries:
        raise RemintRefused("iteration_log_empty")
    return entries


def _sources(store, attempt_id, expected, session):
    from carbon.agent_campaign.graphite import phase4

    controller = store / "controller"
    database = controller / "campaign.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise RemintRefused("campaign_database_missing")
    found = []
    redacted = False
    excluded_non_session = []
    finding_records_seen = 0
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            for entry in _entries(store):
                if (
                    not isinstance(entry, dict)
                    or entry.get("schema") != phase4.LOG_SCHEMA
                ):
                    raise RemintRefused("iteration_log_schema_invalid")
                number = entry.get("session")
                if session is not None and number != session:
                    continue
                if type(number) is not int or number < 1:
                    raise RemintRefused("iteration_session_invalid")
                run_id = entry.get("run_id")
                row = db.execute(
                    "SELECT campaign, run_id FROM runs WHERE key=?",
                    (phase4.session_key(number),),
                ).fetchone()
                if (
                    row is None
                    or row[0] != phase4.CAMPAIGN
                    or row[1] != run_id
                    or run_id
                    != phase4.GraphiteProvider.run_id_for(phase4.session_key(number))
                ):
                    raise RemintRefused("iteration_run_not_bound_to_campaign")
                for finding_id in entry.get("findings") or ():
                    if not isinstance(finding_id, str):
                        raise RemintRefused("finding_id_invalid")
                    finding_records_seen += 1
                    verdict = _finding_verdict(controller, db, finding_id)
                    if verdict is None:
                        redacted = True
                        continue
                    if isinstance(verdict, NonSessionFinding):
                        excluded_non_session.append(
                            {
                                "session": number,
                                "finding_id": finding_id,
                                "code": verdict.code,
                            }
                        )
                        continue
                    if verdict.get("attempt") != attempt_id:
                        continue
                    if verdict.get("outcome") != verify.BREACHED:
                        raise RemintRefused("finding_is_not_a_breach")
                    if (
                        verify.specimen_name(
                            verdict.get("family"), verdict.get("artifact")
                        )
                        == expected
                    ):
                        found.append((entry, verdict))
    except sqlite3.Error:
        raise RemintRefused("campaign_database_unreadable") from None
    # One BREACHED verdict may have several admission conditions/findings.
    unique = {}
    for entry, verdict in found:
        key = (entry["run_id"], json.dumps(verdict, sort_keys=True))
        unique[key] = (entry, verdict)
    if not unique and redacted:
        raise RemintRefused("finding_evidence_redacted")
    if len(unique) != 1:
        raise RemintRefused("remint_source_missing_or_ambiguous")
    return (*next(iter(unique.values())), excluded_non_session, finding_records_seen)


def remint(root, attempt_id, expected, *, session=None):
    """Rebuild one already recorded specimen from an authenticated local source.
    `expected` binds the operator's requested artifact-keyed folder identity."""
    from carbon.agent_campaign.graphite import phase4

    if not isinstance(expected, str) or not _SPECIMEN.fullmatch(expected):
        raise RemintRefused("expected_specimen_name_invalid")
    try:
        analysis.parse_identity(attempt_id)
    except (TypeError, ValueError):
        raise RemintRefused("attempt_identity_invalid") from None
    store = Path(root).expanduser().resolve() / "attacker"
    if not store.is_dir() or store.is_symlink():
        raise RemintRefused("campaign_store_missing_or_linked")
    specimens = store / "specimens"
    if specimens.is_symlink():
        raise RemintRefused("specimen_store_is_a_link")
    entry, recorded, excluded_non_session, finding_records_seen = _sources(
        store, attempt_id, expected, session
    )
    run_dir = store / "graphite" / "runs" / entry["run_id"]
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise RemintRefused("attempt_run_directory_missing")
    try:
        matches = [a for a in analysis.attempts(run_dir) if a.identity == attempt_id]
    except (OSError, ValueError):
        raise RemintRefused("attempt_journal_unreadable") from None
    if len(matches) != 1:
        raise RemintRefused("attempt_journal_missing_or_ambiguous")
    adapter, _variant = phase4.adapter_for(
        phase4.attack_modules(), entry["challenge"], entry["construction_level"]
    )
    result = verify.remint_specimen(matches[0], adapter, recorded, specimens)
    if result.get("folder") and Path(result["folder"]).name != expected:
        raise RemintRefused("reminted_specimen_identity_changed")
    return {
        "session": entry["session"],
        "run_id": entry["run_id"],
        "excluded_non_session": excluded_non_session,
        "excluded_non_session_count": len(excluded_non_session),
        "finding_records_seen": finding_records_seen,
        **result,
    }
