"""Offline buyer-clause consistency; matching text never grants authority."""

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet

SCHEMA = "carbon.onboarding.packet-reconcile.v1"
BUYER_FIELDS = frozenset(
    {
        "buyer",
        "decision",
        "value",
        "wrong_decision",
        "exclusions",
        "geometry",
        "conditions",
        "P",
        "Q",
        "w",
        "outputs",
        "hard_limits",
        "objective",
    }
)
KINDS = {"PACKET", "SOURCE", "OWNER_DECISION", "TEST_LEAD_DECISION"}


def normalized(value):
    return " ".join(packet.text(value).split())


def selector_check(selector):
    if type(selector) is not dict or selector.get("kind") not in {"number", "literal"}:
        raise packet.DraftError("closed clause selector required")
    fields = {"document", "kind", "section"}
    fields |= (
        {"prefix", "suffix"} if selector["kind"] == "number" else {"phrase", "value"}
    )
    if set(selector) != fields:
        raise packet.DraftError("closed clause selector required")
    for key in fields - {"section"}:
        packet.text(selector[key])
    if selector["section"] is not None:
        packet.text(selector["section"])


def extract(text, selector):
    """Only escaped literal delimiters; no caller-controlled regular expression."""
    selector_check(selector)
    if selector["section"] is not None:
        headings = list(re.finditer(r"^## (.+)$", text, re.MULTILINE))
        hits = [
            i
            for i, h in enumerate(headings)
            if normalized(h[1]) == normalized(selector["section"])
        ]
        if len(hits) != 1:
            return {"state": "MISSING_OR_AMBIGUOUS_SECTION", "value": None}
        i = hits[0]
        text = text[
            headings[i].end() : (
                headings[i + 1].start() if i + 1 < len(headings) else len(text)
            )
        ]
    compact = " ".join(text.split())
    if selector["kind"] == "literal":
        phrase = normalized(selector["phrase"])
        count = len(
            re.findall(
                r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", compact, re.IGNORECASE
            )
        )
        return {
            "state": "EXTRACTED" if count == 1 else "MISSING_OR_AMBIGUOUS_CLAUSE",
            "value": selector["value"] if count == 1 else None,
        }
    pattern = (
        re.escape(normalized(selector["prefix"]))
        + r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*"
        + re.escape(normalized(selector["suffix"]))
    )
    matches = re.findall(pattern, compact)
    if len(matches) != 1:
        return {"state": "MISSING_OR_AMBIGUOUS_CLAUSE", "value": None}
    try:
        value = Decimal(matches[0])
    except InvalidOperation as exc:
        raise packet.DraftError("finite numeric clause required") from exc
    return {"state": "EXTRACTED", "value": format(value.normalize(), "f")}


def validate(manifest):
    if (
        type(manifest) is not dict
        or set(manifest) != {"schema", "challenge", "documents", "checks"}
        or manifest["schema"] != SCHEMA
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", str(manifest["challenge"]))
    ):
        raise packet.DraftError("closed reconciliation manifest required")
    docs, checks = manifest["documents"], manifest["checks"]
    if (
        type(docs) is not dict
        or not 1 <= len(docs) <= 40
        or type(checks) is not list
        or not 1 <= len(checks) <= 200
    ):
        raise packet.DraftError("bounded documents/checks required")
    for key, doc in docs.items():
        packet.text(key)
        if (
            type(doc) is not dict
            or set(doc) != {"path", "sha256", "kind"}
            or doc["kind"] not in KINDS
            or not re.fullmatch(r"[0-9a-f]{64}", str(doc["sha256"]))
        ):
            raise packet.DraftError("pinned public document required")
        packet.text(doc["path"])
    if sum(doc["kind"] == "PACKET" for doc in docs.values()) != 1:
        raise packet.DraftError("exactly one packet required")
    ids = set()
    for row in checks:
        if (
            type(row) is not dict
            or set(row) != {"id", "field", "packet", "evidence"}
            or row["field"] not in BUYER_FIELDS
            or row["id"] in ids
            or type(row["evidence"]) is not list
            or not 1 <= len(row["evidence"]) <= 8
        ):
            raise packet.DraftError("unique buyer check and explicit evidence required")
        packet.text(row["id"])
        ids.add(row["id"])
        for s in [row["packet"], *row["evidence"]]:
            selector_check(s)
            if s["document"] not in docs:
                raise packet.DraftError("selector document not bound")
        if docs[row["packet"]["document"]]["kind"] != "PACKET" or any(
            docs[s["document"]]["kind"] == "PACKET" for s in row["evidence"]
        ):
            raise packet.DraftError("packet cannot corroborate itself")
        if any(s["kind"] != row["packet"]["kind"] for s in row["evidence"]):
            raise packet.DraftError("matched typed selectors required")


def reconcile(root, manifest):
    validate(manifest)
    documents, bodies = {}, {}
    for key, doc in manifest["documents"].items():
        try:
            if any(
                word in doc["path"].lower()
                for word in ("ev5", "journal", "hidden", "protected", "secret")
            ):
                raise packet.DraftError("public source only")
            raw = packet.source_path(root, doc["path"]).read_bytes()
            current = packet.digest(raw)
            body = raw.decode("utf-8")
            state = "PIN_MATCH" if current == doc["sha256"] else "STALE_PIN"
            bodies[key] = body
        except (packet.DraftError, OSError, UnicodeError):
            current, state = None, "UNAVAILABLE_NOT_ABSENCE"
        documents[key] = {**doc, "observed_sha256": current, "state": state}
    rows = []
    for row in manifest["checks"]:
        values = []
        for s in [row["packet"], *row["evidence"]]:
            doc = documents[s["document"]]
            item = (
                extract(bodies[s["document"]], s)
                if doc["state"] == "PIN_MATCH"
                else {"state": doc["state"], "value": None}
            )
            values.append(
                {"document": s["document"], "path": doc["path"], "selector": s, **item}
            )
        left, evidence = values[0], values[1:]
        settled = all(v["state"] == "EXTRACTED" for v in values)
        state = (
            "MISSING_STALE_OR_AMBIGUOUS"
            if not settled
            else (
                "CONSISTENT"
                if all(v["value"] == left["value"] for v in evidence)
                else "CONTRADICTED"
            )
        )
        rows.append(
            {
                "id": row["id"],
                "field": row["field"],
                "state": state,
                "packet": left,
                "evidence": evidence,
            }
        )
    bound = {row["field"] for row in rows}
    unbound = sorted(BUYER_FIELDS - bound)
    return {
        "schema": "carbon.onboarding.packet-reconciliation-report.v1",
        "challenge": manifest["challenge"],
        "manifest_sha256": packet.digest(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ),
        "documents": documents,
        "checks": rows,
        "unbound_buyer_fields": unbound,
        "coverage": {
            "required_buyer_fields": len(BUYER_FIELDS),
            "bound_buyer_fields": len(bound),
            "checks_examined": len(rows),
            "consistent": sum(r["state"] == "CONSISTENT" for r in rows),
        },
        "checklist_clear": not unbound
        and all(r["state"] == "CONSISTENT" for r in rows),
        "authority_granted": False,
        "basis": "Reviewed clause bindings only: numeric equality or exact phrase-to-token mappings. Not empirical credibility, semantic entailment, approval, qualification or readiness. Unbound fields need reviewed bindings; do not guess values.",
    }


def render(report):
    lines = [
        f"# {report['challenge']} buyer-field reconciliation",
        "",
        report["basis"],
        "",
        f"Coverage: {report['coverage']}",
        "",
        "| Field / check | State | Packet value | Evidence value(s) |",
        "|---|---|---|---|",
    ]
    for row in report["checks"]:
        lines.append(
            f"| {row['field']} / {row['id']} | {row['state']} | {row['packet']['value']} | {', '.join(str(e['value']) for e in row['evidence'])} |"
        )
    lines.extend(
        [
            "",
            "Unbound buyer fields: " + ", ".join(report["unbound_buyer_fields"]),
            "",
            "All source pointers, digests and selectors are retained in JSON. No packet value was changed.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="report findings without an automation exit-code failure",
    )
    args = parser.parse_args()
    try:
        report = reconcile(
            args.root, packet.read_json(packet.source_path(args.root, args.manifest))
        )
    except packet.DraftError as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(report, indent=2) if args.format == "json" else render(report))
    return 0 if args.report_only or report["checklist_clear"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
