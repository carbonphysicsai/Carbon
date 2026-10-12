"""Load PUBLIC reference pairs with byte-bound provenance for PLT-01.

This consumes existing solves; it never starts a solver or grants scientific
qualification. The panel is supplied by Data Collection. No member residual is
ever substituted for a reference residual.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from carbon.challenge_validator import physics_contract as pc

IMAGE = "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
VERIFICATION = "docs/development/evidence/battery-feasibility-02/code-verification/pybamm-verdict.json"
ACCEPTANCE = ".agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md"
OVERLAY = "scripts/dev/exam_design/locks/battery-overlay.lock.json"


class CalibrationRefused(ValueError):
    """The panel cannot establish calibrated reference readings."""


def _file(directory, name):
    path = (directory / name).resolve()
    if directory.resolve() not in path.parents:
        raise CalibrationRefused("calibration_path_escape")
    return path.read_bytes()


def public_plan(directory, contract):
    """Public probe inputs can be used before reference solves complete."""
    directory = Path(directory)
    body = _file(directory, "plan.json")
    plan = json.loads(body)
    if plan.get(
        "schema"
    ) != "carbon.battery.physics-calibration-plan.v1" or not plan.get(
        "scope", ""
    ).startswith(
        "PUBLIC_DEVELOPMENT"
    ):
        raise CalibrationRefused("calibration_plan_not_public")
    jobs_body = _file(directory, "jobs.json")
    if hashlib.sha256(jobs_body).hexdigest() != plan.get("jobs_sha256"):
        raise CalibrationRefused("calibration_jobs_hash")
    if plan["contract"]["probe_region"] != contract["probe_region"]:
        raise CalibrationRefused("calibration_plan_region")
    if "sha256" in plan["contract"]:
        source_body = _file(directory, "contract.v1.json")
        _hash(source_body, plan["contract"]["sha256"], "contract_hash")
        source = json.loads(source_body)
        if any(
            plan["contract"][k] != source[k]
            for k in ("challenge", "version", "probe_region")
        ):
            raise CalibrationRefused("calibration_contract_identity")
        if (
            source["challenge"] != contract["challenge"]
            or source["required_outputs"] != contract["required_outputs"]
        ):
            raise CalibrationRefused("calibration_contract_identity")
        current = {law["id"]: law for law in contract["laws"]}
        original = {law["id"]: law for law in source["laws"]}
        semantic_fields = (
            "type",
            "output",
            "outputs",
            "summary",
            "input",
            "direction",
            "step",
        )
        for pair in plan["pairs"]:
            for lid in pair["laws"]:
                if (
                    lid not in current
                    or lid not in original
                    or any(
                        current[lid].get(k) != original[lid].get(k)
                        for k in semantic_fields
                    )
                ):
                    raise CalibrationRefused("calibration_contract_law")
    jobs = json.loads(jobs_body)["jobs"]
    if type(jobs) is not list or len({j["case_id"] for j in jobs}) != len(jobs):
        raise CalibrationRefused("calibration_job_ids")
    if "jobs" in plan and plan["jobs"] != len(jobs):
        raise CalibrationRefused("calibration_job_count")
    return plan, jobs, hashlib.sha256(body).hexdigest()


def _hash(body, expected, reason):
    actual = hashlib.sha256(body).hexdigest()
    if expected not in (actual, "sha256:" + actual):
        raise CalibrationRefused("calibration_" + reason)
    return actual


def planned_pairs(plan, records, contract):
    """Reuse hash-bound c1/c2 pairs for rest causality at the declared step.

    The original plan predates RES-06. No pair input or reference is changed;
    the additional law IDs are an explicit prospective projection.
    """
    pairs = []
    for pair in plan["pairs"]:
        lids = list(pair["laws"])
        for law in contract["laws"]:
            if (
                law["type"] == "prefix_invariance"
                and pair["input"] in law["inputs"]
                and pair["step_fraction"] == law["step"]
            ):
                lids.append(law["id"])
        for lid in lids:
            pairs.append(
                {
                    "law_id": lid,
                    "along": pair["input"],
                    "base": records[pair["base"]],
                    "partner": records[pair["partner"]],
                }
            )
    return pairs


def load_directory(directory, contract, *, repository, include_records=False):
    try:
        return _load_directory(
            directory, contract, repository=repository, include_records=include_records
        )
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, CalibrationRefused):
            raise
        raise CalibrationRefused("calibration_panel_schema") from exc


def _load_directory(directory, contract, *, repository, include_records=False):
    """MANIFEST.json binds plan.json and one JSON reference file per record.

    `records` maps relative file names to SHA-256 strings (or {sha256: ...}).
    The plan's `pairs` name law_id, along, base_id and partner_id. Hashes are
    checked before record contents are used. The directory was explicitly
    designated PUBLIC by the owner; a contrary visibility marker is refused.
    """
    directory = Path(directory)
    manifest_body = _file(directory, "MANIFEST.json")
    manifest = json.loads(manifest_body)
    strict = manifest.get("schema") == "carbon.battery.physics-calibration-manifest.v1"
    if strict:
        if not manifest.get("scope", "").startswith("PUBLIC_DEVELOPMENT"):
            raise CalibrationRefused("calibration_not_public")
        plan, jobs, _ = public_plan(directory, contract)
        binding, solver = manifest["plan"], manifest["solver"]
        if manifest.get("missing") != [] or manifest.get("counts") != {"OK": len(jobs)}:
            raise CalibrationRefused("calibration_incomplete")
        if binding["jobs"] != len(jobs) or binding["pairs"] != len(plan["pairs"]):
            raise CalibrationRefused("calibration_plan_count")
        if binding["contract_sha256"] != plan["contract"]["sha256"]:
            raise CalibrationRefused("calibration_contract_hash")
        _hash(_file(directory, "jobs.json"), binding["jobs_sha256"], "jobs_hash")
        _hash(
            _file(directory, "records.jsonl"),
            manifest["records_file_sha256"],
            "records_file_hash",
        )
        _hash(
            _file(directory, "physcal_plan.py"),
            binding["generator_sha256"],
            "generator_hash",
        )
        _hash(
            _file(directory, "solve-command.json"),
            solver["solve_command_sha256"],
            "solve_command_hash",
        )
        verified = solver["overlay_verified"]
        if (
            solver["overlay_lock"] != OVERLAY
            or verified["base_image"] != solver["image"]
            or verified["lock_sha256"]
            != solver["overlay_lock_sha256"].removeprefix("sha256:")
            or verified["network"] != "none"
        ):
            raise CalibrationRefused("calibration_solver_binding")
        manifest = {
            **manifest,
            "image_digest": solver["image"],
            "overlay_lock_sha256": solver["overlay_lock_sha256"],
            "plan": "plan.json",
            "plan_sha256": binding["plan_sha256"],
        }
    image = manifest.get("image_digest", manifest.get("reference_image_digest", ""))
    if image.split("@")[-1] != IMAGE:
        raise CalibrationRefused("calibration_reference_image")
    if manifest.get("visibility", "PUBLIC") != "PUBLIC":
        raise CalibrationRefused("calibration_not_public")
    overlay_sha = hashlib.sha256((Path(repository) / OVERLAY).read_bytes()).hexdigest()
    if manifest.get("overlay_lock_sha256") not in (
        overlay_sha,
        "sha256:" + overlay_sha,
    ):
        raise CalibrationRefused("calibration_overlay_hash")
    plan_body = _file(directory, manifest.get("plan", "plan.json"))
    plan_sha = hashlib.sha256(plan_body).hexdigest()
    if manifest.get("plan_sha256") not in (plan_sha, "sha256:" + plan_sha):
        raise CalibrationRefused("calibration_plan_hash")
    verification = json.loads((Path(repository) / VERIFICATION).read_bytes())
    if (
        verification.get("image_digest") != IMAGE
        or not (Path(repository) / ACCEPTANCE).is_file()
    ):
        raise CalibrationRefused("calibration_reference_unverified")
    plan = json.loads(plan_body)
    hashes = manifest.get("record_sha256", manifest.get("records"))
    if type(plan.get("pairs")) is not list or type(hashes) is not dict:
        raise CalibrationRefused("calibration_panel_schema")
    records = {}
    if (directory / "records.jsonl").is_file():
        for line in _file(directory, "records.jsonl").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            cid = record.get("case_id")
            expected = hashes.get(cid)
            expected = expected.get("sha256") if type(expected) is dict else expected
            # Published per-record identity is exactly the JSONL line without LF.
            actual = hashlib.sha256(line).hexdigest()
            if type(expected) is not str or expected.removeprefix("sha256:") != actual:
                raise CalibrationRefused("calibration_record_hash")
            if type(cid) is not str or cid in records:
                raise CalibrationRefused("calibration_record_id")
            records[cid] = record
        if set(records) != set(hashes):
            raise CalibrationRefused("calibration_record_missing")
    else:
        for name, expected in hashes.items():
            record_body = _file(directory, name)
            expected = expected.get("sha256") if type(expected) is dict else expected
            actual = hashlib.sha256(record_body).hexdigest()
            if expected not in (actual, "sha256:" + actual):
                raise CalibrationRefused("calibration_record_hash")
            record = json.loads(record_body)
            cid = record.get("case_id")
            if type(cid) is not str or cid in records:
                raise CalibrationRefused("calibration_record_id")
            records[cid] = record
    if strict:
        if set(records) != {job["case_id"] for job in jobs}:
            raise CalibrationRefused("calibration_record_missing")
        for record in records.values():
            observed = record.get("solver_provenance", {})
            if (
                record.get("status") != "OK"
                or observed.get("schema") != "carbon.battery.solver-provenance.v1"
                or observed.get("solver_image") != solver["image"]
                or observed.get("overlay_lock") != OVERLAY
                or observed.get("overlay_lock_sha256") != solver["overlay_lock_sha256"]
                or observed.get("pybamm") != verified["versions"]["pybamm"]
            ):
                raise CalibrationRefused("calibration_record_provenance")
    if plan.get("scope", "").startswith("PUBLIC"):
        jobs_body = _file(directory, "jobs.json")
        if plan.get("jobs_sha256") != hashlib.sha256(jobs_body).hexdigest():
            raise CalibrationRefused("calibration_jobs_hash")
        jobs = json.loads(jobs_body)["jobs"]
        for job in jobs:
            if job["case_id"] not in records or records[job["case_id"]].get(
                "inputs"
            ) != {k: job[k] for k in contract["probe_region"]}:
                raise CalibrationRefused("calibration_record_inputs")
    pairs = []
    for pair in plan["pairs"]:
        try:
            if "laws" in pair:
                for lid in pair["laws"]:
                    pairs.append(
                        {
                            "law_id": lid,
                            "along": pair["input"],
                            "base": records[pair["base"]],
                            "partner": records[pair["partner"]],
                        }
                    )
            else:
                pairs.append(
                    {
                        **pair,
                        "base": records[pair["base_id"]],
                        "partner": records[pair["partner_id"]],
                    }
                )
        except KeyError as exc:
            raise CalibrationRefused("calibration_record_missing") from exc
    if strict:
        pairs = planned_pairs(plan, records, contract)
        identities = {
            (p["law_id"], p["base"]["case_id"], p["partner"]["case_id"]) for p in pairs
        }
        if len(identities) != len(pairs):
            raise CalibrationRefused("calibration_duplicate_pair")
        for law in contract["laws"]:
            if law["type"] not in pc.PAIR:
                continue
            axes = (
                list(contract["probe_region"])
                if law["type"] == "smoothness"
                else (
                    law["inputs"]
                    if law["type"] == "prefix_invariance"
                    else [law["input"]]
                )
            )
            for axis in axes:
                if (
                    sum(p["law_id"] == law["id"] and p["along"] == axis for p in pairs)
                    != plan["bases"]
                ):
                    raise CalibrationRefused("calibration_pair_coverage")
    provenance = {
        "image_digest": IMAGE,
        "overlay_lock_sha256": overlay_sha,
        "plan_sha256": plan_sha,
        "manifest_sha256": hashlib.sha256(manifest_body).hexdigest(),
        "records": len(records),
        "pairs": len(pairs),
        "acceptance": ACCEPTANCE,
        "contract_digest": pc.digest(contract),
    }
    if strict:
        from carbon.trust_map.acceptance import AcceptanceRefused, load_acceptance

        try:
            acceptance = load_acceptance(
                "battery-v3",
                IMAGE,
                verification["criteria_digest"],
                root=Path(repository),
            )
        except AcceptanceRefused as exc:
            raise CalibrationRefused("calibration_reference_unverified") from exc
        provenance.update(
            {
                "jobs_sha256": binding["jobs_sha256"],
                "records_file_sha256": manifest["records_file_sha256"],
                "source_contract_sha256": binding["contract_sha256"],
                "source_contract": binding["contract_source"],
                "physical_pairs": len(plan["pairs"]),
                "derived_prefix_laws": [
                    law["id"]
                    for law in contract["laws"]
                    if law["type"] == "prefix_invariance"
                ],
                "acceptance_link": acceptance,
            }
        )
    result = readings({"pairs": pairs}, contract), provenance
    return (*result, records) if include_records else result


def readings(panel, contract):
    laws = {law["id"]: law for law in contract["laws"] if law["type"] in pc.PAIR}
    readings = {lid: {"residuals": [], "unresolved": 0} for lid in laws}
    for pair in panel["pairs"]:
        lid = pair.get("law_id")
        if lid not in laws:
            raise CalibrationRefused("calibration_law")
        row, law = readings[lid], laws[lid]
        base, partner = pair.get("base", {}), pair.get("partner", {})
        if base.get("status") != "OK" or partner.get("status") != "OK":
            row["unresolved"] += 1
            continue
        a, b, along = (
            base.get("inputs", {}),
            partner.get("inputs", {}),
            pair.get("along"),
        )
        region = contract["probe_region"]
        if along not in region or (
            law["type"] == "prefix_invariance"
            and along not in law["inputs"]
            or law["type"] not in ("smoothness", "prefix_invariance")
            and along != law["input"]
        ):
            raise CalibrationRefused("calibration_pair_axis")
        if (
            set(a) != set(region)
            or set(b) != set(region)
            or any(a[k] != b[k] for k in region if k != along)
        ):
            raise CalibrationRefused("calibration_pair_geometry")
        if not pc.applicable(contract, a, base.get("outputs")) or not pc.applicable(
            contract, b, partner.get("outputs")
        ):
            row["unresolved"] += 1
            continue
        step = b[along] - a[along]
        expected_step = law["step"] * (region[along][1] - region[along][0])
        if not math.isclose(step, expected_step, rel_tol=1e-9, abs_tol=1e-12):
            raise CalibrationRefused("calibration_pair_step")
        if not all(
            pc._outputs_valid(contract, r.get("outputs")) for r in (base, partner)
        ):
            row["unresolved"] += 1
            continue
        residual = pc.pair_residual(
            law, base["outputs"], partner["outputs"], along, step
        )
        if residual is None:
            row["unresolved"] += 1
        else:
            row["residuals"].append(residual)
    return readings
