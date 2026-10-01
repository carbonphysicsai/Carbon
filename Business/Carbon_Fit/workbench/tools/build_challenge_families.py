#!/usr/bin/env python3
"""Build the Pilot Designer's public Challenge-family record (GOAL-WORKBENCH-16).

Output: ``data/challenge_families_v1.json``, embedded in the Pilot Designer so a
client's brief can be matched to a launch-portfolio family and shown a proposed
Challenge with the evidence behind each setting.

Inputs, all public and in this repository:

* ``carbon/challenge_readiness/records/*.json``: one readiness record per
  portfolio Challenge, the latest version of each (schema
  ``carbon.challenge-readiness.v3``). Status, limits, costs, reviews and the
  training budget study are copied as recorded; an approval that is null stays
  null.
* ``carbon/battery/domain.py``: the battery Challenge's input bounds, read with
  ``ast`` from the ``INPUT_BOUNDS`` literal so no numerical code is imported.
* ``data/challenge_evidence_source_v1.json``: which exam-design evidence
  supports each setting, as verbatim quotes, and how a client's words are
  matched. Every quote is checked against its source file here; a quote that
  no longer appears verbatim stops the build rather than shipping a stale claim.

The record contains no seed, private case, reference output or hidden-exam
material: only design parameters and results the repository already publishes.

Run from anywhere: ``python3 tools/build_challenge_families.py``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
RECORDS = REPO / "carbon/challenge_readiness/records"
BATTERY_DOMAIN = REPO / "carbon/battery/domain.py"
SOURCE = ROOT / "data/challenge_evidence_source_v1.json"
OUTPUT = ROOT / "data/challenge_families_v1.json"
SCHEMA = "carbon.pilot-designer.challenge-families.v1"
RECORD_SCHEMA = "carbon.challenge-readiness.v3"
COPIED = (
    "status",
    "decision",
    "design_variables",
    "outputs",
    "limits",
    "costs",
    "maturity",
    "recommendation",
    "reviews",
    "training_budget_study",
    "unresolved",
    "next_experiment",
    "tracking",
    "reference",
    "population",
)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def latest_records() -> dict[str, Path]:
    """The highest version of each record, by its ``.v<N>.json`` suffix."""
    latest: dict[str, tuple[int, Path]] = {}
    for path in sorted(RECORDS.glob("*.v*.json")):
        match = re.fullmatch(r"(.+)\.v(\d+)\.json", path.name)
        if not match:
            continue
        name, version = match.group(1), int(match.group(2))
        if name not in latest or version > latest[name][0]:
            latest[name] = (version, path)
    return {name: path for name, (_, path) in sorted(latest.items())}


def battery_bounds() -> dict[str, list[float]]:
    tree = ast.parse(BATTERY_DOMAIN.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(isinstance(t, ast.Name) and t.id == "INPUT_BOUNDS" for t in targets):
            value = ast.literal_eval(node.value)
            return {
                name: [float(low), float(high)] for name, (low, high) in value.items()
            }
    raise ValueError("carbon/battery/domain.py has no INPUT_BOUNDS literal")


def cells(line: str) -> list[str]:
    """The cells of one markdown table row, with emphasis markers removed."""
    if not (line.startswith("|") and line.endswith("|")):
        raise ValueError(f"not a table row: {line!r}")
    return [
        cell.strip().replace("**", "").replace("`", "")
        for cell in line[1:-1].split("|")
    ]


def checked(quotes: list[str], text: str, source: str) -> list[str]:
    for quote in quotes:
        if quote not in text:
            raise ValueError(f"{source} no longer contains the quoted line: {quote!r}")
    return list(quotes)


def evidence_block(key: str, spec: dict) -> dict:
    source_path = REPO / spec["source"]
    text = source_path.read_text(encoding="utf-8")
    settings = []
    for item in spec["settings"]:
        quotes = checked(item["quotes"], text, spec["source"])
        rows = [cells(q) for q in quotes if q.startswith("|")]
        setting = {
            "id": item["id"],
            "label": item["label"],
            "value": item["value"],
            "why": item["why"],
            "section": item["section"],
            "table": {"columns": item["table_columns"], "rows": rows},
            "quotes": quotes,
            "limit": item.get("limit"),
        }
        if "supporting_quotes" in item:
            supporting = checked(item["supporting_quotes"], text, spec["source"])
            setting["supporting_table"] = {
                "columns": item["supporting_columns"],
                "rows": [cells(q) for q in supporting],
            }
        settings.append(setting)
    return {
        "id": key,
        "title": spec["title"],
        "summary": spec["summary"],
        "source": {"path": spec["source"], "sha256": digest(source_path)},
        "settings": settings,
        "limits_of_evidence": checked(spec["limits_of_evidence"], text, spec["source"]),
    }


def section(text: str, heading: str, source: str) -> list[str]:
    """The lines under one ``##`` heading, up to the next ``##`` heading."""
    lines = text.split("\n")
    try:
        start = lines.index(heading) + 1
    except ValueError:
        raise ValueError(f"{source} has no section {heading!r}") from None
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines)
    )
    return lines[start:end]


def list_items(lines: list[str], source: str, heading: str) -> list[str]:
    """The first numbered or bulleted list in ``lines``, wrapped lines joined.

    The list ends at the first line that is neither an item, an indented
    continuation nor blank, so a section's later paragraphs are never read as
    items. Only emphasis markers are removed; the words are the source's.
    """
    items: list[str] = []
    for line in lines:
        if re.match(r"^(\d+\.|-) ", line):
            items.append(re.sub(r"^(\d+\.|-) ", "", line).strip())
        elif items and line.startswith("   ") and line.strip():
            items[-1] += " " + line.strip()
        elif items and line.strip():
            break
    if not items:
        raise ValueError(f"{source} section {heading!r} has no list")
    return [item.replace("**", "").replace("`", "") for item in items]


def table_after(lines: list[str], header: str, source: str) -> dict:
    try:
        start = lines.index(header)
    except ValueError:
        raise ValueError(f"{source} has no table {header!r}") from None
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(cells(line))
    return {"columns": cells(header), "rows": rows}


def campaign_plan(spec: dict) -> dict:
    source = REPO / spec["specification"]
    text = source.read_text(encoding="utf-8")
    name = spec["specification"]
    questions = list_items(
        section(text, spec["questions_section"], name), name, spec["questions_section"]
    )
    stages = table_after(
        section(text, spec["stages_section"], name), spec["stages_table_header"], name
    )
    cannot = list_items(
        section(text, spec["cannot_establish_section"], name),
        name,
        spec["cannot_establish_section"],
    )
    spend = spec["prior_spend"]
    spend_path = REPO / spend["source"]
    checked([spend["quote"]], spend_path.read_text(encoding="utf-8"), spend["source"])
    budget = spec["training_budget"]
    budget_path = REPO / budget["source"]
    checked(budget["quotes"], budget_path.read_text(encoding="utf-8"), budget["source"])
    return {
        "title": spec["title"],
        "purpose": spec["purpose"],
        "source": {"path": name, "sha256": digest(source)},
        "questions": questions,
        "stages": stages,
        "cannot_establish": cannot,
        "prior_spend": {
            "label": spend["label"],
            "value": spend["quote"],
            "source": {"path": spend["source"], "sha256": digest(spend_path)},
        },
        "training_budget": {
            "summary": budget["summary"],
            "quotes": budget["quotes"],
            "source": {"path": budget["source"], "sha256": digest(budget_path)},
        },
    }


def build() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = latest_records()
    bounds = {"battery-fastcharge-ageing-development-v1": battery_bounds()}
    evidence = {
        key: evidence_block(key, spec)
        for key, spec in sorted(source["evidence"].items())
    }
    families = []
    for family_id, matching in source["families"].items():
        path = records.get(family_id)
        if path is None:
            raise ValueError(f"no readiness record for {family_id}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if (
            record.get("schema") != RECORD_SCHEMA
            or record.get("challenge_id") != family_id
        ):
            raise ValueError(
                f"{relative(path)} is not a {RECORD_SCHEMA} record for {family_id}"
            )
        variables = []
        for variable in record["design_variables"]:
            known = bounds.get(family_id, {}).get(variable["name"])
            variables.append(
                {
                    **variable,
                    "bounds": known,
                    "bounds_source": relative(BATTERY_DOMAIN) if known else None,
                    "aliases": matching["variable_aliases"].get(variable["name"], []),
                }
            )
        unknown_aliases = set(matching["variable_aliases"]) - {
            v["name"] for v in variables
        }
        if unknown_aliases:
            raise ValueError(
                f"{family_id} aliases name unknown variables: {sorted(unknown_aliases)}"
            )
        families.append(
            {
                "id": family_id,
                "title": matching["title"],
                "record": {"path": relative(path), "sha256": digest(path)},
                "matching": {
                    "keywords": matching["keywords"],
                    "physics": matching["physics"],
                },
                **{key: record[key] for key in COPIED},
                "design_variables": variables,
                "evidence": matching["evidence"],
            }
        )
        if matching["evidence"] is not None and matching["evidence"] not in evidence:
            raise ValueError(
                f"{family_id} names missing evidence {matching['evidence']}"
            )
    return {
        "schema": SCHEMA,
        "purpose": (
            "Public launch-portfolio families and the exam-design evidence behind "
            "their proposed settings, for the Pilot Designer's proposed Challenge. "
            "Relayed from repository records; nothing here is approved, qualified "
            "or a commitment to run."
        ),
        "matching_rule": source["matching_rule"],
        "source": {"path": relative(SOURCE), "sha256": digest(SOURCE)},
        "families": families,
        "evidence": evidence,
        "campaign_plan": campaign_plan(source["campaign_plan"]),
    }


def main() -> None:
    OUTPUT.write_text(
        json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
