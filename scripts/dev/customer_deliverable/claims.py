"""Fail-closed, public-artifact citation checks; never scientific acceptance."""

from __future__ import annotations

import ast
import hashlib
import json
import re

SCHEMA = "carbon.customer-deliverable.claim-inventory.v1"
REPORT_SCHEMA = "carbon.customer-deliverable.claim-check.v1"
BASIS = {
    "SOURCE_OBSERVATION",
    "IMPLEMENTATION",
    "SPECIFICATION",
    "HOST_DECLARED_NOT_COMPARED",
}


def parse_json(text):
    """Reuse the public projection's bounded, finite, unique-key parser."""
    from types import SimpleNamespace

    from .package_sections import _json

    return _json(SimpleNamespace(text=text))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("closed claim inventory required")


def _digest(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("claim artifact SHA-256 required")


def _identity(value):
    if type(value) is not str or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_.:-]{0,159}", value
    ):
        raise ValueError("bounded claim identity required")


def locate(data, locator):
    """Locate actual bytes/scalars; missing and ambiguous anchors are failures."""
    _closed(locator, {"kind", "value"})
    text = data.decode("utf-8")
    if locator["kind"] == "file":
        if locator["value"] != "file":
            raise ValueError("file locator required")
        return data
    if locator["kind"] == "text":
        value = locator["value"]
        if type(value) is not str or not value or text.count(value) != 1:
            raise ValueError("unique claim artifact text unavailable")
        return value.encode("utf-8")
    if locator["kind"] == "lines":
        match = re.fullmatch(r"L([1-9][0-9]*)-L([1-9][0-9]*)", locator["value"])
        if not match:
            raise ValueError("explicit claim line range required")
        start, end = map(int, match.groups())
        lines = text.splitlines(keepends=True)
        if start > end or end > len(lines):
            raise ValueError("claim artifact lines unavailable")
        return "".join(lines[start - 1 : end]).encode("utf-8")
    if locator["kind"] == "python-constant":
        _identity(locator["value"])
        values = [
            node.value
            for node in ast.parse(text).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == locator["value"]
                for t in node.targets
            )
        ]
        if (
            len(values) != 1
            or not isinstance(values[0], ast.Constant)
            or type(values[0].value) is not str
        ):
            raise ValueError("unique literal reference version unavailable")
        return values[0].value.encode("utf-8")
    if locator["kind"] == "json-pointer":
        pointer = locator["value"]
        if type(pointer) is not str or not pointer.startswith("/"):
            raise ValueError("explicit claim JSON pointer required")
        value = parse_json(text)
        for part in pointer[1:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if type(value) is dict and key in value:
                value = value[key]
            elif type(value) is list and re.fullmatch(r"0|[1-9][0-9]*", key):
                value = value[int(key)]
            else:
                raise ValueError("claim artifact scalar unavailable")
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    raise ValueError("registered claim locator kind required")


def validate_inventory(inventory):
    _closed(inventory, {"schema", "surfaces", "artifacts", "claims"})
    if inventory["schema"] != SCHEMA:
        raise ValueError("claim inventory schema required")
    for name in ("surfaces", "artifacts", "claims"):
        if type(inventory[name]) is not list or not inventory[name]:
            raise ValueError("nonempty claim inventory required")
    artifact_ids = set()
    from .generate import safe_path

    for artifact in inventory["artifacts"]:
        _closed(artifact, {"id", "path", "sha256"})
        _identity(artifact["id"])
        if artifact["id"] in artifact_ids:
            raise ValueError("duplicate claim artifact")
        artifact_ids.add(artifact["id"])
        safe_path(artifact["path"])
        _digest(artifact["sha256"])
    surfaces = {}
    for surface in inventory["surfaces"]:
        _closed(surface, {"id", "artifact", "claims"})
        _identity(surface["id"])
        if surface["id"] in surfaces or surface["artifact"] not in artifact_ids:
            raise ValueError("unique registered claim surface required")
        if type(surface["claims"]) is not list or not surface["claims"]:
            raise ValueError("nonempty surface claim coverage required")
        surfaces[surface["id"]] = surface
    ids = set()
    for claim in inventory["claims"]:
        _closed(
            claim,
            {
                "id",
                "surface",
                "statement",
                "basis",
                "requirement",
                "citations",
                "reference",
            },
        )
        _identity(claim["id"])
        if claim["id"] in ids or claim["surface"] not in surfaces:
            raise ValueError("unique registered claim required")
        ids.add(claim["id"])
        if claim["basis"] not in BASIS or claim["requirement"] not in {
            "ARTIFACT_TRACEABILITY",
            "VERIFIED",
            "CURRENT_REFERENCE",
        }:
            raise ValueError("registered claim basis/requirement required")
        if type(claim["citations"]) is not list or not claim["citations"]:
            raise ValueError("every claim requires an artifact citation")
        for citation in [claim["statement"], *claim["citations"]]:
            _closed(citation, {"artifact", "locator", "sha256"})
            if citation["artifact"] not in artifact_ids:
                raise ValueError("unregistered claim artifact")
            _digest(citation["sha256"])
        if claim["statement"]["artifact"] != surfaces[claim["surface"]]["artifact"]:
            raise ValueError("claim statement must belong to its surface")
        if claim["reference"] is not None:
            _closed(claim["reference"], {"artifact", "locator", "version"})
            if claim["reference"]["artifact"] not in artifact_ids:
                raise ValueError("registered reference authority artifact required")
            _identity(claim["reference"]["version"])
    for surface in surfaces.values():
        actual = {c["id"] for c in inventory["claims"] if c["surface"] == surface["id"]}
        if (
            len(surface["claims"]) != len(set(surface["claims"]))
            or set(surface["claims"]) != actual
        ):
            raise ValueError("complete surface claim coverage required")


def check_inventory(inventory, read_artifact):
    """Compare registered actual bytes. Loader is called only with registered paths.

    A traceability pass says nothing about the truth/adequacy of the observation.
    VERIFIED has no generic positive path: an artifact or host assertion cannot
    confer scientific or acceptance authority. Such claims need a domain-owned
    verifier and are reported for the Validator, not silently approved here.
    """
    validate_inventory(inventory)
    artifacts = {a["id"]: a for a in inventory["artifacts"]}
    payloads, errors = {}, {}
    for key, artifact in artifacts.items():
        try:
            data = read_artifact(artifact["path"])
            if type(data) is not bytes or not data:
                raise ValueError("artifact missing or empty")
            if sha256(data) != artifact["sha256"]:
                raise ValueError("artifact digest changed")
            payloads[key] = data
        except (OSError, ValueError, UnicodeError, KeyError) as error:
            errors[key] = str(error)
    results = []
    for claim in inventory["claims"]:
        failures = []
        citations = [claim["statement"], *claim["citations"]]
        for citation in citations:
            key = citation["artifact"]
            path = artifacts[key]["path"]
            try:
                if key in errors:
                    raise ValueError(errors[key])
                selected = locate(payloads[key], citation["locator"])
                if sha256(selected) != citation["sha256"]:
                    raise ValueError("cited claim value/text changed")
            except (
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                UnicodeError,
                SyntaxError,
            ) as error:
                failures.append(
                    {"claim": claim["id"], "artifact": path, "reason": str(error)}
                )
        if claim["requirement"] == "VERIFIED":
            failures.append(
                {
                    "claim": claim["id"],
                    "artifact": artifacts[claim["citations"][0]["artifact"]]["path"],
                    "reason": (
                        "HOST_DECLARED_NOT_COMPARED cannot satisfy VERIFIED"
                        if claim["basis"] == "HOST_DECLARED_NOT_COMPARED"
                        else "domain-owned verified evidence not established by citation integrity"
                    ),
                }
            )
        reference = claim["reference"]
        if claim["requirement"] == "CURRENT_REFERENCE" and reference is None:
            failures.append(
                {
                    "claim": claim["id"],
                    "artifact": artifacts[claim["statement"]["artifact"]]["path"],
                    "reason": "current reference authority/version missing",
                }
            )
        if (
            claim["requirement"] == "CURRENT_REFERENCE"
            and claim["basis"] == "HOST_DECLARED_NOT_COMPARED"
        ):
            failures.append(
                {
                    "claim": claim["id"],
                    "artifact": artifacts[claim["statement"]["artifact"]]["path"],
                    "reason": "HOST_DECLARED_NOT_COMPARED cannot establish current reference authority",
                }
            )
        if reference is not None:
            key = reference["artifact"]
            try:
                if key in errors:
                    raise ValueError(errors[key])
                current = locate(payloads[key], reference["locator"]).decode("utf-8")
                # JSON pointers return canonical JSON; text locators return text.
                if reference["locator"]["kind"] == "json-pointer":
                    current = json.loads(current)
                if current != reference["version"]:
                    raise ValueError("reference version superseded or mismatched")
            except (
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                UnicodeError,
                SyntaxError,
            ) as error:
                failures.append(
                    {
                        "claim": claim["id"],
                        "artifact": artifacts[key]["path"],
                        "reason": str(error),
                    }
                )
        results.append(
            {
                "claim": claim["id"],
                "surface": claim["surface"],
                "basis": claim["basis"],
                "requirement": claim["requirement"],
                "status": "FAIL" if failures else "PASS",
                "citations_checked": len(citations),
                "failures": failures,
            }
        )
    for key, reason in errors.items():
        if not any(
            f["artifact"] == artifacts[key]["path"]
            for row in results
            for f in row["failures"]
        ):
            results.append(
                {
                    "claim": "inventory.artifact." + key,
                    "surface": "inventory",
                    "basis": "IMPLEMENTATION",
                    "requirement": "ARTIFACT_TRACEABILITY",
                    "status": "FAIL",
                    "citations_checked": 0,
                    "failures": [
                        {
                            "claim": "inventory.artifact." + key,
                            "artifact": artifacts[key]["path"],
                            "reason": reason,
                        }
                    ],
                }
            )
    return {
        "schema": REPORT_SCHEMA,
        "status": "FAIL" if any(r["status"] == "FAIL" for r in results) else "PASS",
        "basis": "ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE",
        "artifacts_examined": len(artifacts),
        "claims_examined": len(results),
        "results": results,
        "qualification_claim": False,
    }


def require_pass(report):
    if report["status"] != "PASS":
        failures = [
            f"{f['claim']}: {f['artifact']}: {f['reason']}"
            for row in report["results"]
            for f in row["failures"]
        ]
        raise ValueError("Claim citation FAIL:\n" + "\n".join(failures))
    return report


def generated_claims(manifest):
    """Index every sourced fact/row and crosswalk mapping; GAP is no assertion."""
    claims = []
    for fact in manifest["facts"]:
        claims.append(
            {
                "id": "package.fact." + fact["id"],
                "surface": "package",
                "value": fact,
                "sources": [fact["source"]],
                "basis": "SOURCE_OBSERVATION",
            }
        )
    for surface, section in manifest["package_evidence"]["sections"].items():
        for row in section["rows"]:
            if row["coverage"] != "GAP":
                claims.append(
                    {
                        "id": surface + "." + row["field"],
                        "surface": surface,
                        "value": row,
                        "sources": row["evidence_refs"],
                        "basis": "SOURCE_OBSERVATION",
                    }
                )
    for row in manifest["credibility_evidence"]["matrix"]:
        if row["coverage"] != "GAP":
            claims.append(
                {
                    "id": "crosswalk." + row["requirement_id"],
                    "surface": "credibility",
                    "value": row,
                    "sources": row["evidence_refs"],
                    "basis": "SOURCE_OBSERVATION",
                }
            )
    # Normative mapping claims cite the framework, not an assessed standard.
    claims.append(
        {
            "id": "crosswalk.standard-index",
            "surface": "credibility",
            "value": manifest["standard_rendering"],
            "sources": ["F3"],
            "basis": "SPECIFICATION",
        }
    )
    risk = manifest["credibility_evidence"]["risk_informed_plan"]
    for name in (
        "context_of_use",
        "model_influence",
        "decision_consequence",
        "required_credibility",
    ):
        value = risk[name]
        if value is not None and (
            name == "context_of_use" or value["value"] is not None
        ):
            claims.append(
                {
                    "id": "crosswalk.host." + name,
                    "surface": "credibility",
                    "value": value,
                    "sources": ["P8"],
                    "basis": "HOST_DECLARED_NOT_COMPARED",
                }
            )
    return claims


def _comparable_provenance(value, field=None):
    """Keep every assertion; normalize only valid Git citation revisions."""
    if type(value) is dict:
        ledger = {"id", "path", "revision", "git_blob", "sha256", "url"} <= set(value)
        return {
            key: (
                "COMMIT"
                if ledger
                and key == "revision"
                and type(item) is str
                and re.fullmatch(r"[0-9a-f]{40}", item)
                else _comparable_provenance(item, key)
            )
            for key, item in value.items()
        }
    if type(value) is list:
        return [_comparable_provenance(item) for item in value]
    if type(value) is str:
        if field in {"evidence_revision", "framework_revision"} and re.fullmatch(
            r"[0-9a-f]{40}", value
        ):
            return "COMMIT"
        if field in {"url", "citation", "context_citation"}:
            return re.sub(
                r"https://github\.com/carbonphysicsai/Carbon/blob/[0-9a-f]{40}/",
                "https://github.com/carbonphysicsai/Carbon/blob/COMMIT/",
                value,
            )
    return value


def check_generated_manifest(manifest, reader, policy):
    """Re-read registered artifacts and reproduce claims to catch stale output.

    This checks what the public source records, not whether its physics is true.
    Fresh sources are read at the verifier's selected current commit/export;
    the old manifest cannot choose a historical commit to make itself pass.
    """
    from .generate import REPOSITORY, GitReader, _render_core

    fresh = json.loads(
        _render_core(
            manifest["challenge"],
            manifest["profile"],
            reader,
            policy,
        )["generation-manifest.json"]
    )
    old_claims = generated_claims(manifest)
    fresh_claims = {c["id"]: c for c in generated_claims(fresh)}
    old_sources = {s["id"]: s for s in manifest["sources"]}
    fresh_sources = {s["id"]: s for s in fresh["sources"]}
    results = []
    if len(old_sources) != len(manifest["sources"]) or set(old_sources) != set(
        fresh_sources
    ):
        results.append(
            {
                "claim": "source-ledger.coverage",
                "surface": "package",
                "basis": "IMPLEMENTATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 0,
                "failures": [
                    {
                        "claim": "source-ledger.coverage",
                        "artifact": "generation-manifest.json / registered public source policy",
                        "reason": "source ledger duplicate, missing or unregistered artifact",
                    }
                ],
            }
        )
    if manifest.get("claim_inventory") != old_claims:
        results.append(
            {
                "claim": "claim-inventory.coverage",
                "surface": "package",
                "basis": "IMPLEMENTATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 0,
                "failures": [
                    {
                        "claim": "claim-inventory.coverage",
                        "artifact": "generation-manifest.json",
                        "reason": "complete claim inventory missing or differs from rendered claims",
                    }
                ],
            }
        )
    for source_id in sorted(set(old_sources) & set(fresh_sources)):
        old = old_sources[source_id]
        current = fresh_sources[source_id]
        try:
            if not re.fullmatch(r"[0-9a-f]{40}", old["revision"]):
                raise ValueError("invalid cited commit")
            framework_ids = {s["id"] for s in policy["framework"]}
            role_revision = (
                manifest["framework_revision"]
                if source_id in framework_ids
                else manifest["evidence_revision"]
            )
            if old["revision"] != role_revision:
                raise ValueError("source revision does not bind manifest role/revision")
            expected_url = f"https://github.com/{REPOSITORY}/blob/{old['revision']}/{current['path']}"
            if old["url"] != expected_url:
                raise ValueError(
                    "cited public URL does not bind registered artifact/commit"
                )
            if isinstance(reader, GitReader) and old["revision"] != current["revision"]:
                original = GitReader(reader.root, old["revision"], old["revision"]).get(
                    {"id": source_id, "path": current["path"]}
                )
                if (
                    original is None
                    or original.ledger()["sha256"] != old["sha256"]
                    or original.blob != old["git_blob"]
                ):
                    raise ValueError(
                        "original cited commit artifact unavailable or mismatched"
                    )
        except (ValueError, KeyError, TypeError, OSError) as error:
            results.append(
                {
                    "claim": "source-ledger." + source_id,
                    "surface": "package",
                    "basis": "SOURCE_OBSERVATION",
                    "requirement": "ARTIFACT_TRACEABILITY",
                    "status": "FAIL",
                    "citations_checked": 1,
                    "failures": [
                        {
                            "claim": "source-ledger." + source_id,
                            "artifact": current["path"],
                            "reason": str(error),
                        }
                    ],
                }
            )
    for claim in old_claims:
        failures = []
        for source_id in claim["sources"]:
            old = old_sources.get(source_id)
            current = fresh_sources.get(source_id)
            path = (old or current or {}).get("path", "registered source " + source_id)
            if old is None or current is None:
                failures.append(
                    {
                        "claim": claim["id"],
                        "artifact": path,
                        "reason": "cited artifact missing",
                    }
                )
            elif (
                old["path"] != current["path"]
                or old["sha256"] != current["sha256"]
                or old["git_blob"] != current["git_blob"]
            ):
                failures.append(
                    {
                        "claim": claim["id"],
                        "artifact": path,
                        "reason": "cited artifact digest/identity changed",
                    }
                )
        current = fresh_claims.get(claim["id"])

        if current is None or _comparable_provenance(claim) != _comparable_provenance(
            current
        ):
            failures.append(
                {
                    "claim": claim["id"],
                    "artifact": ", ".join(
                        (old_sources.get(s) or {}).get("path", s)
                        for s in claim["sources"]
                    ),
                    "reason": "claim value, basis, scope or locator differs from actual registered artifact",
                }
            )
        results.append(
            {
                "claim": claim["id"],
                "surface": claim["surface"],
                "basis": claim["basis"],
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL" if failures else "PASS",
                "citations_checked": len(claim["sources"]),
                "failures": failures,
            }
        )
    # Removed claims must not hide a currently rendered affirmative statement.
    old_ids = {c["id"] for c in old_claims}
    for key in sorted(set(fresh_claims) - old_ids):
        results.append(
            {
                "claim": key,
                "surface": fresh_claims[key]["surface"],
                "basis": fresh_claims[key]["basis"],
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 0,
                "failures": [
                    {
                        "claim": key,
                        "artifact": "generation-manifest.json",
                        "reason": "claim missing from prior inventory",
                    }
                ],
            }
        )
    for field in ("qualification_claim",):
        if manifest[field] is not False:
            results.append(
                {
                    "claim": field,
                    "surface": "package",
                    "basis": "SOURCE_OBSERVATION",
                    "requirement": "VERIFIED",
                    "status": "FAIL",
                    "citations_checked": 0,
                    "failures": [
                        {
                            "claim": field,
                            "artifact": "generation-manifest.json",
                            "reason": "qualification not established",
                        }
                    ],
                }
            )
    # This coverage control also catches future/unindexed quantitative fields,
    # altered risk values, and affirmative claims outside the familiar rows.
    allowed_urls = {s["url"] for s in manifest["sources"]}

    def broken_citations(value, path="manifest", field=None):
        if type(value) is dict:
            for key, item in value.items():
                if path == "manifest" and key in {"claim_inventory", "claim_check"}:
                    continue
                yield from broken_citations(item, path + "." + key, key)
        elif type(value) is list:
            for index, item in enumerate(value):
                yield from broken_citations(item, path + f"[{index}]")
        elif type(value) is str and field in {"citation", "url", "context_citation"}:
            urls = re.findall(
                r"https://github\.com/carbonphysicsai/Carbon/blob/[0-9a-f]{40}/[^)\s]+",
                value,
            )
            if any(url.split("#", 1)[0] not in allowed_urls for url in urls):
                yield path

    for path in broken_citations(manifest):
        results.append(
            {
                "claim": path,
                "surface": "package",
                "basis": "SOURCE_OBSERVATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 1,
                "failures": [
                    {
                        "claim": path,
                        "artifact": "registered public source ledger",
                        "reason": "citation does not bind an actually checked original artifact/commit",
                    }
                ],
            }
        )
    # Only the derived top-level check/index are excluded. Source ledgers,
    # citation strings, unknown nested fields and authority flags are checked.

    def differences(old, new, path="manifest"):
        if type(old) is dict and type(new) is dict:
            keys = set(old) | set(new)
            if path == "manifest":
                keys -= {"claim_inventory", "claim_check"}
            for key in sorted(keys):
                child = path + "." + key
                if key not in old or key not in new:
                    yield child
                else:
                    yield from differences(old[key], new[key], child)
        elif type(old) is list and type(new) is list:
            if len(old) != len(new):
                yield path
            else:
                for index, (a, b) in enumerate(zip(old, new)):
                    yield from differences(a, b, path + f"[{index}]")
        elif type(old) is not type(new) or old != new:
            yield path

    for path in differences(
        _comparable_provenance(manifest), _comparable_provenance(fresh)
    ):
        results.append(
            {
                "claim": path,
                "surface": "package",
                "basis": "SOURCE_OBSERVATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 0,
                "failures": [
                    {
                        "claim": path,
                        "artifact": "generation-manifest.json / registered public source policy",
                        "reason": "unindexed or changed claim differs from artifact-derived rendering",
                    }
                ],
            }
        )
    report = {
        "schema": REPORT_SCHEMA,
        "status": (
            "PASS"
            if results and all(r["status"] == "PASS" for r in results)
            else "FAIL"
        ),
        "basis": "ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE",
        "artifacts_examined": len(fresh_sources),
        "claims_examined": len(results),
        "results": results,
        "qualification_claim": False,
    }
    stored = manifest.get("claim_check")
    if stored is not None and stored != report:
        results.append(
            {
                "claim": "stored-check-report.integrity",
                "surface": "package",
                "basis": "IMPLEMENTATION",
                "requirement": "ARTIFACT_TRACEABILITY",
                "status": "FAIL",
                "citations_checked": 0,
                "failures": [
                    {
                        "claim": "stored-check-report.integrity",
                        "artifact": "generation-manifest.json",
                        "reason": "claimed check status/counts/basis differ from actual recomputed checks",
                    }
                ],
            }
        )
        report["status"] = "FAIL"
        report["claims_examined"] = len(results)
    return report


def check_package_outputs(manifest, outputs, reader, policy):
    """Validate actual shipped files; a good manifest cannot bless edited prose."""
    from .generate import Source, render

    report = require_pass(check_generated_manifest(manifest, reader, policy))
    ledgers = {s["id"]: s for s in manifest["sources"]}

    class OriginalCitationReader:
        # Read current actual bytes, retain already-checked original URLs. This
        # never selects old evidence to hide a superseding current artifact.
        evidence_revision = manifest["evidence_revision"]
        framework_revision = manifest["framework_revision"]
        membership_basis = manifest["membership_basis"]

        def get(self, spec, framework=False):
            source = reader.get(spec, framework=framework)
            if source is None:
                return None
            return Source(
                source.id,
                source.path,
                ledgers[source.id]["revision"],
                source.blob,
                source.text,
            )

    expected = render(
        manifest["challenge"], manifest["profile"], OriginalCitationReader(), policy
    )
    checked = 0
    for name in ("sample.md", "sample.json", "deliverable.schema.json"):
        if (
            name not in outputs
            or type(outputs[name]) is not str
            or outputs[name] != expected[name]
        ):
            raise ValueError(
                f"Claim citation FAIL: package.output.{name}: {name}: missing or changed customer claims differ from checked artifacts"
            )
        checked += 1
    report["output_files_examined"] = checked
    return report
