"""Public development evidence indexing; never risk or acceptance adjudication."""

from __future__ import annotations

import copy
import hashlib

from .package_sections import _closed, _digest, _json, _token

SCHEMA = "carbon.customer-deliverable.credibility-evidence.v1"
CONTEXT_SCHEMA = "carbon.customer-deliverable.credibility-context.v1"
ADVERSE = {"FAIL", "UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"}
OBLIGATIONS = {
    "D01": ("Intended use and decision consequence", "Customer/program use authority"),
    "D02": (
        "Requirements, criteria and approving authority",
        "Customer/science authority",
    ),
    "D03": (
        "Applicable population, coverage and exclusions",
        "Science/customer authority",
    ),
    "D04": (
        "Reference verification and physical adequacy",
        "Reference/science authority",
    ),
    "D05": ("Artifact-bound requirement evidence", "Science/product authority"),
    "D06": (
        "Uncertainty, sensitivity and applicability",
        "Science/statistics authority",
    ),
    "D07": (
        "Adverse findings, robustness and retest",
        "Independent assessment authority",
    ),
    "D08": (
        "Artifact/runtime provenance and reproducibility",
        "Engineering/product authority",
    ),
    "D09": (
        "Fallback, abstention and unavailable-reference handling",
        "Customer/operations authority",
    ),
    "D10": (
        "Limitations, missing proof and change impact",
        "Customer/science authority",
    ),
    "D11": (
        "Audit, review independence, rights and acceptance",
        "Customer/accreditation authority",
    ),
}
DOD_QUESTIONS = (
    (
        "VV&A-USE",
        "What exact purpose, use and consequences are being assessed?",
        ["D01", "D03", "D09"],
    ),
    (
        "VV&A-CRITERIA",
        "Who approved the criteria and traceability to the intended use?",
        ["D02", "D05"],
    ),
    (
        "VV&A-REFERENT",
        "What supports reference adequacy and physical comparison?",
        ["D04", "D05", "D06"],
    ),
    (
        "VV&A-ADVERSE",
        "Which discrepancies, limits and missing tests remain?",
        ["D07", "D10"],
    ),
    (
        "VV&A-CONFIG",
        "Which exact artifact, runtime and evidence versions were inspected?",
        ["D08", "D11"],
    ),
    (
        "VV&A-ACCEPT",
        "Who tailors the program and independently decides accreditation?",
        ["D01", "D11"],
    ),
)


def _context(source, challenge, identity, contract_source):
    if source is None:
        return None, "P8: public risk/context declaration unavailable"
    try:
        document = _json(source)
        _closed(
            document,
            {
                "schema",
                "mode",
                "challenge",
                "disclosure",
                "identity",
                "context_of_use",
                "model_influence",
                "decision_consequence",
                "required_credibility",
            },
        )
        if (
            document["schema"] != CONTEXT_SCHEMA
            or document["mode"] != "DEVELOPMENT_SAMPLE"
            or document["challenge"] != challenge
        ):
            raise ValueError("development context required")
        _closed(document["disclosure"], {"kind", "evidence"})
        evidence = document["disclosure"]["evidence"]
        if (
            document["disclosure"]["kind"] not in {"PUBLIC", "RELEASED"}
            or type(evidence) is not str
            or not evidence.startswith("https://")
            or len(evidence) > 500
        ):
            raise ValueError("public disclosure required")
        _closed(
            document["identity"],
            {
                "model_artifact_hash",
                "reference_image_digest",
                "physics_contract_digest",
            },
        )
        for value in document["identity"].values():
            _digest(value)
        if identity is None or document["identity"] != identity:
            raise ValueError("matched package identity required")
        if (
            contract_source is None
            or identity["physics_contract_digest"]
            != "sha256:"
            + hashlib.sha256(contract_source.text.encode("utf-8")).hexdigest()
        ):
            raise ValueError("matched committed contract required")
        _closed(document["context_of_use"], {"id", "version"})
        for value in document["context_of_use"].values():
            _token(value)
            if value in {"HUMAN_INPUT", "UNRESOLVED", "NOT_ASSESSED"}:
                raise ValueError("named development use required")
        for field in (
            "model_influence",
            "decision_consequence",
            "required_credibility",
        ):
            declaration = document[field]
            _closed(declaration, {"value", "authority_ref"})
            if declaration["value"] is None:
                if declaration["authority_ref"] is not None:
                    raise ValueError("unknown declaration required")
            else:
                _token(declaration["value"])
                if declaration["value"] in {
                    "HUMAN_INPUT",
                    "UNRESOLVED",
                    "NOT_ASSESSED",
                }:
                    raise ValueError("use null for unknown declaration")
                _digest(declaration["authority_ref"])
        return document, None
    except (ValueError, KeyError, TypeError, AttributeError):
        return (
            None,
            "P8: risk/context declaration unavailable: malformed, undisclosed or unmatched package identity",
        )


def build_credibility(package, sections, facts, findings, sources, crosswalk, profile):
    """Wrap normalized facts; source outcomes never approve a requirement."""
    context_source = sources.get("P8")
    context, context_gap = _context(
        context_source, package["challenge"], package["identity"], sources.get("P3")
    )
    matrix = []
    for component_name, component in package["sections"].items():
        for observation in component["rows"]:
            key = component_name + "." + observation["field"]
            matrix.append(
                {
                    "requirement_id": "DEVREQ." + key,
                    "kind": "DEVELOPMENT_EVIDENCE_OBLIGATION_NOT_CUSTOMER_CRITERION",
                    "description": observation["label"],
                    "sections": component["d_sections"],
                    "basis": (
                        "physical"
                        if observation["field"].endswith("physical_validation")
                        else component["basis"]
                    ),
                    "coverage": observation["coverage"],
                    "value": observation["value"],
                    "unit": observation["unit"],
                    "sample_count": observation["sample_count"],
                    "measurement_version": observation.get("measurement_version"),
                    "identity": (
                        package["identity"]
                        if "P4" in observation["evidence_refs"]
                        else None
                    ),
                    "identity_scope": (
                        "DECLARED_PACKAGE_PROJECTION"
                        if "P4" in observation["evidence_refs"]
                        else "SOURCE_SCOPE_ONLY_NO_PRODUCT_BINDING"
                    ),
                    "source_versions": [
                        sources[ref].ledger() for ref in observation["evidence_refs"]
                    ],
                    "measured": observation["measured"],
                    "source_outcome": observation["outcome"],
                    "requirement_outcome": "NOT_ASSESSED",
                    "criterion": None,
                    "criterion_authority": "HUMAN_INPUT",
                    "evidence_refs": observation["evidence_refs"],
                    "locator": observation["locator"],
                    "citation": observation["citation"],
                    "gap": observation["reason"],
                    "adverse_links": (
                        ["PACKAGE_" + key]
                        if any(f["id"] == "PACKAGE_" + key for f in findings)
                        else []
                    ),
                }
            )
    for fact in facts:
        if fact["kind"] in {"review", "metadata", "rebuilds"}:
            homes = ["D08", "D11"]
        else:
            homes = ["D07", "D10", "D11"]
        matrix.append(
            {
                "requirement_id": "DEVREQ.historical." + fact["id"],
                "kind": "HISTORICAL_OBSERVATION_NOT_CURRENT_PRODUCT_ACCEPTANCE",
                "description": fact["label"],
                "sections": homes,
                "basis": fact["basis"],
                "coverage": "EVIDENCED",
                "value": fact["value"],
                "unit": None,
                "sample_count": None,
                "measurement_version": None,
                "identity": None,
                "identity_scope": "HISTORICAL_SOURCE_ONLY_NO_PRODUCT_BINDING",
                "source_versions": [sources[fact["source"]].ledger()],
                "measured": False,
                "source_outcome": fact["outcome"],
                "requirement_outcome": "NOT_ASSESSED",
                "criterion": None,
                "criterion_authority": "HUMAN_INPUT",
                "evidence_refs": [fact["source"]],
                "locator": fact["locator"],
                "citation": fact["citation"],
                "gap": None,
                "adverse_links": (
                    [fact["id"]] if any(f["id"] == fact["id"] for f in findings) else []
                ),
            }
        )
    obligations = []
    for sid, (description, owner) in OBLIGATIONS.items():
        linked = [row for row in matrix if sid in row["sections"]]
        obligations.append(
            {
                "id": "DEVREQ." + sid,
                "description": description,
                "coverage": sections[sid]["coverage"],
                "supporting_rows": [row["requirement_id"] for row in linked],
                "evidence_refs": sorted(
                    {ref for row in linked for ref in row["evidence_refs"]}
                ),
                "source_outcomes": sorted({row["source_outcome"] for row in linked}),
                "criterion": None,
                "authority": "HUMAN_INPUT",
                "requirement_outcome": "NOT_ASSESSED",
                "owner_role": owner,
                "next_proof": list(sections[sid]["gaps"]),
            }
        )

    def declaration(field):
        return {
            "value": None if context is None else context[field]["value"],
            "authority_ref": (
                None if context is None else context[field]["authority_ref"]
            ),
            "basis": (
                "HUMAN_INPUT"
                if context is None or context[field]["value"] is None
                else "PUBLIC_DECLARATION_NOT_AUTHENTICATED_ACCEPTANCE"
            ),
            "citation": None if context is None else context_source.cite("/" + field),
        }

    plan = {
        "context_of_use": None if context is None else context["context_of_use"],
        "context_citation": (
            None if context is None else context_source.cite("/context_of_use")
        ),
        "model_influence": declaration("model_influence"),
        "decision_consequence": declaration("decision_consequence"),
        "required_credibility": declaration("required_credibility"),
        "risk_combination": {
            "form": "model influence × decision consequence",
            "value": None,
            "rule": None,
            "authority": "HUMAN_INPUT",
        },
        "goals": obligations,
        "gaps": ([context_gap] if context_gap else [])
        + [
            "HUMAN_INPUT: accepted use, risk combination rule, credibility criteria and applicability",
            "HUMAN_INPUT: independent physical evidence, competence/independence, rights and acceptance",
        ],
    }
    defense = []
    for qid, question, homes in DOD_QUESTIONS:
        linked = [row for row in matrix if set(homes) & set(row["sections"])]
        has_evidence = any(row["coverage"] == "EVIDENCED" for row in linked)
        defense.append(
            {
                "id": qid,
                "question": question,
                "sections": homes,
                "coverage": "PARTIAL" if has_evidence else "GAP",
                "answer": (
                    "Indexed development evidence only; customer judgment remains open"
                    if has_evidence
                    else "Evidence unavailable for this question"
                ),
                "evidence_rows": [row["requirement_id"] for row in linked],
                "anchors": [crosswalk[sid][5] for sid in homes],
                "mapping_source": "F3",
                "accreditation_outcome": "NOT_ASSESSED",
                "customer_action": [
                    OBLIGATIONS[sid][0] + ": HUMAN_INPUT" for sid in homes
                ],
            }
        )
    return copy.deepcopy(
        {
            "schema": SCHEMA,
            "mode": "DEVELOPMENT_SAMPLE",
            "profile": profile,
            "qualification_claim": False,
            "compliance_claim": False,
            "accreditation_claim": False,
            "clause_complete": False,
            "identity": package["identity"],
            "identity_basis": package["identity_basis"],
            "matrix": matrix,
            "risk_informed_plan": plan,
            "defense_vva": defense,
            "retained_findings": findings,
            "limits": [
                "Development obligation IDs are not customer requirements or normative standard clause IDs",
                "EVIDENCED coverage can retain FAIL; source PASS cannot issue requirement acceptance",
                "MMS supports code verification only; reference-relative evidence is not physical validation",
                "Host-declared context/use/risk and authority_ref are assertions, not authenticated applicability or acceptance decisions",
                "Historical source outcomes retain their original reference/contract meaning; annotate, never re-score or infer current eligibility",
                "ASME V&V 40 clause IDs and cross-domain applicability remain HUMAN_INPUT",
                "DoDI mappings are contents-only anchors; tailoring and accreditation remain HUMAN_INPUT",
            ],
        }
    )


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def credibility_markdown(annex):
    lines = [
        "## Credibility matrix — DEVELOPMENT CROSSWALK ONLY",
        "",
        "Development evidence obligations, not accepted customer criteria. Coverage and source outcome are separate; all requirement outcomes are NOT_ASSESSED.",
        "",
        "| Obligation / homes | Coverage / basis | Source outcome / requirement outcome | Evidence / gap |",
        "| --- | --- | --- | --- |",
    ]
    for row in annex["matrix"]:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    row["requirement_id"] + " / " + ", ".join(row["sections"]),
                    row["coverage"] + " / " + row["basis"],
                    row["source_outcome"] + " / " + row["requirement_outcome"],
                    row["gap"] or row["citation"] or "HUMAN_INPUT",
                )
            )
            + " |"
        )
    plan = annex["risk_informed_plan"]
    lines.extend(
        [
            "",
            "### Risk-informed credibility plan",
            "",
            "Model influence × decision consequence is a planning relationship; no numerical scale, combination rule or acceptance level is inferred.",
            "",
        ]
    )
    for field in (
        "context_of_use",
        "model_influence",
        "decision_consequence",
        "required_credibility",
    ):
        value = plan[field]
        if field != "context_of_use":
            value = value["value"]
        citation = (
            plan["context_citation"]
            if field == "context_of_use"
            else plan[field]["citation"]
        )
        lines.append(
            f"- {field}: {_cell(value if value is not None else 'HUMAN_INPUT')}; {_cell(citation or 'authority HUMAN_INPUT')}."
        )
    lines.extend(
        ["", "| Goal | Indexed coverage | Next proof / owner |", "| --- | --- | --- |"]
    )
    for goal in plan["goals"]:
        lines.append(
            f"| {goal['id']}: {goal['description']} | {goal['coverage']} | {_cell('; '.join(goal['next_proof']))}; {goal['owner_role']}, HUMAN_INPUT |"
        )
    lines.extend(
        [
            "",
            *["- " + gap for gap in plan["gaps"]],
            "",
            "### Defense VV&A questions — evidence support, not accreditation",
            "",
            "MIL-STD-3022 template anchors and DoDI contents-only anchors index the same facts. Program tailoring, independent review and accreditation stay with the designated customer authority.",
            "",
            "| Question | Coverage | Evidence rows / template anchors | Customer-owned action |",
            "| --- | --- | --- | --- |",
        ]
    )
    for question in annex["defense_vva"]:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    question["question"],
                    question["coverage"],
                    ", ".join(question["evidence_rows"])
                    + "; "
                    + "; ".join(question["anchors"]),
                    "; ".join(question["customer_action"]),
                )
            )
            + " |"
        )
    lines.extend(["", *["- " + limit for limit in annex["limits"]], ""])
    return lines
