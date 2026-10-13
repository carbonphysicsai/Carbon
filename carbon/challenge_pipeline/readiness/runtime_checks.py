"""R2/R4/R5: actual containment, frozen settings and bound grant arithmetic.

No remote fetch, spend, account ledger or supplied containment PASS is used.
Owner reviews are scoped to the exact grants and level, never inherited.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .model import FAIL, NOT_BUILT, PASS, REVIEW_REQUIRED, Result, digest, file_digest

REVIEW_SCHEMA = "carbon.readiness.runtime-review.v1"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
ANALYSIS_LANE = "miner-analysis-carrier"


class Invalid(ValueError):
    pass


def _object(pairs):
    value = {}
    for name, field in pairs:
        if name in value:
            raise Invalid("committed_evidence_repeats_a_field")
        value[name] = field
    return value


def _scope(ctx):
    levels = ctx.data.get("runtime_by_level", {})
    if type(levels) is not dict:
        raise Invalid("runtime_registration_malformed")
    record = levels.get(str(ctx.level))
    if record is None:
        return None
    if (
        type(record) is not dict
        or record.get("challenge") != ctx.challenge
        or type(record.get("level")) is not int
        or record["level"] != ctx.level
    ):
        raise Invalid("runtime_registration_scope_mismatch")
    return record


def _git(ctx, *args):
    done = subprocess.run(
        ["git", *args], cwd=ctx.repository, capture_output=True, check=False, timeout=30
    )
    if done.returncode:
        raise Invalid("committed_evidence_unavailable")
    return done.stdout


def _committed(ctx, relative, *, main=False):
    # Only repository-relative, non-symlink evidence can be committed evidence.
    if type(relative) is not str or not relative or "\\" in relative:
        raise Invalid("evidence_path_invalid")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or ":" in relative:
        raise Invalid("evidence_path_invalid")
    target = ctx.repository / path
    if target.is_symlink() or ctx.repository.resolve() not in target.resolve().parents:
        raise Invalid("evidence_path_invalid")
    try:
        current = target.read_bytes()
        committed = _git(ctx, "show", "HEAD:" + relative)
        if current != committed:
            raise Invalid("evidence_differs_from_HEAD")
        if main and _git(ctx, "show", "origin/main:" + relative) != committed:
            raise Invalid("grant_differs_from_main")
        value = json.loads(committed, object_pairs_hook=_object)
    except (OSError, ValueError) as error:
        if isinstance(error, Invalid):
            raise
        raise Invalid("committed_evidence_malformed") from error
    if type(value) is not dict:
        raise Invalid("committed_evidence_not_object")
    return value, file_digest(target)


def _grants(ctx, record):
    from carbon.agent_campaign.grant import SpendingGrant
    from carbon.agent_campaign.graphite import grant_binding, phase4

    roles = record.get("roles")
    if type(roles) is not dict or not roles:
        raise Invalid("NO_GRANT_FOR_LEVEL: no run roles")
    grants, evidence = {}, []
    for role, named in roles.items():
        if role not in ("constructor", "attacker") or type(named) is not dict:
            raise Invalid("runtime_role_invalid")
        entry = grant_binding.PHASE3_GRANTS.get(named.get("grant_id"))
        if (
            entry is None
            or entry.challenge != ctx.challenge
            or entry.runner != ("phase3" if role == "constructor" else "phase4")
            or named.get("grant_file") != entry.grant_file
            or not entry.main_blob
        ):
            raise Invalid("NO_GRANT_FOR_LEVEL: role binding mismatch")
        document, sha = _committed(ctx, entry.grant_file, main=True)
        grant = SpendingGrant.from_document(document)
        if grant.grant_id != entry.grant_id:
            raise Invalid("grant_identity_mismatch")
        if role == "constructor":
            refused = grant_binding.level_refusal(grant, ctx.level)
        else:
            bound = phase4.PHASE4_STAGE_GRANTS.get(grant.grant_id)
            if (
                bound is None
                or bound.challenge != ctx.challenge
                or bound.grant_file != entry.grant_file
            ):
                raise Invalid("NO_GRANT_FOR_LEVEL: attacker binding mismatch")
            refused = bound.levels is not None and ctx.level not in bound.levels
        if refused:
            raise Invalid("NO_GRANT_FOR_LEVEL: grant excludes this level")
        grants[role] = grant
        evidence.append(
            {
                "role": role,
                "grant_id": grant.grant_id,
                "file": entry.grant_file,
                "file_digest": sha,
                "grant_digest": digest(document),
            }
        )
    return grants, tuple(evidence)


def _review(ctx, record, item, grants, *, blocks=None):
    named = record.get("reviews", {})
    if type(named) is not dict:
        raise Invalid("runtime_reviews_malformed")
    relative = named.get(item)
    if relative is None:
        return Result(
            REVIEW_REQUIRED,
            f"owner: {'Test Engineer' if item == 'R4' else 'Test Lead'}; no committed {item} review for this level",
        )
    review, sha = _committed(ctx, relative)
    owner = "Test Engineer" if item == "R4" else "Test Lead"
    if (
        review.get("schema") != REVIEW_SCHEMA
        or review.get("item") != item
        or review.get("challenge") != ctx.challenge
        or type(review.get("level")) is not int
        or review["level"] != ctx.level
        or review.get("reviewer") != owner
        or review.get("decision") not in (PASS, FAIL)
        or type(review.get("basis")) is not str
        or not review["basis"].strip()
        or type(review.get("roles")) is not dict
        or set(review["roles"]) != set(grants)
    ):
        raise Invalid("runtime_review_identity_or_scope_mismatch")
    try:
        datetime.date.fromisoformat(review["date"])
    except (KeyError, TypeError, ValueError) as error:
        raise Invalid("runtime_review_date_invalid") from error
    for role, grant in grants.items():
        accepted = review["roles"][role]
        if type(accepted) is not dict or accepted.get("grant_digest") != digest(
            grant.document()
        ):
            raise Invalid("runtime_review_grant_digest_mismatch")
        if blocks is not None:
            block = blocks[role + "_model"]
            if (
                accepted.get("model") != block["model"]
                or type(accepted.get("max_output_tokens")) is not int
                or accepted["max_output_tokens"] != block["max_output_tokens"]
                or type(accepted.get("sizing_rule")) is not str
                or not accepted["sizing_rule"].strip()
                or accepted["sizing_rule"] == "HUMAN_INPUT"
            ):
                raise Invalid("output_sizing_review_mismatch")
    return Result(review["decision"], f"committed {owner} review of {item}", (sha,))


def containment(item, ctx):
    from carbon.development_session import containment_check as carrier
    from carbon.development_session.research_image import load_analysis_image

    from .checks import _analysis_image_manifest

    try:
        record = _scope(ctx)
        if record is None:
            return Result(
                NOT_BUILT,
                "owner: Test Lead; no containment lane recorded for this level",
            )
        lanes = record.get("containment_lanes")
        if type(lanes) is not list or len(set(lanes)) != len(lanes):
            raise Invalid("containment_lanes_malformed")
        if not lanes:
            return Result(
                NOT_BUILT,
                "owner: Test Lead; no check-capable containment lane declared",
            )
        if lanes != [ANALYSIS_LANE]:
            raise Invalid("containment_lane_has_no_no_spend_probe")
        manifest, refused = _analysis_image_manifest()
        if refused:
            return Result(FAIL, refused)
        before = file_digest(manifest)
        image = load_analysis_image(Path(manifest))
        with tempfile.TemporaryDirectory(prefix="readiness-containment-") as root:
            report = carrier.containment_check(root=Path(root), manifest=Path(manifest))
        if before != file_digest(manifest):
            raise Invalid("containment_manifest_changed_during_probe")
        if type(report) is not dict or report.get("schema") != carrier.SCHEMA:
            raise Invalid("containment_report_malformed")
        if report.get("synthetic_test_double") or report.get("synthetic"):
            raise Invalid("synthetic_containment_cannot_pass")
        evidence = (
            {
                "lane": ANALYSIS_LANE,
                "manifest_digest": before,
                "image_id": image.image_id,
                "producer_digest": file_digest(carrier.__file__),
            },
        )
        if report.get("status") != PASS:
            return Result(
                FAIL,
                "real containment probe failed: "
                + str(report.get("reason") or report.get("code")),
                evidence,
            )
        probes = report.get("probes")
        if (
            report.get("image_id") != image.image_id
            or type(probes) is not list
            or any(type(p) is not dict for p in probes)
            or [p.get("probe") for p in probes] != list(carrier.PROBES)
            or any(p.get("status") != PASS for p in probes)
            or not SHA.fullmatch(str(report.get("create_arguments_digest", "")))
            or type(report.get("isolation")) is not dict
            or not report["isolation"]
            or not report.get("operation")
            or type(report.get("canary")) is not dict
            or report["canary"].get("removed") is not True
            or report.get("claims") != {"security_acceptance": False}
        ):
            raise Invalid("containment_probes_or_launch_evidence_invalid")
        return Result(
            PASS,
            "real analysis carrier probe passed every containment check",
            evidence
            + (
                {
                    "probe_ids": list(carrier.PROBES),
                    "create_arguments_digest": report["create_arguments_digest"],
                },
            ),
        )
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))


def model_settings(item, ctx):
    from carbon.agent_campaign.graphite import (
        grant_binding,
        model_providers,
        readiness_models,
    )
    from carbon.agent_campaign.graphite.roles import RoleName

    try:
        record = _scope(ctx)
        if record is None:
            return Result(
                NOT_BUILT,
                "owner: Test Engineer; no per-role model registration for this level",
            )
        grants, evidence = _grants(ctx, record)
        evidence += (
            {
                "model_producer_digest": file_digest(readiness_models.__file__),
                "provider_registry_digest": file_digest(model_providers.__file__),
            },
        )
        commit = _git(ctx, "rev-parse", "HEAD").decode().strip()
        with tempfile.TemporaryDirectory(prefix="readiness-models-") as root:
            report = readiness_models.produce(
                Path(root),
                challenge=ctx.challenge,
                level=ctx.level,
                grants=grants,
                commit=commit,
            )
        if (
            type(report) is not dict
            or report.get("challenge") != ctx.challenge
            or type(report.get("level")) is not int
            or report["level"] != ctx.level
            or report.get("worker_ran") is not False
        ):
            raise Invalid("model_report_scope_or_execution_mismatch")
        problems, blocks = [], []
        for role, grant in grants.items():
            block = report.get(role + "_model")
            if block is None:
                # Keep checking other roles: an absent block never hides a contradiction.
                problems.append(
                    (
                        NOT_BUILT,
                        role + " has no frozen model block; owner: Test Engineer",
                    )
                )
                continue
            if type(block) is not dict:
                raise Invalid("model_block_malformed")
            chosen = model_providers.resolve(block.get("provider"))
            if chosen.name != grant_binding.model_provider_of(grant):
                raise Invalid("model_provider_does_not_match_grant")
            adapter = chosen.adapters.get(block.get("provider_id"))
            name = block.get("model")
            maximum = (
                None
                if adapter is None
                else adapter.output_maxima.get(name) or adapter.output_maximum
            )
            expected = chosen.context_tokens.get(name)
            if (
                expected is None
                or type(block.get("max_input_tokens")) is not int
                or block["max_input_tokens"] != expected
                or block.get("recorded_context_tokens") != expected
                or block.get("charge_reporting") is not True
                or adapter is None
                or not adapter.reported_charge
                or type(block.get("max_output_tokens")) is not int
                or block["max_output_tokens"] <= 0
                or maximum is None
                or block["max_output_tokens"] > maximum.tokens
                or block.get("recorded_output_maximum") != maximum.record()
                or not SHA.fullmatch(str(block.get("selection_digest", "")))
                or grant_binding.start_model_refusal(grant, RoleName(role), name)
            ):
                problems.append(
                    (
                        FAIL,
                        f"{role}: context/charge/output/model mismatch (input {block.get('max_input_tokens')}, recorded context {expected})",
                    )
                )
            blocks.append({"role": role, **block})
        evidence += tuple(blocks)
        for status in (FAIL, NOT_BUILT):
            details = [detail for found, detail in problems if found == status]
            if details:
                return Result(status, "; ".join(details), evidence)
        reviewed = _review(ctx, record, "R4", grants, blocks=report)
        return Result(reviewed.status, reviewed.detail, evidence + reviewed.evidence)
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))


def grants(item, ctx):
    from carbon.agent_campaign import grant_runs
    from carbon.agent_campaign.graphite import experiment, phase4
    from carbon.challenge_validator.scoring import scoring_for

    try:
        record = _scope(ctx)
        if record is None:
            return Result(
                NOT_BUILT,
                "owner: Test Lead; no per-role grants recorded for this level",
            )
        bound, evidence = _grants(ctx, record)
        evidence += (
            {
                "budget_producer_digest": file_digest(experiment.__file__),
                "attacker_budget_producer_digest": file_digest(phase4.__file__),
                "cap_enforcement_digest": file_digest(grant_runs.__file__),
            },
        )
        scoring = scoring_for(ctx.challenge)
        problems = []
        for role, grant in bound.items():
            budget = (
                experiment.phase3_budget(grant, scoring)
                if role == "constructor"
                else phase4.attacker_budget(grant, scoring)
            )
            if (
                grant.worst_case_run_cost * grant.permitted_runs
                + grant.cleanup_allowance
                > grant.monetary_ceiling
                or grant.worst_case_run_cost > grant_runs.PER_RUN_CAP_USD
                or grant.monetary_ceiling > grant_runs.WEEKLY_CAP_USD
                or (
                    not budget.tokens_only
                    and budget.max_pods * budget.pod_reservation_usd
                    > budget.pod_allowance_usd
                )
                or budget.pod_allowance_usd + budget.token_allowance_usd
                != grant.worst_case_run_cost
            ):
                problems.append(role + ": grant arithmetic or owner cap mismatch")
            if (
                role == "attacker" or budget.tokens_only
            ) and budget.pod_allowance_usd != 0:
                problems.append(role + ": no-pod run carries a pod allowance")
        if problems:
            return Result(FAIL, "; ".join(problems), evidence)
        reviewed = _review(ctx, record, "R5", bound)
        return Result(reviewed.status, reviewed.detail, evidence + reviewed.evidence)
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))
