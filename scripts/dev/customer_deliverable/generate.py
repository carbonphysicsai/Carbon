"""Render development evidence documents from explicitly registered public files.

No solver, evaluator, network client, hidden-store discovery or qualification.
Git reads committed blobs; offline bundles verify bytes against export receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPOSITORY = "carbonphysicsai/Carbon"
PROFILES = {"nasa-std-7009b": 1, "asme-vv10": 2}
NASA_STANDARD = (
    "https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/"
    "NASA-STD-7009B-Final-3-5-2024.pdf"
)
# Factor names/anchors: NASA-STD-7009B Appendix E. Common-section links are
# development indexing choices, never assessed factor levels or compliance.
NASA_FACTORS = {
    "capability": [
        ("Data pedigree", "E.3.2", ["D03", "D04", "D08"], []),
        ("Verification", "E.3.3", ["D04", "D08"], ["EV5_REBUILDS"]),
        ("Validation", "E.3.4", ["D04", "D05"], ["EV4_FALSE_FEASIBLE"]),
        ("Development technical review", "E.3.5", ["D10", "D11"], []),
        ("Development process/product management", "E.3.6", ["D08", "D11"], []),
    ],
    "results": [
        ("Use assessment", "E.4.2", ["D01", "D03", "D09"], []),
        ("Input pedigree", "E.4.3", ["D03", "D08"], []),
        ("Uncertainty characterization", "E.4.4", ["D06"], []),
        (
            "Results robustness",
            "E.4.5",
            ["D05", "D07"],
            ["EV5_ATTACK", "Q1_MISSING_V3"],
        ),
        ("Use/analysis technical review", "E.4.6", ["D10", "D11"], []),
        ("Use process/product management", "E.4.7", ["D08", "D11"], []),
    ],
}
POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "Business/research/deliverable-generator/public-sources.json"
)


def git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()


def safe_path(path: str) -> str:
    pure = PurePosixPath(path)
    if (
        path != pure.as_posix()
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in path
        or path == "."
        or re.search(r"hidden|protected|private|ax42", path, re.IGNORECASE)
    ):
        raise ValueError("Source policy contains a forbidden path")
    return path


def load_policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy["repository"] != REPOSITORY:
        raise ValueError("Source repository is not authorized")
    for group in [
        policy["framework"],
        *[entry["sources"] for entry in policy["challenges"].values()],
    ]:
        ids = [item["id"] for item in group]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source identity")
        for item in group:
            safe_path(item["path"])
            if not re.fullmatch(r"[A-Z]\d+", item["id"]):
                raise ValueError("Invalid source identity")
    return policy


@dataclass(frozen=True)
class Source:
    id: str
    path: str
    revision: str
    blob: str
    text: str

    @property
    def url(self) -> str:
        return f"https://github.com/{REPOSITORY}/blob/{self.revision}/{self.path}"

    def cite(self, locator: str = "file") -> str:
        anchor = f"#{locator}" if re.fullmatch(r"L\d+(?:-L\d+)?", locator) else ""
        return f"[{self.id}:{locator}]({self.url}{anchor})"

    def ledger(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "revision": self.revision,
            "git_blob": self.blob,
            "sha256": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "url": self.url,
            "locator": "immutable public file; fact locators in manifest",
            "access_class": "PUBLIC_COMMITTED",
        }


class GitReader:
    membership_basis = "LOCAL_COMMITTED_GIT_OBJECT"

    def __init__(self, root: Path, evidence_ref: str, framework_ref: str):
        self.root = root
        self.evidence_revision = self._revision(evidence_ref)
        self.framework_revision = self._revision(framework_ref)

    def _git(self, *args: str) -> bytes:
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(self.root), *args],
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode:
            raise ValueError("Committed Git object unavailable")
        return result.stdout

    def _revision(self, ref: str) -> str:
        sha = (
            self._git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
            .decode("ascii")
            .strip()
        )
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise ValueError("Invalid committed revision")
        return sha

    def get(self, spec: dict, framework: bool = False) -> Source | None:
        path = safe_path(spec["path"])
        rev = self.framework_revision if framework else self.evidence_revision
        entry = self._git("ls-tree", rev, "--", path).decode("utf-8").strip()
        if not entry:
            return None
        mode, kind, identity = entry.split("\t", 1)[0].split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError("Source is not a regular committed file")
        data = self._git("cat-file", "blob", f"{rev}:{path}")
        if git_blob(data) != identity:
            raise ValueError("Committed source identity mismatch")
        return Source(spec["id"], path, rev, identity, data.decode("utf-8"))


class BundleReader:
    membership_basis = "TRUSTED_EXPORTER_ASSERTION_WITH_BLOB_BYTE_CHECK"

    def __init__(self, root: Path):
        self.root = root
        if (
            any(parent.is_symlink() for parent in [root, *root.parents])
            or (root / "receipt.json").is_symlink()
        ):
            raise ValueError("Source export must not be a symlink")
        self.receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
        if (
            self.receipt.get("schema") != "PUBLIC_SOURCE_EXPORT_V1"
            or self.receipt.get("repository") != REPOSITORY
        ):
            raise ValueError("Invalid public source export")
        self.evidence_revision = self.receipt["evidence_revision"]
        self.framework_revision = self.receipt["framework_revision"]
        for rev in (self.evidence_revision, self.framework_revision):
            if not re.fullmatch(r"[a-f0-9]{40}", rev):
                raise ValueError("Invalid export revision")

    def get(self, spec: dict, framework: bool = False) -> Source | None:
        safe_path(spec["path"])
        item = self.receipt["files"].get(spec["id"])
        if item is None:
            return None
        rev = self.framework_revision if framework else self.evidence_revision
        if item.get("path") != spec["path"] or item.get("revision") != rev:
            raise ValueError("Public export identity/role mismatch")
        payload = self.root / f"{spec['id']}.txt"
        if payload.is_symlink():
            raise ValueError("Public export payload must not be a symlink")
        data = payload.read_bytes()
        if git_blob(data) != item.get("git_blob") or hashlib.sha256(
            data
        ).hexdigest() != item.get("sha256"):
            raise ValueError("Public export bytes do not match receipt")
        return Source(
            spec["id"], spec["path"], rev, item["git_blob"], data.decode("utf-8")
        )


def extract_facts(config: dict, sources: dict) -> tuple[list, list]:
    facts, gaps = [], []
    for rule in config["extractors"]:
        source = sources.get(rule["source"])
        matches = list(re.finditer(rule["pattern"], source.text)) if source else []
        if len(matches) != 1:
            gaps.append(f"{rule['id']}: source absent or unique anchor unavailable")
            continue
        match = matches[0]
        locator = (
            f"L{source.text[:match.start()].count(chr(10)) + 1}"
            f"-L{source.text[:match.end()].count(chr(10)) + 1}"
        )
        groups = list(match.groups())
        if rule["kind"] in {"counts", "rebuilds", "violations"}:
            values = [int(value) for value in groups]
            if rule["kind"] != "violations" and values[0] > values[1]:
                gaps.append(f"{rule['id']}: inconsistent source counts")
                continue
            value = f"{values[0]} / {values[1]}"
            quantities = [
                {"low": n, "base": n, "high": n, "basis": "SOURCED"} for n in values
            ]
        elif rule["kind"] == "fraction":
            value = groups[0]
            number = float(value)
            quantities = [
                {"low": number, "base": number, "high": number, "basis": "SOURCED"}
            ]
        else:
            value, quantities = groups[0], []
        if rule["kind"] == "verdict":
            outcome = value
        elif rule["kind"] in {"counts", "violations"} and values[0] > 0:
            outcome = "FAIL"  # Source explicitly reports false/infeasible calls.
        else:
            outcome = "NOT_ASSESSED"  # No qualification inferred from counts.
        facts.append(
            {
                "id": rule["id"],
                "source": source.id,
                "locator": locator,
                "label": rule["label"],
                "value": value,
                "kind": rule["kind"],
                "basis": rule["basis"],
                "outcome": outcome,
                "quantities": quantities,
                "citation": source.cite(locator),
            }
        )
    readiness = sources.get("R1")
    if readiness:
        try:
            reviews = json.loads(readiness.text)["reviews"]
            expected = {
                "customer",
                "launch",
                "numerical_reference",
                "scientific",
                "security",
            }
            if not isinstance(reviews, dict) or not expected <= set(reviews):
                raise ValueError("Incomplete public review record")
            for name in sorted(expected):
                review = reviews[name]
                state = review["state"]
                if state not in {
                    "NOT_STARTED",
                    "IN_REVIEW",
                    "PASS",
                    "FAIL",
                    "APPROVED",
                    "REJECTED",
                    "UNRESOLVED",
                }:
                    raise ValueError("Unrecognized public review state")
                locator = f"/reviews/{name}/state"
                facts.append(
                    {
                        "id": f"REVIEW_{name}",
                        "source": readiness.id,
                        "locator": locator,
                        "label": f"Recorded {name} review state",
                        "value": state,
                        "kind": "review",
                        "basis": "verification",
                        "outcome": "NOT_ASSESSED",
                        "quantities": [],
                        "citation": readiness.cite(locator),
                    }
                )
        except (KeyError, TypeError, ValueError):
            gaps.append("Readiness reviews unavailable or schema unrecognized")
    return facts, gaps


def render(challenge: str, profile: str, reader, policy: dict) -> dict:
    if challenge not in policy["challenges"] or profile not in PROFILES:
        raise ValueError("Unsupported Challenge or standard profile")
    config = policy["challenges"][challenge]
    sources, missing = {}, []
    for spec in policy["framework"] + config["sources"]:
        source = reader.get(spec, framework=spec in policy["framework"])
        if source is None:
            missing.append(spec["id"])
        else:
            sources[source.id] = source
    if not all(key in sources for key in ("F1", "F2", "F3")):
        raise ValueError("Committed framework template/schema/crosswalk required")
    template = sources["F1"].text
    schema = json.loads(sources["F2"].text)
    sections = {}
    titles = {}
    for match in re.finditer(
        r"^## (D\d{2}) ([^\n]+)\n(.*?)(?=^## |\Z)",
        template,
        re.MULTILINE | re.DOTALL,
    ):
        sid, title, body = match.groups()
        auto = re.search(
            r"Automation: (manual|automatable now|automatable later)\.", body
        )
        if sid in sections or auto is None:
            raise ValueError("Unrecognized common template structure")
        titles[sid] = title
        sections[sid] = {
            "coverage": "GAP",
            "automation": auto.group(1),
            "statement": "HUMAN_INPUT: this section requires accepted evidence "
            "or human judgment; it is not automatically filled.",
            "evidence_refs": ["F1"],
            "gaps": ["HUMAN_INPUT: section completion and responsible authority"],
        }
    if (
        set(sections) != set(schema["properties"]["sections"]["required"])
        or schema["properties"]["schema_version"].get("const") != "PROPOSAL_V1"
    ):
        raise ValueError("Template/schema version or section identity mismatch")
    crosswalk = {}
    for line in sources["F3"].text.splitlines():
        if re.match(r"\| D\d{2} ", line):
            cells = [part.strip() for part in line.split("|")[1:-1]]
            if len(cells) != 6 or cells[0][:3] in crosswalk:
                raise ValueError("Unrecognized standards crosswalk structure")
            crosswalk[cells[0][:3]] = cells
    if set(crosswalk) != set(sections):
        raise ValueError("Standard section mapping incomplete")
    facts, gaps = extract_facts(config, sources)
    now = {
        key
        for key, value in sections.items()
        if value["automation"] == "automatable now"
    }
    if now != {"D08", "D11"}:
        raise ValueError("New automatable section needs an explicit adapter")
    for sid in sorted(now):
        sections[sid].update(
            coverage="PARTIAL",
            statement="Public committed-source identities and recorded metadata "
            "are indexed below. No artifact qualification, physical "
            "validity or audit completeness is inferred.",
            evidence_refs=sorted(sources),
            gaps=[
                (
                    "HUMAN_INPUT: product identity/parity, rights, independent "
                    "review and qualification authority"
                ),
                *gaps,
                *[f"MISSING_SOURCE: {key}" for key in missing],
            ],
        )
    findings = []
    for fact in facts:
        if fact["kind"] in {"counts", "verdict", "gap", "violations", "fraction"}:
            findings.append(
                {
                    "id": fact["id"],
                    "basis": fact["basis"],
                    "outcome": fact["outcome"],
                    "statement": f"{fact['label']}: {fact['value']}",
                    "evidence_refs": [fact["source"]],
                    "status": "HISTORICAL_RETAINED",
                }
            )
    ledgers = [sources[key].ledger() for key in sorted(sources)]
    record = {
        "schema_version": "PROPOSAL_V1",
        "mode": "DEVELOPMENT_SAMPLE",
        "challenge": challenge,
        "intended_tier": "EVIDENCE_AUDIT",
        "eligible_tier": "UNESTABLISHED",
        "qualification_record": None,
        "source_snapshot": reader.evidence_revision,
        "sections": sections,
        "sources": [
            {key: entry[key] for key in ("id", "url", "locator", "access_class")}
            for entry in ledgers
        ],
        "adverse_review": "FINDINGS_RETAINED" if findings else "NOT_ASSESSED",
        "adverse_findings": findings,
        "tier_criteria": [
            {
                "criterion": "Customer-specific audit prerequisites and acceptance",
                "status": "GAP",
                "authority": "HUMAN_INPUT",
                "evidence_refs": ["F1"],
            }
        ],
    }
    lines = [
        "# Customer evidence record — DEVELOPMENT SAMPLE",
        "",
        "**No qualification claim. Eligible tier: UNESTABLISHED.**",
        "",
        f"Challenge: `{challenge}`. Evidence snapshot: `{reader.evidence_revision}`.",
        f"Framework snapshot: `{reader.framework_revision}`. Profile: `{profile}`.",
        (
            f"Template {sources['F1'].cite()}; schema {sources['F2'].cite()}; "
            f"crosswalk {sources['F3'].cite()}."
        ),
        "",
        (
            "Source-derived counts are SOURCED low=base=high point reproductions, "
            "not uncertainty estimates. Manual judgments remain gaps."
        ),
        "",
    ]
    for sid, section in sections.items():
        lines.extend(
            [
                f"## {sid} {titles[sid]}",
                "",
                (
                    f"Coverage: **{section['coverage']}**. "
                    f"Automation: {section['automation']}."
                ),
                "",
                section["statement"],
                "",
            ]
        )
        if sid == "D08":
            for item in ledgers:
                lines.append(
                    f"- {item['id']}: Git blob `{item['git_blob']}`; "
                    f"public-file SHA-256 `{item['sha256']}`. "
                    f"{sources[item['id']].cite()}"
                )
        elif sid == "D11":
            for fact in facts:
                lines.append(
                    f"- {fact['label']}: **{fact['value']}**. " f"{fact['citation']}"
                )
        lines.extend(["", "Gaps:", "", *[f"- {gap}" for gap in section["gaps"]], ""])
    lines.extend(["## Adverse evidence retained", ""])
    for fact in facts:
        if fact["kind"] in {"counts", "verdict", "gap", "violations", "fraction"}:
            lines.append(
                f"- {fact['label']}: **{fact['value']}**; "
                f"source-scoped outcome {fact['outcome']}. "
                f"{fact['citation']}"
            )
    lines.extend(["", "Missing sources/extraction anchors:", ""])
    for gap in [*[f"MISSING_SOURCE: {key}" for key in missing], *gaps]:
        lines.append(f"- {gap}")
    if not missing and not gaps:
        lines.append(
            "- None in the registered extraction scope. This is not "
            "a complete-evidence or no-defects claim."
        )
    lines.extend(
        [
            "",
            "## Standard rendering index",
            "",
            (
                "Applicable clauses, formal levels and sufficiency: "
                "HUMAN_INPUT. This is an evidence index, not compliance."
            ),
            "",
        ]
    )
    if profile == "asme-vv10":
        lines.extend(
            [
                (
                    "**ASME V&V 10 clause IDs: HUMAN_INPUT.** Topic rendering "
                    "only; licensed clause review remains missing."
                ),
                "",
            ]
        )
    standard_index = {
        "profile": profile,
        "applicability": "HUMAN_INPUT",
        "qualification_claim": False,
        "section_mapping": [
            {
                "section": cells[0][:3],
                "anchor": cells[PROFILES[profile]],
                "source": "F3",
            }
            for cells in crosswalk.values()
        ],
    }
    for cells in crosswalk.values():
        lines.append(
            f"- {cells[0]} → {cells[PROFILES[profile]]}. " f"{sources['F3'].cite()}"
        )
    if profile == "nasa-std-7009b":
        standard_index["factors"] = {}
        fact_map = {fact["id"]: fact for fact in facts}
        for group, factors in NASA_FACTORS.items():
            lines.extend(
                [
                    "",
                    f"### NASA {group} factor evidence index",
                    "",
                    (
                        "Coverage concerns indexed public records only. Physical "
                        "validation, formal levels and thresholds remain HUMAN_INPUT. "
                        f"[NASA-STD-7009B Appendix E]({NASA_STANDARD}); "
                        f"rendering contract {sources['F3'].cite()}."
                    ),
                    "",
                    "| Factor / anchor | Common sections | Indexed evidence coverage | Evidence / gaps |",
                    "| --- | --- | --- | --- |",
                ]
            )
            standard_index["factors"][group] = []
            for name, anchor, linked_sections, linked_facts in factors:
                available = [fact_map[fid] for fid in linked_facts if fid in fact_map]
                provenance = "D08" in linked_sections
                coverage = "PARTIAL" if available or provenance else "GAP"
                refs = [f["source"] for f in available] or (
                    ["F1"] if provenance else []
                )
                evidence = "; ".join(f["citation"] for f in available)
                if provenance:
                    evidence = (
                        evidence or f"Public-file ledger D08; {sources['F1'].cite()}"
                    )
                evidence = (
                    (evidence + "; " if evidence else "")
                    + "HUMAN_INPUT: sufficiency, applicability and physical/use evidence"
                )
                lines.append(
                    f"| {name} / {anchor} | {', '.join(linked_sections)} | "
                    f"{coverage} | {evidence} |"
                )
                standard_index["factors"][group].append(
                    {
                        "name": name,
                        "anchor": anchor,
                        "standard_source": NASA_STANDARD,
                        "sections": linked_sections,
                        "coverage": coverage,
                        "evidence_refs": sorted(set(refs)),
                        "formal_level": "HUMAN_INPUT",
                        "threshold": "HUMAN_INPUT",
                    }
                )
        lines.extend(
            [
                "",
                "### Appendix A record-location subset",
                "",
                (
                    "This subset indexes the framework's verified anchors; it is "
                    "not a complete requirements-compliance matrix. Remaining "
                    "requirements, tailoring and acceptance need authorized review."
                ),
                "",
                "| Common section | Verified anchor / source | Applicability | Record location |",
                "| --- | --- | --- | --- |",
            ]
        )
        for cells in crosswalk.values():
            sid = cells[0][:3]
            lines.append(
                f"| {sid} | {cells[1]}; {sources['F3'].cite()} | HUMAN_INPUT | "
                f"{sid}: {sections[sid]['coverage']}; source manifest |"
            )
    lines.extend(
        [
            "",
            "## Eligibility and audit limits",
            "",
            (
                "HUMAN_INPUT: buyer use, qualified exam/reference, product "
                "artifact, physical evidence, rights, risk acceptance and "
                "independent review. Reference-relative findings cannot "
                "establish physical validation."
            ),
            "",
            (
                f"Commit-membership basis: `{reader.membership_basis}`. "
                "Offline exports require a trusted exporter; blob byte "
                "checks alone do not authenticate commit membership."
            ),
            "",
        ]
    )
    manifest = {
        "status": "DEVELOPMENT_SAMPLE",
        "challenge": challenge,
        "profile": profile,
        "standard_rendering": standard_index,
        "evidence_revision": reader.evidence_revision,
        "framework_revision": reader.framework_revision,
        "membership_basis": reader.membership_basis,
        "sources": ledgers,
        "missing_sources": missing,
        "facts": facts,
        "extraction_gaps": gaps,
        "qualification_claim": False,
    }
    return {
        "sample.md": "\n".join(lines),
        "sample.json": json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        "deliverable.schema.json": sources["F2"].text,
        "generation-manifest.json": json.dumps(manifest, indent=2, ensure_ascii=False)
        + "\n",
    }


def write_outputs(root: Path, outputs: dict) -> None:
    expected = {
        "sample.md",
        "sample.json",
        "deliverable.schema.json",
        "generation-manifest.json",
    }
    if set(outputs) != expected:
        raise ValueError("Unrecognized output manifest")
    if any(parent.is_symlink() for parent in [root, *root.parents]):
        raise ValueError("Output path must not contain a symlink")
    if any((root / name).exists() or (root / name).is_symlink() for name in outputs):
        raise ValueError("Output exists; choose a fresh directory")
    root.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        with (root / name).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge")
    parser.add_argument(
        "--standard", choices=sorted(PROFILES), default="nasa-std-7009b"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--framework-ref")
    parser.add_argument("--public-export", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        policy = load_policy()
        if args.challenge not in policy["challenges"]:
            raise ValueError("Unsupported Challenge; no evidence was read")
        if args.public_export and (args.ref != "HEAD" or args.framework_ref):
            raise ValueError("Export receipt owns revisions; do not override")
        reader = (
            BundleReader(args.public_export)
            if args.public_export
            else GitReader(args.repo_root, args.ref, args.framework_ref or args.ref)
        )
        outputs = render(args.challenge, args.standard, reader, policy)
        write_outputs(args.output_dir, outputs)
    except (ValueError, KeyError, OSError, UnicodeError) as error:
        parser.exit(2, f"Refused: {error}\n")
    print("Wrote DEVELOPMENT SAMPLE: Markdown, record, schema and source manifest.")
    return 0
