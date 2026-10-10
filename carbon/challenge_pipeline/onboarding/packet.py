"""Deterministic common-packet drafts. Source verification is not qualification."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "carbon.onboarding.brief.v1"
PACKET = "carbon.onboarding.packet-draft.v1"
LIMIT = 2_000_000
SECTIONS = (
    ("Engineering job", ("buyer", "decision", "value", "wrong_decision", "exclusions")),
    (
        "Physical system",
        ("physics", "geometry", "materials", "conditions", "omissions"),
    ),
    ("Population P, Q and w", ("P", "Q", "w", "strata", "independent_unit")),
    ("Case contract", ("case_identity", "validity", "disclosure")),
    ("Reference policy", ("solver", "pins", "refinement", "uncertainty", "cost")),
    ("Output and measurement contract", ("outputs", "hard_limits", "objective")),
    ("Construction contract", ("vocabulary", "training", "permissions")),
    ("Research kit", ("public_kit", "baseline", "rights")),
    ("Evidence plan", ("panel", "controls", "confirmation")),
    ("Readiness and claim record", ("readiness", "owners", "next_gate")),
)
FIELDS = {field for _, fields in SECTIONS for field in fields}


class DraftError(ValueError):
    """A stable non-echoing tooling refusal."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 8000:
        raise DraftError("nonempty bounded text required")
    return value


def source_path(root: Path, name: str) -> Path:
    """Only explicit public repository documentation; no host or hidden scan."""
    text(name)
    parts = name.replace("\\", "/").split("/")
    if any(p in ("", ".", "..") for p in parts) or ":" in name:
        raise DraftError("repository-relative source required")
    allowed = (
        name.startswith("docs/development/"),
        name.startswith("Design_Specs/"),
        name.startswith(".agent/decisions/"),
        name.startswith(".agent/tickets/"),
    )
    if not any(allowed) or any(
        p.lower() in {"hidden", "protected", "secrets", ".git", ".aws"} for p in parts
    ):
        raise DraftError("public documentation source required")
    root = root.resolve()
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise DraftError("source missing or outside repository")
    if target.stat().st_size > LIMIT:
        raise DraftError("source exceeds tooling size bound")
    return target


def read_json(path: Path):
    if path.stat().st_size > LIMIT:
        raise DraftError("input exceeds tooling size bound")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DraftError("finite JSON required")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DraftError("UTF-8 JSON required") from error


def verify_sources(sources, root):
    if type(sources) is not list or len(sources) > 8:
        raise DraftError("bounded source list required")
    checked = []
    for source in sources:
        if type(source) is not dict or set(source) != {"path", "sha256", "excerpt"}:
            raise DraftError("source path, sha256 and excerpt required")
        raw = source_path(root, source["path"]).read_bytes()
        excerpt = text(source["excerpt"])
        if source["sha256"] != digest(raw) or excerpt not in raw.decode("utf-8"):
            raise DraftError("source digest or excerpt mismatch")
        checked.append(dict(source))
    return checked


def generate(brief, root: Path):
    if (
        type(brief) is not dict
        or not {"schema", "challenge", "buyer", "decision", "physics", "solver"}
        <= set(brief)
        or set(brief)
        - {"schema", "challenge", "buyer", "decision", "physics", "solver", "fields"}
        or brief["schema"] != SCHEMA
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", str(brief["challenge"]))
    ):
        raise DraftError("closed brief schema required")
    extras = brief.get("fields", {})
    if type(extras) is not dict or set(extras) - FIELDS:
        raise DraftError("known packet fields required")
    rows = {}
    for key in sorted(FIELDS):
        proposal = brief.get(key)
        sources = []
        if key in extras:
            item = extras[key]
            if type(item) is not dict or set(item) != {"value", "sources"}:
                raise DraftError("field value and sources required")
            proposal = text(item["value"])
            sources = verify_sources(item["sources"], root)
            # Sourced extraction, not an unconstrained paraphrase with a citation.
            if sources and not any(proposal in s["excerpt"] for s in sources):
                raise DraftError("sourced value must be a retained excerpt")
        if proposal is not None:
            text(proposal)
        rows[key] = {
            "status": "SOURCE_EXTRACT" if sources else "HUMAN_INPUT",
            "recommendation": proposal,
            "sources": sources,
            "owner": (
                "science/product owner"
                if key != "permissions"
                else "construction/security owner"
            ),
            "needed_decision": f"Confirm applicability and authorize {key}",
            "held_closed": "No runtime registration, bank draw, execution, qualification or spend",
        }
    return {
        "schema": PACKET,
        "challenge": brief["challenge"],
        "maturity": "DRAFT_ONLY",
        "fields": rows,
    }


def render(packet):
    validate_packet(packet)
    lines = [
        f"# {packet['challenge']} — generated common packet draft",
        "",
        "DEVELOPMENT / DRAFT_ONLY. SOURCE_EXTRACT means verified bytes, not approval.",
        "Every unsourced field is HUMAN_INPUT. No runtime or qualification authority.",
        "",
    ]
    for i, (title, fields) in enumerate(SECTIONS, 1):
        lines.extend([f"## {i}. {title}", ""])
        for key in fields:
            item = packet["fields"][key]
            lines.extend(
                [
                    f"### {key} — {item['status']}",
                    "",
                    item["recommendation"] or "HUMAN_INPUT: no value supplied.",
                    "",
                ]
            )
            for source in item["sources"]:
                lines.append(f"Source: `{source['path']}` sha256 `{source['sha256']}`.")
            lines.extend(
                [
                    f"Owner: {item['owner']}. Needed: {item['needed_decision']}.",
                    f"Held closed: {item['held_closed']}.",
                    "",
                ]
            )
    return "\n".join(lines)


def validate_packet(packet):
    if (
        type(packet) is not dict
        or set(packet) != {"schema", "challenge", "maturity", "fields"}
        or packet["schema"] != PACKET
        or packet["maturity"] != "DRAFT_ONLY"
        or type(packet["fields"]) is not dict
        or set(packet["fields"]) != FIELDS
    ):
        raise DraftError("complete draft packet required")
    for item in packet["fields"].values():
        if (
            type(item) is not dict
            or set(item)
            != {
                "status",
                "recommendation",
                "sources",
                "owner",
                "needed_decision",
                "held_closed",
            }
            or item["status"] not in {"HUMAN_INPUT", "SOURCE_EXTRACT"}
            or type(item["sources"]) is not list
            or (item["status"] == "SOURCE_EXTRACT") != bool(item["sources"])
        ):
            raise DraftError("draft field provenance required")
        for key in ("owner", "needed_decision", "held_closed"):
            text(item[key])
        if item["recommendation"] is not None:
            text(item["recommendation"])


def compare(packet, actual: str):
    """An explicit omission diff, not a semantic equivalence or acceptance test."""
    drafted = render(packet)
    headings = re.findall(r"^## (\d+)\. (.+)$", actual, re.MULTILINE)
    return {
        "comparison": "TEXT_AND_SECTION_COVERAGE_ONLY_NOT_SEMANTIC_EQUIVALENCE",
        "actual_sha256": digest(actual.encode("utf-8")),
        "actual_numbered_sections": headings,
        "generated_sections": len(SECTIONS),
        "source_extracted_fields": sum(
            r["status"] == "SOURCE_EXTRACT" for r in packet["fields"].values()
        ),
        "human_input_fields": [
            k for k, r in packet["fields"].items() if r["status"] == "HUMAN_INPUT"
        ],
        "diff": "".join(
            difflib.unified_diff(
                actual.splitlines(True),
                drafted.splitlines(True),
                fromfile="real-packet",
                tofile="generated-draft",
            )
        ),
    }
