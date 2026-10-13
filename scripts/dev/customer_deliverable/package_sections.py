"""Allow-listed DEVELOPMENT package facts, never evaluation or qualification.

The optional public projection is a document-export transport, not a PLT-01,
Model Card, trust-map or decision API. Producer custody/disclosure assertions
remain assertions. Only registered committed blobs are supplied by generate.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

from carbon.trust_map.acceptance import digest, validate_acceptance

PROJECTION_SCHEMA = "carbon.customer-deliverable.public-package-projection.v1"
PACKAGE_SCHEMA = "carbon.customer-deliverable.package-evidence.v1"
OUTCOMES = {
    "PASS",
    "FAIL",
    "UNRESOLVED",
    "NOT_ASSESSED",
    "FAILED_REFERENCE",
    "FAILED_INFRA",
}
GROUPS = {
    "law_checks": (
        "Physics contract and law-check report",
        ["D02", "D05", "D07"],
        "reference-relative",
    ),
    "model_card": ("Model card", ["D05", "D06", "D08"], "reference-relative"),
    "trust_map": ("Trust map", ["D03", "D05", "D06", "D09"], "reference-relative"),
    "solver_verification": (
        "Solver code verification (MMS)",
        ["D04", "D08"],
        "verification",
    ),
    "decision_evidence": ("Decision evidence", ["D05", "D07"], "decision-value"),
}
CARD_FIELDS = {
    "accuracy_overall": "Overall accuracy",
    "accuracy_near_limits": "Accuracy near limits",
    "robustness": "Robustness / local sensitivity",
    "extrapolation": "Recorded stretch-set error growth in the declared domain",
    "uncertainty_calibration": "Reference-relative uncertainty calibration",
    "speedup_equal_accuracy": "Speed-up at equal accuracy",
    "inference_latency": "Inference latency",
    "training_cost": "Controlled rebuild cost",
}


def _number(value, *, nonnegative=False):
    if type(value) not in (int, float):
        raise ValueError("finite number required")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("finite number required")
    if nonnegative and value < 0:
        raise ValueError("nonnegative number required")
    return value


def _count(value, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError("count required")
    return value


def _digest(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("digest required")
    return value


def _token(value):
    if type(value) is not str or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_.:-]{0,79}", value
    ):
        raise ValueError("registered token required")
    return value


def _unit(value):
    if type(value) is not str or not re.fullmatch(r"[\w°µ·*/^ .%()+-]{1,60}", value):
        raise ValueError("unit required")
    return value


def _outcome(value):
    if value not in OUTCOMES:
        raise ValueError("outcome required")
    return value


def _closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("closed public shape required")


def _json(source):
    # Bounded parse, duplicate-key refusal and finite values. No exception/input
    # text crosses the generic GAP branch.
    if len(source.text.encode("utf-8")) > 2_000_000:
        raise ValueError("public aggregate too large")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    return json.loads(
        source.text,
        object_pairs_hook=object_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )


def _row(
    field,
    label,
    value=None,
    *,
    unit=None,
    count=None,
    outcome="NOT_ASSESSED",
    source=None,
    locator="file",
    reason=None,
    measured=True,
    measurement_version=None,
):
    return {
        "field": field,
        "label": label,
        "coverage": "GAP" if reason is not None else "EVIDENCED",
        "value": None if reason is not None else value,
        "unit": unit,
        "sample_count": count,
        "outcome": outcome,
        "reason": reason,
        "measured": measured and reason is None,
        "measurement_version": measurement_version,
        "evidence_refs": [] if source is None else [source.id],
        "locator": locator,
        "citation": None if source is None else source.cite(locator),
        "floor": None,
        "floor_authority": "HUMAN_INPUT",
    }


def _gap(field, label, reason, source=None, outcome="NOT_ASSESSED"):
    return _row(field, label, reason=reason, source=source, outcome=outcome)


def _projection(source, challenge):
    document = _json(source)
    _closed(
        document,
        {
            "schema",
            "mode",
            "challenge",
            "disclosure",
            "identity",
            "law_checks",
            "model_card",
            "trust_map",
            "verify_r",
            "equal_budget",
        },
    )
    if (
        document["schema"] != PROJECTION_SCHEMA
        or document["mode"] != "DEVELOPMENT_SAMPLE"
        or document["challenge"] != challenge
    ):
        raise ValueError("development projection identity mismatch")
    _closed(document["disclosure"], {"kind", "evidence"})
    if document["disclosure"]["kind"] not in {"PUBLIC", "RELEASED"}:
        raise ValueError("public or released material required")
    evidence = document["disclosure"]["evidence"]
    if (
        type(evidence) is not str
        or not evidence.startswith("https://")
        or len(evidence) > 500
    ):
        raise ValueError("disclosure evidence required")
    _closed(
        document["identity"],
        {"model_artifact_hash", "reference_image_digest", "physics_contract_digest"},
    )
    for value in document["identity"].values():
        _digest(value)
    return document


def _draft(source, family):
    document = _json(source)
    if (
        type(document) is not dict
        or document.get("schema") != "carbon.physics-contract.draft.v1"
        or document.get("challenge") != family
        or document.get("runtime_enabled") is not False
    ):
        raise ValueError("draft contract identity mismatch")
    laws = document["laws"]
    if type(laws) is not list or not laws or len(laws) > 128:
        raise ValueError("law list required")
    ids = [_token(law["id"]) for law in laws]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate law")
    return document, ids


def _law_rows(projection, source, contract_source, family):
    rows = [
        _gap(
            "law_results",
            "Measured law checks / gate outcomes",
            "PLT-01 public aggregate law-check output unavailable",
            source,
        )
    ]
    if projection is None or projection["law_checks"] is None:
        return rows
    try:
        _, law_ids = _draft(contract_source, family)
        contract_digest = (
            "sha256:" + hashlib.sha256(contract_source.text.encode("utf-8")).hexdigest()
        )
        if projection["identity"]["physics_contract_digest"] != contract_digest:
            raise ValueError("contract digest mismatch")
        report = projection["law_checks"]
        _closed(report, {"producer", "measurement_version", "laws"})
        if report["producer"] != "PLT-01":
            raise ValueError("PLT-01 projection required")
        _token(report["measurement_version"])
        if type(report["laws"]) is not list or not report["laws"]:
            raise ValueError("nonempty law results required")
        observed = set()
        rows = []
        for i, law in enumerate(report["laws"]):
            _closed(
                law,
                {
                    "id",
                    "sample_count",
                    "violation_rate",
                    "residual_median",
                    "unit",
                    "outcome",
                    "adopted",
                    "calibration_image_digest",
                },
            )
            name = _token(law["id"])
            if name not in law_ids or name in observed:
                raise ValueError("law identity mismatch")
            observed.add(name)
            count = _count(law["sample_count"], positive=True)
            rate = _number(law["violation_rate"], nonnegative=True)
            if rate > 1 or type(law["adopted"]) is not bool:
                raise ValueError("law rate/adoption invalid")
            if (
                _digest(law["calibration_image_digest"])
                != projection["identity"]["reference_image_digest"]
            ):
                raise ValueError("calibration image mismatch")
            outcome = _outcome(law["outcome"])
            # A packet draft does not register a gate, whatever the projection
            # claims. Retain the diagnostic measurement and its original result.
            label = name + " (diagnostic; gate adoption HUMAN_INPUT)"
            row = _row(
                name + ".violation_rate",
                label,
                rate,
                unit="fraction",
                count=count,
                outcome=outcome,
                source=source,
                locator=f"/law_checks/laws/{i}/violation_rate",
                measurement_version=report["measurement_version"],
            )
            row["reported_adopted"] = law["adopted"]
            row["gate_authority"] = "HUMAN_INPUT_DRAFT_CONTRACT"
            row["gate_input_eligible"] = False
            rows.append(row)
            if law["residual_median"] is None:
                rows.append(
                    _gap(
                        name + ".residual",
                        name + " residual",
                        "Residual not measured",
                        source,
                    )
                )
            else:
                rows.append(
                    _row(
                        name + ".residual",
                        name + " median residual",
                        _number(law["residual_median"]),
                        unit=_unit(law["unit"]),
                        count=count,
                        outcome=outcome,
                        source=source,
                        locator=f"/law_checks/laws/{i}/residual_median",
                        measurement_version=report["measurement_version"],
                    )
                )
        rows.extend(
            _gap(name, name + " law result", "Required law not measured", source)
            for name in law_ids
            if name not in observed
        )
        return rows
    except (ValueError, KeyError, TypeError, AttributeError):
        return [
            _gap(
                "law_results",
                "Measured law checks / gate outcomes",
                "Public law-check output unavailable: invalid or incompatible contract/calibration",
                source,
            )
        ]


def _measurement(field, label, raw, source, locator):
    if raw is None:
        return _gap(field, label, "Measurement unavailable / not run", source)
    try:
        _closed(
            raw,
            {
                "value",
                "unit",
                "sample_count",
                "statistic",
                "measurement_version",
                "outcome",
            },
        )
        outcome = _outcome(raw["outcome"])
        count = _count(raw["sample_count"])
        if raw["value"] is None or count == 0:
            return _gap(
                field,
                label,
                "Measurement unavailable / not run",
                source,
                outcome if outcome != "PASS" else "NOT_ASSESSED",
            )
        value = _number(raw["value"])
        _token(raw["measurement_version"])
        statistic = _token(raw["statistic"])
        return _row(
            field,
            label + " (" + statistic + ")",
            value,
            unit=_unit(raw["unit"]),
            count=count,
            outcome=outcome,
            source=source,
            locator=locator,
            measurement_version=raw["measurement_version"],
        )
    except (ValueError, KeyError, TypeError):
        return _gap(
            field,
            label,
            "Measurement unavailable: malformed, unmeasured or nonfinite",
            source,
        )


def _card_rows(projection, source):
    card = None if projection is None else projection["model_card"]
    if card is not None and (
        type(card) is not dict or not set(card) <= set(CARD_FIELDS)
    ):
        card = None
    return [
        _measurement(
            name,
            label,
            None if card is None else card.get(name),
            source,
            "/model_card/" + name,
        )
        for name, label in CARD_FIELDS.items()
    ]


def _map_rows(projection, source, acceptance):
    absent = [
        _gap(
            "map",
            "Reference error / top-model disagreement",
            "Public carbon.trust_map aggregate unavailable",
            source,
        )
    ]
    if projection is None or projection["trust_map"] is None:
        return absent
    try:
        document = projection["trust_map"]
        _closed(
            document,
            {
                "schema",
                "maturity",
                "model",
                "spec",
                "top_models",
                "source",
                "reference_verification",
                "cells",
                "basis",
                "methods",
                "scored_case_selection",
            },
        )
        if (
            document["schema"] != "carbon.trust-map.v2"
            or document["maturity"] != "DEVELOPMENT"
            or document["scored_case_selection"] != "FORBIDDEN"
        ):
            raise ValueError("native development map required")
        _token(document["model"])
        if document["source"]["kind"] not in {"PUBLIC", "RELEASED"}:
            raise ValueError("undisclosed map")
        verification = document["reference_verification"]
        if (
            acceptance is None
            or verification != acceptance
            or _digest(verification["image_digest"])
            != projection["identity"]["reference_image_digest"]
        ):
            raise ValueError("reference verification mismatch")
        outputs = document["spec"]["outputs"]
        if type(outputs) is not dict or not outputs or len(outputs) > 32:
            raise ValueError("outputs required")
        units = {_token(name): _unit(desc["unit"]) for name, desc in outputs.items()}
        cells = document["cells"]
        if type(cells) is not list or not cells or len(cells) > 4096:
            raise ValueError("cells required")
        rows, coordinates = [], set()
        total = 0
        for i, cell in enumerate(cells):
            _closed(
                cell,
                {
                    "band",
                    "y",
                    "x",
                    "count",
                    "status",
                    "near_limit_count",
                    "error",
                    "disagreement",
                },
            )
            coordinate = tuple(_count(cell[key]) for key in ("band", "y", "x"))
            if coordinate in coordinates:
                raise ValueError("duplicate map cell")
            coordinates.add(coordinate)
            count = _count(cell["count"])
            total += count
            if _count(cell["near_limit_count"]) > count or cell["status"] != (
                "OBSERVED" if count else "NO_DATA"
            ):
                raise ValueError("cell coverage mismatch")
            for layer in ("error", "disagreement"):
                _closed(cell[layer], outputs)
                for output, unit in units.items():
                    _closed(cell[layer][output], {"median", "p90"})
                    for statistic in ("median", "p90"):
                        value = cell[layer][output][statistic]
                        field = f"cell.{i}.{layer}.{output}.{statistic}"
                        label = f"Cell {coordinate}: {output} {layer} {statistic}"
                        if count:
                            value = _number(value, nonnegative=True)
                            rows.append(
                                _row(
                                    field,
                                    label,
                                    value,
                                    unit=unit,
                                    count=count,
                                    source=source,
                                    locator=f"/trust_map/cells/{i}/{layer}/{output}/{statistic}",
                                )
                            )
                        elif value is None:
                            rows.append(
                                _gap(
                                    field,
                                    label,
                                    "NO_DATA: no observations in this cell",
                                    source,
                                )
                            )
                        else:
                            raise ValueError("empty cell cannot report an error")
        if _count(document["basis"]["cases"], positive=True) != total:
            raise ValueError("map basis mismatch")
        rows.extend(
            [
                _gap(
                    "law_layer",
                    "Law-violation layer",
                    "Not emitted by the current carbon.trust_map schema",
                    source,
                ),
                _gap(
                    "interval_layer",
                    "Uncertainty / calibration layers",
                    "Not emitted by the current carbon.trust_map schema",
                    source,
                ),
            ]
        )
        return rows
    except (ValueError, KeyError, TypeError):
        return [
            _gap(
                "map",
                "Reference error / top-model disagreement",
                "Public map unavailable: invalid, undisclosed or mismatched reference",
                source,
            )
        ]


def _mms_rows(source, acceptance_source, family, acceptance):
    if source is None:
        return [
            _gap("mms", "MMS measurements", "Public image-bound MMS result unavailable")
        ], None
    try:
        document = _json(source)
        schema = document["schema"]
        image = _digest(document.get("image_digest", document.get("image")))
        rows = [
            _row(
                "image_digest",
                "MMS reference image",
                image,
                source=source,
                locator="/image_digest" if "image_digest" in document else "/image",
                measured=False,
            )
        ]
        if schema == "carbon.code-verification.result.v1":
            if (
                document.get("kind") != "code_verification"
                or document.get("family") != family
            ):
                raise ValueError("code result required")
            _digest(document["source_digest"])
            _digest(document["criteria_digest"])
            norms = document["norms"]
            if type(norms) is not list or not norms:
                raise ValueError("measured norms required")
            for i, norm in enumerate(norms):
                samples = _count(norm["samples"], positive=True)
                for name in ("l2", "linf"):
                    rows.append(
                        _row(
                            f"norm.{i}.{name}",
                            f"MMS rung {i + 1} {name} error",
                            _number(norm[name], nonnegative=True),
                            unit="dimensionless manufactured-solution error",
                            count=samples,
                            source=source,
                            locator=f"/norms/{i}/{name}",
                        )
                    )
            for name, value in document["metrics"].items():
                if name in {"l2_order", "linf_order", "absolute_error"}:
                    rows.append(
                        _row(
                            name,
                            "MMS " + name,
                            _number(value),
                            unit=(
                                "dimensionless observed order"
                                if name in {"l2_order", "linf_order"}
                                else "dimensionless manufactured-solution error"
                            ),
                            source=source,
                            locator="/metrics/" + name,
                        )
                    )
            state = document["state"]
            if (
                state not in OUTCOMES | {"HUMAN_INPUT"}
                or type(document["accepted_development_pass"]) is not bool
            ):
                raise ValueError("machine verdict required")
            rows.append(
                _row(
                    "machine_verdict",
                    "Recorded MMS machine verdict",
                    state,
                    outcome="NOT_ASSESSED" if state == "HUMAN_INPUT" else state,
                    source=source,
                    locator="/state",
                    measured=False,
                )
            )
            rows.append(
                _row(
                    "machine_acceptance",
                    "Recorded machine acceptance flag",
                    document["accepted_development_pass"],
                    source=source,
                    locator="/accepted_development_pass",
                    measured=False,
                )
            )
        elif schema == "carbon.reference-package.mms.v1":
            if family != "f02":
                raise ValueError("native heat MMS belongs to f02")
            found = False
            for series in ("space_orders", "time_orders"):
                for i, rung in enumerate(document.get(series, [])):
                    found = True
                    for name in ("max", "rms"):
                        rows.append(
                            _row(
                                f"{series}.{i}.{name}",
                                f"MMS {series} pair {i + 1} {name}",
                                _number(rung[name]),
                                unit="dimensionless observed order",
                                source=source,
                                locator=f"/{series}/{i}/{name}",
                            )
                        )
            if not found:
                raise ValueError("observed orders required")
            rows.append(
                _gap(
                    "machine_acceptance",
                    "MMS machine acceptance",
                    "Raw native MMS observations do not issue a machine acceptance verdict",
                    source,
                )
            )
        else:
            raise ValueError("MMS result, not a plan/rebuild required")
        if acceptance is not None and image == acceptance["image_digest"]:
            rows.append(
                _row(
                    "owner_acceptance_link",
                    "Registered code-verification decision for this exact image (not use acceptance)",
                    (
                        "CONDITIONAL, t_end 0.375 (MMS test-design scope)"
                        if family == "f02"
                        else "RECORDED_OWNER_DECISION"
                    ),
                    source=acceptance_source,
                    measured=False,
                )
            )
            rows.append(
                _row(
                    "acceptance_conditions",
                    "Registered MMS verification conditions (test design, not application acceptance)",
                    acceptance["conditions"],
                    source=acceptance_source,
                    locator="/conditions",
                    measured=False,
                )
            )
        else:
            rows.append(
                _gap(
                    "owner_acceptance_link",
                    "Separate owner acceptance link",
                    "Matching owner acceptance record unavailable",
                )
            )
        rows.append(
            _gap(
                "physical_validation",
                "Physical validation",
                "MMS verifies code against equations; it is not physical validation",
            )
        )
        return rows, image
    except (ValueError, KeyError, TypeError, AttributeError):
        return [
            _gap(
                "mms",
                "MMS measurements",
                "Public MMS result unavailable: malformed, unmeasured or unsupported schema",
                source,
            )
        ], None


def _acceptance_from_sources(sources, family):
    """Only already allow-listed committed/exported bytes may establish a join."""
    try:
        link = _json(sources["P2"])
        result = _json(sources["P1"])
        image = result.get("image_digest", result.get("image"))
        criteria = _json(sources["P7"])
        criteria_digest = result.get("criteria_digest", digest(criteria))
        files = {
            source.path: source.text.encode("utf-8") for source in sources.values()
        }
        return validate_acceptance(
            link,
            family=family,
            image_digest=image,
            criteria_digest=criteria_digest,
            files=files,
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def _decision_rows(projection, source, family):
    rows = []
    verify = None if projection is None else projection["verify_r"]
    try:
        if (
            verify is None
            or verify["schema"] != "carbon.design-search.verify-aware-result.v1"
        ):
            raise ValueError("aggregate required")
        if "question_id" in verify or "questions" in verify:
            raise ValueError("aggregate only")
        _digest(verify["rule_digest"])
        count = _count(verify["offered"], positive=True)
        unscored = _count(verify["unscored"])
        if unscored > count or verify["status"] not in {"SCORED", "INCOMPLETE_LEGS"}:
            raise ValueError("VERIFY-R status mismatch")
        rows.append(
            _row(
                "verify_r.offered",
                "VERIFY-R offered questions",
                count,
                count=count,
                source=source,
                locator="/verify_r/offered",
                measured=False,
            )
        )
        rows.append(
            _row(
                "verify_r.rule_digest",
                "VERIFY-R registered rule digest",
                verify["rule_digest"],
                source=source,
                locator="/verify_r/rule_digest",
                measured=False,
            )
        )
        rows.append(
            _gap(
                "verify_r.k",
                "VERIFY-R registered top-k / verification budget",
                "Standalone aggregate omits k and budget; matched rule receipt required",
                source,
            )
        )
        rows.append(
            _gap(
                "verify_r.overhead",
                "VERIFY-R inference / verification wall-cost evidence",
                "Standalone aggregate omits timings; no measured end-to-end speed claim",
                source,
            )
        )
        if verify["status"] == "SCORED" and unscored == 0:
            regret = _number(verify["mean_service_regret"], nonnegative=True)
            if regret > 1:
                raise ValueError("bounded regret invalid")
            rows.append(
                _row(
                    "verify_r.regret",
                    "VERIFY-R mean bounded service regret",
                    regret,
                    unit="dimensionless bounded regret",
                    count=count,
                    source=source,
                    locator="/verify_r/mean_service_regret",
                )
            )
        else:
            rows.append(
                _gap(
                    "verify_r.regret",
                    "VERIFY-R mean bounded service regret",
                    "INCOMPLETE_LEGS: offered questions contain unscored evidence",
                    source,
                )
            )
    except (ValueError, KeyError, TypeError):
        rows.append(
            _gap(
                "verify_r",
                "Reference-verified top-k / VERIFY-R",
                "Public VERIFY-R aggregate unavailable or invalid",
                source,
            )
        )
    report = None if projection is None else projection["equal_budget"]
    try:
        if (
            report is None
            or report["schema"] != "carbon.design-search.equal-budget-report.v1"
            or report["challenge"] != family
        ):
            raise ValueError("matched equal-budget report required")
        if "jobs" in report or "questions" in report:
            raise ValueError("aggregate only")
        if report["status"] != "OK" or report["cost_basis"] != "MEASURED":
            raise ValueError("measured complete equal-budget evidence required")
        _digest(report["source_digest"])
        _digest(report["panel_digest"])
        count = _count(report["job_count"], positive=True)
        unit = _unit(report["objective"]["unit"])
        curves = report["curves"]
        if type(curves) is not list or not curves:
            raise ValueError("curves required")
        equal_rows = []
        for i, curve in enumerate(curves):
            budget = curve["budget"]
            _closed(budget, {"wall_s", "core_s"})
            for name in ("wall_s", "core_s"):
                value = _number(budget[name], nonnegative=True)
                if value == 0:
                    raise ValueError("positive budget required")
                equal_rows.append(
                    _row(
                        f"budget.{i}.{name}",
                        f"Budget {i + 1} {name}",
                        value,
                        unit="s",
                        source=source,
                        locator=f"/equal_budget/curves/{i}/budget/{name}",
                        measured=False,
                    )
                )
            estimates = curve["estimates"]
            for arm in ("solver_alone", "baseline_then_solver", "model_then_solver"):
                for metric in (
                    "mean_best_verified_value_conditional",
                    "mean_regret_conditional",
                    "feasible_pick_fraction",
                ):
                    value = estimates[arm][metric]
                    field = f"curve.{i}.{arm}.{metric}"
                    label = f"Budget {i + 1} {arm}: {metric}"
                    locator = f"/equal_budget/curves/{i}/estimates/{arm}/{metric}"
                    if value is None:
                        equal_rows.append(
                            _gap(
                                field,
                                label,
                                "No verified feasible value; conditional metric unavailable",
                                source,
                            )
                        )
                    else:
                        value = _number(value)
                        if metric == "mean_regret_conditional" and value < 0:
                            raise ValueError("negative regret")
                        if metric == "feasible_pick_fraction" and not 0 <= value <= 1:
                            raise ValueError("feasible fraction invalid")
                        equal_rows.append(
                            _row(
                                field,
                                label,
                                value,
                                unit=(
                                    "fraction"
                                    if metric == "feasible_pick_fraction"
                                    else unit
                                ),
                                count=count,
                                source=source,
                                locator=locator,
                            )
                        )
            delta = estimates["paired_verified_value_delta"]
            paired = _count(estimates["paired_verified_value_count"])
            if paired > count:
                raise ValueError("paired count invalid")
            if delta is None or paired != count:
                equal_rows.append(
                    _gap(
                        f"curve.{i}.paired_delta",
                        f"Budget {i + 1} paired verified-value delta",
                        "Incomplete paired jobs: no complete paired value estimate",
                        source,
                    )
                )
            else:
                equal_rows.append(
                    _row(
                        f"curve.{i}.paired_delta",
                        f"Budget {i + 1} model-minus-solver verified value",
                        _number(delta),
                        unit=unit,
                        count=paired,
                        source=source,
                        locator=f"/equal_budget/curves/{i}/estimates/paired_verified_value_delta",
                    )
                )
            intervals = curve.get("bootstrap_ci")
            if intervals is not None and type(intervals) is not dict:
                raise ValueError("interval index required")
            interval = (
                None
                if intervals is None
                else intervals.get("paired_verified_value_delta")
            )
            if interval is None or delta is None or paired != count:
                equal_rows.append(
                    _gap(
                        f"curve.{i}.paired_ci",
                        f"Budget {i + 1} paired cluster-bootstrap interval",
                        "Valid complete paired interval unavailable",
                        source,
                    )
                )
            else:
                if type(interval) is not list or len(interval) != 2:
                    raise ValueError("interval shape")
                lo, hi = [_number(value) for value in interval]
                confidence = _number(report["confidence"])
                if (
                    not lo <= delta <= hi
                    or not 0 < confidence < 1
                    or _count(report["independent_clusters"]) < 2
                ):
                    raise ValueError("interval basis mismatch")
                equal_rows.append(
                    _row(
                        f"curve.{i}.paired_ci",
                        f"Budget {i + 1} paired cluster-bootstrap interval",
                        interval,
                        unit=unit,
                        count=count,
                        source=source,
                        locator=f"/equal_budget/curves/{i}/bootstrap_ci/paired_verified_value_delta",
                    )
                )
                equal_rows.append(
                    _row(
                        f"curve.{i}.confidence",
                        f"Budget {i + 1} interval nominal level",
                        confidence,
                        unit="fraction",
                        source=source,
                        locator="/equal_budget/confidence",
                        measured=False,
                    )
                )
        rows.extend(equal_rows)
    except (ValueError, KeyError, TypeError):
        rows.append(
            _gap(
                "equal_budget",
                "Measured equal-budget curves",
                "Public equal-budget aggregate unavailable: missing, unresolved, assumed costs or identity mismatch",
                source,
            )
        )
    rows.append(
        _gap(
            "false_feasibility",
            "False feasibility of Assistant-selected picks",
            "Native aggregate does not measure Assistant selection pressure; PB-INV/ADV evidence required",
            source,
        )
    )
    return rows


def build_package_sections(challenge, family, sources):
    """Build five bounded evidence views without changing the D01–D11 schema."""
    projection_source = sources.get("P4")
    projection, projection_gap = None, None
    if projection_source is not None:
        try:
            projection = _projection(projection_source, challenge)
        except (ValueError, KeyError, TypeError, AttributeError):
            projection_gap = "P4: public package projection unavailable: malformed, nonfinite, undisclosed or mismatched identity"
    else:
        projection_gap = (
            "P4: public package projection not present at the evidence revision"
        )
    acceptance = _acceptance_from_sources(sources, family)
    mms_rows, image = _mms_rows(
        sources.get("P1"), sources.get("P2"), family, acceptance
    )
    if "P5" in sources:
        extra_rows, extra_image = _mms_rows(
            sources["P5"], sources.get("P2"), family, acceptance
        )
        if image is not None and image == extra_image:
            for row in extra_rows:
                row["field"] = "supplement." + row["field"]
            mms_rows.extend(extra_rows)
        else:
            mms_rows.append(
                _gap(
                    "supplement",
                    "Supplemental MMS",
                    "Supplemental image-bound MMS unavailable or mismatched",
                    sources["P5"],
                )
            )
    if projection is not None and (
        image is None
        or acceptance is None
        or projection["identity"]["reference_image_digest"] != image
    ):
        projection = None
        projection_gap = "P4: image-and-criteria-bound MMS acceptance unavailable; dependent joins refused"
    rows = {
        "law_checks": _law_rows(
            projection, projection_source, sources.get("P3"), family
        ),
        "model_card": _card_rows(projection, projection_source),
        "trust_map": _map_rows(projection, projection_source, acceptance),
        "solver_verification": mms_rows,
        "decision_evidence": _decision_rows(projection, projection_source, family),
    }
    if "P3" in sources:
        try:
            draft, law_ids = _draft(sources["P3"], family)
            rows["law_checks"].insert(
                0,
                _row(
                    "draft_law_count",
                    "Draft law definitions (not adopted/results)",
                    len(law_ids),
                    source=sources["P3"],
                    locator="/laws",
                    measured=False,
                ),
            )
            rows["law_checks"].insert(
                1,
                _row(
                    "validity_status",
                    "Draft validity declaration status",
                    _token(draft["validity"]["status"]),
                    source=sources["P3"],
                    locator="/validity/status",
                    measured=False,
                ),
            )
            outputs = draft["required_outputs"]
            if type(outputs) is not dict:
                raise ValueError("output definitions required")
            for name, definition in outputs.items():
                _token(name)
                availability = _token(definition["availability"])
                rows["law_checks"].append(
                    _row(
                        "output." + name,
                        name + " output availability (definition only)",
                        availability,
                        source=sources["P3"],
                        locator="/required_outputs/" + name + "/availability",
                        measured=False,
                    )
                )
        except (ValueError, KeyError, TypeError):
            rows["law_checks"].append(
                _gap(
                    "contract",
                    "Physics contract metadata",
                    "Draft unavailable or wrong family",
                    sources["P3"],
                )
            )
    sections = {}
    for name, (title, homes, basis) in GROUPS.items():
        values = rows[name]
        gaps = [
            row["field"] + ": " + row["reason"]
            for row in values
            if row["coverage"] == "GAP"
        ]
        if projection_gap is not None and name != "solver_verification":
            gaps.insert(0, projection_gap)
        if family == "battery-v3" and name != "solver_verification":
            gaps.append(
                "Current battery-plating-ref-v2 near-onset adequacy: REFERENCE_ADEQUACY_NOT_ESTABLISHED / GAP; required resolved mesh-160 evidence, version-bound current-use acceptance and complete refinement/failure/fallback costs are not established by these source-scoped rows"
            )
        sections[name] = {
            "title": title,
            "d_sections": homes,
            "basis": basis,
            "coverage": "PARTIAL" if any(row["measured"] for row in values) else "GAP",
            "rows": values,
            "gaps": gaps,
            "evidence_refs": sorted(
                {ref for row in values for ref in row["evidence_refs"]}
            ),
        }
    return {
        "schema": PACKAGE_SCHEMA,
        "mode": "DEVELOPMENT_SAMPLE",
        "challenge": challenge,
        "identity": None if projection is None else projection["identity"],
        "identity_basis": "DECLARED_IN_PUBLIC_PROJECTION_NOT_INDEPENDENTLY_ATTESTED",
        "qualification_claim": False,
        "sections": sections,
    }


def package_markdown(package):
    """Render only normalized rows, never entire producer objects."""
    lines = [
        "## Carbon Model Package evidence — DEVELOPMENT SAMPLE",
        "",
        "Coverage is not a verdict or qualification. Floors and acceptance remain HUMAN_INPUT.",
        "Identity/disclosure in a public projection is a producer assertion, not attestation.",
        "Host-declared use, domain and observable coverage are assertions; source identity is not verified applicability.",
        "Maps never replace solver verification of Assistant picks; law diagnostics do not adopt gates.",
        "",
    ]
    if package["challenge"].startswith("battery"):
        lines.extend(
            [
                "Battery plating reference transition: battery-plating-ref-v2 is not established by an image/MMS link. No usable near-onset label before required resolved mesh-160 evidence and current-use acceptance; REFERENCE_ADEQUACY_NOT_ESTABLISHED / GAP remains.",
                "Historical EV4/EV5/score-proof and card/map values retain their original reference meaning: annotate, never re-score. Current near-limit accuracy, calibration, feasible-pick or speed claims are not established by those rows; refinement/failure/fallback costs are required.",
                "Reference authority: [OWNER-PLATING-REFERENCE-01, 2026-10-13](https://github.com/carbonphysicsai/Carbon/blob/e9a28008b3975c3aaa93b710b6f623221241c2eb/.agent/decisions/2026-10-13-OWNER-PLATING-REFERENCE-01.md). This dated presentation note leaves the original source observations unchanged.",
                "",
            ]
        )
    for section in package["sections"].values():
        lines.extend(
            [
                f"### {section['title']}",
                "",
                f"Coverage: **{section['coverage']}**; basis: {section['basis']}; homes: {', '.join(section['d_sections'])}.",
                "",
                "| Field | Coverage | Recorded value / units | Source outcome | Evidence / reason |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in section["rows"]:
            value = (
                "GAP"
                if row["coverage"] == "GAP"
                else json.dumps(row["value"], ensure_ascii=False)
            )
            if row["unit"]:
                value += " " + row["unit"]
            if row["sample_count"] is not None:
                value += "; n=" + str(row["sample_count"])
            evidence = row["reason"] or row["citation"] or "HUMAN_INPUT"
            cells = [row["label"], row["coverage"], value, row["outcome"], evidence]
            lines.append(
                "| "
                + " | ".join(
                    str(cell).replace("|", "\\|").replace("\n", " ") for cell in cells
                )
                + " |"
            )
        lines.extend(["", "Gaps:", "", *["- " + gap for gap in section["gaps"]], ""])
    return lines
