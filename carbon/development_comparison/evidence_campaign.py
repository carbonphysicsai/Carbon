"""Bounded DEVELOPMENT evidence campaign over trusted producer stage modules.

The CLI cannot grant scientific readiness or paid execution. A synthetic dry
run exercises the same graph without calling a Challenge solver. Real stage
adapters must be repository code with pinned bytes and an operator grant.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path

from carbon.design_search import adaptive_arms, budget_registration, equal_budget
from carbon.development_comparison import (
    campaign_entrypoints,
    evidence_pipeline,
    value_bar,
)

SCHEMA = "carbon.development-evidence-campaign.v1"
READINESS = "carbon.onboarding.evidence-readiness.v1"  # #1039, 98a236bf6
APPROVAL = SCHEMA + ".approval"
STAGE_RESULT = SCHEMA + ".stage-result"
PILOT = SCHEMA + ".cost-pilot.v1"
STATE = SCHEMA + ".state"
FAMILIES = ("battery-v3", "motor", "f02")
READINESS_LABELS = (
    "Registered, deduplicated, reuse-checked panel on main",
    "Pinned package and current operator-store image observation",
    "Convergence, conservation AND code verification for current image/family",
    "Kit covers every panel action, condition and observable",
    "Registered TRAIN physically disjoint from panel",
    "Strong cheap-baseline implementation ready",
    "Challenge-supported equal-budget implementation ready",
)
PHASES = ("reference", "train", "assemble", "score")
ARTIFACT_ROLES = {
    "PUBLIC_TRAIN",
    "PUBLIC_INPUT",
    "HELDOUT_REFERENCE",
    "MODEL",
    "ANALYSIS",
    "SYNTHETIC_FIXTURE",
}
ROOT = Path(__file__).resolve().parents[2]
MAX_INPUT_BYTES = 32 * 1024 * 1024


class CampaignRefused(ValueError):
    def __init__(self, stage: str, code: str, *, observed_wall_s=None):
        self.stage, self.code = stage, code
        self.observed_wall_s = observed_wall_s
        super().__init__(f"{stage}: {code}")


def _closed(value, fields, stage):
    if type(value) is not dict or set(value) != set(fields):
        raise CampaignRefused(stage, "CLOSED_SCHEMA_REQUIRED")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _digest(body):
    return _sha(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def seal(body, field):
    if type(body) is not dict or field in body:
        raise CampaignRefused("seal", "UNSEALED_BODY_REQUIRED")
    return {**body, field: _digest(body)}


def _number(value, stage, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise CampaignRefused(stage, "FINITE_NUMBER_REQUIRED")
    if value < 0 or (positive and value == 0):
        raise CampaignRefused(stage, "POSITIVE_NUMBER_REQUIRED")
    return float(value)


def _host(plan):
    """A registered host quote, not a measured throughput or spend approval."""
    host = plan["host"]
    _closed(
        host,
        {
            "host_id",
            "vcpus",
            "ram_gb",
            "usd_per_hour",
            "usd_to_eur",
            "fixed_eur",
            "basis",
            "source",
        },
        "host",
    )
    if not isinstance(host["host_id"], str) or not host["host_id"]:
        raise CampaignRefused("host", "HOST_ID_REQUIRED")
    if type(host["vcpus"]) is not int or host["vcpus"] <= 0:
        raise CampaignRefused("host", "POSITIVE_VCPUS_REQUIRED")
    _number(host["ram_gb"], "host RAM", positive=True)
    _number(host["usd_per_hour"], "host hourly USD")
    _number(host["usd_to_eur"], "host USD-to-EUR", positive=True)
    _number(host["fixed_eur"], "host fixed charges")
    if (
        host["basis"] not in ("ASSUMPTION", "SOURCED", "MEASURED_PILOT")
        or not host["source"]
    ):
        raise CampaignRefused("host", "HOST_PROVENANCE_REQUIRED")
    return host


def _hourly_eur(host):
    return host["usd_per_hour"] * host["usd_to_eur"]


def _pilot(path, pin, family, scope):
    """Accept a capped, digest-bound development pilot measurement only."""
    row = _read(path, pin)
    _closed(
        row,
        {
            "schema",
            "scope",
            "family",
            "host_id",
            "cap_eur",
            "observed_eur",
            "stage_samples",
            "pilot_digest",
        },
        "pilot",
    )
    if (
        row["schema"] != PILOT
        or row["scope"] != scope
        or row["family"] != family
        or not isinstance(row["host_id"], str)
        or not row["host_id"]
        or row["pilot_digest"]
        != _digest({k: v for k, v in row.items() if k != "pilot_digest"})
    ):
        raise CampaignRefused("pilot", "PILOT_IDENTITY_MISMATCH")
    cap = _number(row["cap_eur"], "pilot cap", positive=True)
    observed = _number(row["observed_eur"], "pilot observed")
    if cap > 10 or observed > cap:
        raise CampaignRefused("pilot", "TEN_EURO_PILOT_CAP_EXCEEDED")
    samples = row["stage_samples"]
    if type(samples) is not list or not samples:
        raise CampaignRefused("pilot", "STAGE_SAMPLES_REQUIRED")
    for sample in samples:
        _closed(sample, {"phase", "attempts", "wall_s", "core_s"}, "pilot sample")
        if (
            sample["phase"] not in PHASES
            or type(sample["attempts"]) is not int
            or sample["attempts"] < 1
        ):
            raise CampaignRefused("pilot", "STAGE_SAMPLE_INVALID")
        _number(sample["wall_s"], "pilot sample", positive=True)
        _number(sample["core_s"], "pilot sample", positive=True)
    return row


def _safe_relative(value, stage):
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or Path(value).is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
        or ":" in value
    ):
        raise CampaignRefused(stage, "LOCAL_RELATIVE_PATH_REQUIRED")
    return value


def _read(path, expected=None):
    if str(path).startswith(("\\\\", "//")) or path.is_symlink() or not path.is_file():
        raise CampaignRefused("load", "REGULAR_LOCAL_FILE_REQUIRED")
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise CampaignRefused("load", "RESOURCE_LIMIT")
    if expected is not None and _sha(raw) != expected:
        raise CampaignRefused("load", "BYTE_PIN_MISMATCH")
    try:
        return evidence_pipeline._json(raw)
    except (ValueError, UnicodeError) as exc:
        raise CampaignRefused("load", "INVALID_JSON") from exc


def _descriptor(base, row, stage):
    _closed(row, {"path", "sha256"}, stage)
    relative = _safe_relative(row["path"], stage)
    value = row["sha256"]
    value_bar._sha(value, stage)
    target = base / relative
    if not target.resolve().is_relative_to(base.resolve()) or any(
        part.is_symlink()
        for part in (target, *target.parents)
        if part.is_relative_to(base)
    ):
        raise CampaignRefused(stage, "PATH_ESCAPE")
    _read(target, value)
    return target


def _readiness(path, pin, family, *, require_yes):
    row = _read(path, pin)
    _closed(
        row,
        {
            "schema",
            "challenge",
            "main",
            "observed_at",
            "items",
            "yes_count",
            "all_prerequisites_yes",
            "spend_authorized",
            "qualified",
            "paid_run_output_exception",
            "examined_sources",
        },
        "readiness",
    )
    if (
        row["schema"] != READINESS
        or row["challenge"] != family
        or row["spend_authorized"] is not False
        or row["qualified"] is not False
        or type(row["main"]) is not str
        or len(row["main"]) != 40
        or any(char not in "0123456789abcdef" for char in row["main"])
        or type(row["examined_sources"]) is not dict
    ):
        raise CampaignRefused("readiness", "IDENTITY_MISMATCH")
    try:
        observed = datetime.fromisoformat(row["observed_at"])
    except (TypeError, ValueError) as exc:
        raise CampaignRefused("readiness", "OBSERVATION_TIME_REQUIRED") from exc
    if observed.tzinfo is None:
        raise CampaignRefused("readiness", "AWARE_OBSERVATION_TIME_REQUIRED")
    items = row["items"]
    if type(items) is not list or len(items) != 7:
        raise CampaignRefused("readiness", "EXACTLY_SEVEN_ITEMS_REQUIRED")
    for index, item in enumerate(items):
        _closed(
            item, {"item", "label", "state", "basis", "owner", "pointers"}, "readiness"
        )
        if item["item"] != index + 1 or item["label"] != READINESS_LABELS[index]:
            raise CampaignRefused("readiness", "ITEM_ID_INVALID")
        if (
            not isinstance(item["basis"], str)
            or not isinstance(item["owner"], str)
            or type(item["pointers"]) is not list
        ):
            raise CampaignRefused("readiness", "ITEM_BASIS_REQUIRED")
        if item["state"] not in ("YES", "NO", "PLANNED", "UNKNOWN"):
            raise CampaignRefused("readiness", "ITEM_STATUS_INVALID")
        if require_yes and item["state"] != "YES":
            raise CampaignRefused("readiness", "ITEM_NOT_YES:" + str(index + 1))
    count = sum(item["state"] == "YES" for item in items)
    if row["yes_count"] != count or row["all_prerequisites_yes"] is not (count == 7):
        raise CampaignRefused("readiness", "SUMMARY_MISMATCH")
    return row


def _fresh_readiness(plan, plan_dir):
    """Re-evaluate #1039 on the exact merged main immediately before dispatch."""
    if plan["scope"] == "SYNTHETIC_FIXTURE":
        return
    try:
        from carbon.challenge_pipeline.onboarding import evidence_readiness
    except ImportError as exc:
        raise CampaignRefused("readiness", "PR_1039_NOT_ON_MAIN") from exc
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        main = subprocess.check_output(
            ["git", "rev-parse", "origin/main"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CampaignRefused("readiness", "EXACT_MAIN_UNAVAILABLE") from exc
    if head != main:
        raise CampaignRefused("readiness", "EXACT_MAIN_REQUIRED")
    for family in FAMILIES:
        descriptor = plan["readiness"][family]
        recorded = _readiness(
            _descriptor(plan_dir, descriptor, "readiness"),
            descriptor["sha256"],
            family,
            require_yes=True,
        )
        if recorded["main"] != main:
            raise CampaignRefused("readiness", "STALE_MAIN_OBSERVATION")
        try:
            fresh = evidence_readiness.generate(ROOT, family, main_ref="origin/main")
        except (ValueError, KeyError, OSError) as exc:
            raise CampaignRefused("readiness", "FRESH_CHECK_UNAVAILABLE") from exc
        if (
            fresh["main"] != main
            or fresh["yes_count"] != 7
            or not fresh["all_prerequisites_yes"]
            or fresh["examined_sources"] != recorded["examined_sources"]
        ):
            raise CampaignRefused("readiness", "FRESH_SEVEN_YES_REQUIRED")
        for old, new in zip(recorded["items"], fresh["items"], strict=True):
            if old["state"] != new["state"] or old["label"] != new["label"]:
                raise CampaignRefused("readiness", "FRESH_STATUS_CHANGED")


def _module(task, scope):
    name = task["module"]
    fixture = name == "carbon.development_comparison.campaign_fixture"
    if not isinstance(name, str) or not (
        fixture
        if scope == "SYNTHETIC_FIXTURE"
        else name.startswith("carbon.development_comparison.campaign_adapters.")
    ):
        raise CampaignRefused("stage", "TRUSTED_MODULE_REQUIRED")
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError):
        spec = None
    if spec is None or spec.origin is None:
        raise CampaignRefused("stage", "REGISTERED_MODULE_UNAVAILABLE")
    source = Path(spec.origin).resolve()
    if not source.is_relative_to(ROOT) or source.is_symlink():
        raise CampaignRefused("stage", "MODULE_PATH_REFUSED")
    if _sha(source.read_bytes()) != task["module_sha256"]:
        raise CampaignRefused("stage", "MODULE_BYTE_PIN_MISMATCH")
    return name


def validate(plan, plan_dir, *, require_ready=True, require_modules=True):
    _closed(
        plan,
        {
            "schema",
            "scope",
            "campaign_id",
            "readiness",
            "budget_registration",
            "value_rule",
            "entrypoint_registration_digest",
            "cost_pilots",
            "stages",
            "host",
            "hard_cap_eur",
            "hard_wall_s",
            "analysis",
            "analysis_reserve",
            "plan_digest",
        },
        "plan",
    )
    if plan["schema"] != SCHEMA or plan["scope"] not in (
        "PUBLIC_DEVELOPMENT",
        "SYNTHETIC_FIXTURE",
    ):
        raise CampaignRefused("plan", "DEVELOPMENT_SCOPE_REQUIRED")
    if not isinstance(plan["campaign_id"], str) or not plan["campaign_id"]:
        raise CampaignRefused("plan", "CAMPAIGN_ID_REQUIRED")
    if plan["entrypoint_registration_digest"] != campaign_entrypoints.digest():
        raise CampaignRefused("entrypoint", "REGISTRATION_DIGEST_MISMATCH")
    if plan["plan_digest"] != _digest(
        {k: v for k, v in plan.items() if k != "plan_digest"}
    ):
        raise CampaignRefused("plan", "PLAN_DIGEST_MISMATCH")
    _closed(plan["cost_pilots"], FAMILIES, "cost pilots")
    for family in FAMILIES:
        descriptor = plan["cost_pilots"][family]
        _pilot(
            _descriptor(plan_dir, descriptor, "cost pilot"),
            descriptor["sha256"],
            family,
            plan["scope"],
        )
    _closed(plan["readiness"], FAMILIES, "readiness")
    for family in FAMILIES:
        descriptor = plan["readiness"][family]
        _readiness(
            _descriptor(plan_dir, descriptor, "readiness"),
            descriptor["sha256"],
            family,
            require_yes=require_ready,
        )
    registration = _read(_descriptor(plan_dir, plan["budget_registration"], "budget"))
    budget_registration.validate(registration)
    rule = _read(_descriptor(plan_dir, plan["value_rule"], "rule"))
    value_bar._owner_rule(rule)
    if rule["rule_id"] != "VALUE-BAR-V1":
        raise CampaignRefused("rule", "VALUE_BAR_V1_REQUIRED")
    host = _host(plan)
    _number(plan["hard_wall_s"], "hard wall", positive=True)
    if _number(plan["hard_cap_eur"], "cap", positive=True) <= host["fixed_eur"]:
        raise CampaignRefused("cap", "FIXED_CHARGES_EXCEED_CAP")
    _closed(
        plan["analysis"], {"bootstrap_replicates", "confidence", "seed"}, "analysis"
    )
    analysis = plan["analysis"]
    if (
        type(analysis["bootstrap_replicates"]) is not int
        or analysis["bootstrap_replicates"] < 100
        or analysis["bootstrap_replicates"] > 10000
        or analysis["confidence"] != 0.95
        or type(analysis["seed"]) is not int
    ):
        raise CampaignRefused("analysis", "REGISTERED_ANALYSIS_REQUIRED")
    _closed(plan["analysis_reserve"], FAMILIES, "analysis reserve")
    for family in FAMILIES:
        reserve = plan["analysis_reserve"][family]
        _closed(reserve, {"wall_s", "core_s", "peak_ram_gb"}, "analysis reserve")
        wall = _number(reserve["wall_s"], "analysis reserve", positive=True)
        core = _number(reserve["core_s"], "analysis reserve", positive=True)
        if (
            _number(reserve["peak_ram_gb"], "analysis RAM", positive=True)
            > host["ram_gb"]
        ):
            raise CampaignRefused("analysis reserve", "HOST_RAM_EXCEEDED")
        if core > wall:
            raise CampaignRefused(
                "analysis reserve", "ONE_CORE_ANALYSIS_RESERVE_REQUIRED"
            )
    tasks, seen = [], set()
    if plan["scope"] == "PUBLIC_DEVELOPMENT" and require_modules:
        inspection = campaign_entrypoints.inspect(ROOT)
        if any(
            state != "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
            for states in inspection.values()
            for state in states.values()
        ):
            raise CampaignRefused("entrypoint", "PRODUCER_REGISTRATION_INCOMPLETE")
    if type(plan["stages"]) is not list or not plan["stages"]:
        raise CampaignRefused("stage", "STAGES_REQUIRED")
    for task in plan["stages"]:
        _closed(
            task,
            {
                "family",
                "phase",
                "shard",
                "shards",
                "module",
                "module_sha256",
                "vcpus",
                "planned_wall_s",
                "planned_core_s",
                "peak_ram_gb",
                "inputs",
            },
            "stage",
        )
        family, phase, shard, shards = (
            task[k] for k in ("family", "phase", "shard", "shards")
        )
        if (
            family not in FAMILIES
            or phase not in PHASES
            or type(shard) is not int
            or type(shards) is not int
            or shards < 1
            or not 0 <= shard < shards
        ):
            raise CampaignRefused("stage", "TASK_ID_INVALID")
        key = (family, phase, shard)
        if key in seen:
            raise CampaignRefused("stage", "DUPLICATE_TASK")
        seen.add(key)
        if type(task["vcpus"]) is not int or not 1 <= task["vcpus"] <= host["vcpus"]:
            raise CampaignRefused("stage", "VCPU_ALLOCATION_INVALID")
        if _number(task["peak_ram_gb"], "stage RAM", positive=True) > host["ram_gb"]:
            raise CampaignRefused("stage", "HOST_RAM_EXCEEDED")
        wall = _number(task["planned_wall_s"], "stage", positive=True)
        core = _number(task["planned_core_s"], "stage", positive=True)
        if core > wall * task["vcpus"] + 1e-9:
            raise CampaignRefused("stage", "CORE_EXCEEDS_ALLOCATION")
        if require_modules:
            _module(task, plan["scope"])
        elif not isinstance(task["module"], str) or not task["module"]:
            raise CampaignRefused("stage", "PLANNED_MODULE_NAME_REQUIRED")
        if type(task["inputs"]) is not dict:
            raise CampaignRefused("stage", "INPUTS_REQUIRED")
        for descriptor in task["inputs"].values():
            _closed(descriptor, {"path", "sha256", "role"}, "stage input")
            if descriptor["role"] not in ARTIFACT_ROLES:
                raise CampaignRefused("stage input", "INPUT_ROLE_INVALID")
            if (
                plan["scope"] == "PUBLIC_DEVELOPMENT"
                and descriptor["role"] == "SYNTHETIC_FIXTURE"
            ):
                raise CampaignRefused("stage input", "FIXTURE_ROLE_REFUSED")
            if phase == "train" and descriptor["role"] not in (
                "PUBLIC_TRAIN",
                "PUBLIC_INPUT",
                "SYNTHETIC_FIXTURE",
            ):
                raise CampaignRefused("stage input", "TRAIN_MAY_NOT_READ_HELDOUT")
            _descriptor(
                plan_dir,
                {k: descriptor[k] for k in ("path", "sha256")},
                "stage input",
            )
        tasks.append(task)
    for family in FAMILIES:
        for phase in ("reference", "train", "assemble"):
            group = [t for t in tasks if t["family"] == family and t["phase"] == phase]
            if (
                not group
                or {t["shard"] for t in group} != set(range(group[0]["shards"]))
                or any(t["shards"] != len(group) for t in group)
            ):
                raise CampaignRefused("stage", "COMPLETE_SHARD_SET_REQUIRED")
        if (
            len(
                [t for t in tasks if t["family"] == family and t["phase"] == "assemble"]
            )
            != 1
        ):
            raise CampaignRefused("stage", "ONE_ASSEMBLY_REQUIRED")
        if (
            len([t for t in tasks if t["family"] == family and t["phase"] == "score"])
            > 1
        ):
            raise CampaignRefused("stage", "ONE_SCORE_PLUGIN_AT_MOST")
    if plan["scope"] == "PUBLIC_DEVELOPMENT" and not any(
        t["phase"] == "score" for t in tasks
    ):
        # An absent score is valid: the future verify-aware score is optional.
        pass
    return registration, rule, tasks


def _phase_wall(tasks, host):
    """Deterministic list scheduling; planned values are assumptions, not timings."""
    running, waiting, now, used_cores, used_ram = [], list(tasks), 0.0, 0, 0.0
    while waiting or running:
        for task in list(waiting):
            if (
                used_cores + task["vcpus"] <= host["vcpus"]
                and used_ram + task["peak_ram_gb"] <= host["ram_gb"] + 1e-9
            ):
                running.append((now + task["planned_wall_s"], task))
                used_cores += task["vcpus"]
                used_ram += task["peak_ram_gb"]
                waiting.remove(task)
        if not running:
            raise CampaignRefused("sheet", "UNSCHEDULABLE_TASK")
        now = min(end for end, _ in running)
        for end, task in list(running):
            if end == now:
                running.remove((end, task))
                used_cores -= task["vcpus"]
                used_ram -= task["peak_ram_gb"]
    return now


def server_sheet(plan, tasks, plan_dir=None):
    host = _host(plan)
    groups = {
        family: [t for t in tasks if t["family"] == family] for family in FAMILIES
    }
    phase_wall = {
        phase: _phase_wall([t for t in tasks if t["phase"] == phase], host)
        for phase in PHASES
    }
    phase_wall["analysis"] = sum(
        plan["analysis_reserve"][family]["wall_s"] for family in FAMILIES
    )
    total_wall_s = sum(phase_wall.values())
    total_core_s = sum(t["planned_core_s"] for t in tasks) + sum(
        plan["analysis_reserve"][family]["core_s"] for family in FAMILIES
    )
    node_usd = total_wall_s / 3600 * host["usd_per_hour"]
    node_eur = node_usd * host["usd_to_eur"]
    total_eur = node_eur + host["fixed_eur"]
    rows = {}
    for family, group in groups.items():
        core_s = (
            sum(t["planned_core_s"] for t in group)
            + plan["analysis_reserve"][family]["core_s"]
        )
        wall_s = plan["analysis_reserve"][family]["wall_s"] + sum(
            _phase_wall([t for t in group if t["phase"] == phase], host)
            for phase in PHASES
        )
        rows[family] = {
            "planned_cpu_hours": core_s / 3600,
            "isolated_wall_hours": wall_s / 3600,
            "allocated_eur_estimate": total_eur * core_s / total_core_s,
            "allocation_basis": "proportional planned CPU hours; shared node wall is priced only once",
            "pilot": (
                _pilot(
                    _descriptor(plan_dir, plan["cost_pilots"][family], "cost pilot"),
                    plan["cost_pilots"][family]["sha256"],
                    family,
                    plan["scope"],
                )
                if plan_dir is not None
                else {"receipt_sha256": plan["cost_pilots"][family]["sha256"]}
            ),
        }
    return {
        "schema": SCHEMA + ".server-sheet",
        "scope": plan["scope"],
        "basis": "stage estimates remain ASSUMPTION extrapolations; capped pilot samples are shown per Challenge",
        "plan_digest": plan["plan_digest"],
        "entrypoint_registration_digest": plan["entrypoint_registration_digest"],
        "host": host,
        "by_challenge": rows,
        "total": {
            "planned_cpu_hours": total_core_s / 3600,
            "planned_wall_hours": total_wall_s / 3600,
            "node_usd_estimate": node_usd,
            "node_eur_estimate": node_eur,
            "fixed_eur": host["fixed_eur"],
            "eur_estimate": total_eur,
            "hard_cap_eur_for_approval": plan["hard_cap_eur"],
            "headroom_eur": plan["hard_cap_eur"] - total_eur,
        },
        "phase_wall_hours": {k: v / 3600 for k, v in phase_wall.items()},
        "limits": [
            "registered vCPUs and RAM are allocation limits, not measured throughput",
            "actual billed wall and fixed charges need a host quote and operator check",
            "USD-to-EUR conversion is a registered planning input, not a live exchange rate",
            "this sheet does not authorize spend or scientific qualification",
        ],
    }


def _state(path, plan):
    if not path.exists():
        return {
            "schema": STATE,
            "plan_digest": plan["plan_digest"],
            "billed_wall_s": 0.0,
            "last_active_epoch_s": None,
            "completed": {},
            "attempts": [],
            "analysis_costs": {},
            "state_digest": None,
        }
    state = _read(path)
    _closed(
        state,
        {
            "schema",
            "plan_digest",
            "billed_wall_s",
            "last_active_epoch_s",
            "completed",
            "attempts",
            "analysis_costs",
            "state_digest",
        },
        "resume",
    )
    if (
        state["schema"] != STATE
        or state["plan_digest"] != plan["plan_digest"]
        or state["state_digest"]
        != _digest({k: v for k, v in state.items() if k != "state_digest"})
    ):
        raise CampaignRefused("resume", "PLAN_IDENTITY_MISMATCH")
    _number(state["billed_wall_s"], "resume")
    if state["last_active_epoch_s"] is not None:
        _number(state["last_active_epoch_s"], "resume", positive=True)
    if (
        type(state["completed"]) is not dict
        or type(state["attempts"]) is not list
        or type(state["analysis_costs"]) is not dict
    ):
        raise CampaignRefused("resume", "STATE_INVALID")
    return state


def _save(path, state):
    state["state_digest"] = _digest(
        {k: v for k, v in state.items() if k != "state_digest"}
    )
    temporary = path.with_name(path.name + f".{os.getpid()}.{time.time_ns()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(state, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _key(task):
    return f"{task['family']}/{task['phase']}/{task['shard']}"


def _prior_artifacts(output, receipt):
    return {
        name: {
            "path": str(output / descriptor["path"]),
            "sha256": descriptor["sha256"],
            "role": descriptor["role"],
        }
        for name, descriptor in receipt["artifacts"].items()
    }


def _verified_receipt(task, output, plan):
    receipt_path = output / "receipt.json"
    receipt = _read(receipt_path)
    _closed(
        receipt,
        {
            "schema",
            "plan_digest",
            "family",
            "phase",
            "shard",
            "status",
            "core_s",
            "peak_ram_bytes",
            "artifacts",
        },
        "stage receipt",
    )
    if (
        receipt["schema"] != STAGE_RESULT
        or receipt["plan_digest"] != plan["plan_digest"]
        or any(receipt[key] != task[key] for key in ("family", "phase", "shard"))
        or receipt["status"] != "OK"
    ):
        raise CampaignRefused("stage receipt", "IDENTITY_OR_STATUS_MISMATCH")
    _number(receipt["core_s"], "stage receipt")
    if type(receipt["peak_ram_bytes"]) is not int or receipt["peak_ram_bytes"] < 0:
        raise CampaignRefused("stage receipt", "RAM_EVIDENCE_REQUIRED")
    if type(receipt["artifacts"]) is not dict:
        raise CampaignRefused("stage receipt", "ARTIFACTS_REQUIRED")
    for descriptor in receipt["artifacts"].values():
        _closed(descriptor, {"path", "sha256", "role"}, "artifact")
        if descriptor["role"] not in ARTIFACT_ROLES:
            raise CampaignRefused("artifact", "ROLE_INVALID")
        if (
            plan["scope"] == "PUBLIC_DEVELOPMENT"
            and descriptor["role"] == "SYNTHETIC_FIXTURE"
        ):
            raise CampaignRefused("artifact", "FIXTURE_ROLE_REFUSED")
        _descriptor(
            output,
            {k: descriptor[k] for k in ("path", "sha256")},
            "artifact",
        )
    return receipt


def _terminate(process):
    if process.poll() is None:
        if os.name == "posix":
            import signal

            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def _execute_task(
    task, plan, plan_dir, workspace, prior, prior_receipts, deadline, attempt, stop
):
    key = _key(task)
    output = workspace / key / f"attempt-{attempt}"
    output.mkdir(parents=True, exist_ok=False)
    context = {
        "schema": SCHEMA + ".stage-context",
        "plan_digest": plan["plan_digest"],
        "entrypoint_registration_digest": plan["entrypoint_registration_digest"],
        "scope": plan["scope"],
        "family": task["family"],
        "phase": task["phase"],
        "shard": task["shard"],
        "shards": task["shards"],
        "inputs": {
            name: {
                "path": str(
                    _descriptor(
                        plan_dir,
                        {k: descriptor[k] for k in ("path", "sha256")},
                        "stage input",
                    )
                ),
                "sha256": descriptor["sha256"],
                "role": descriptor["role"],
            }
            for name, descriptor in task["inputs"].items()
        },
        "prior": {
            key: {
                name: descriptor
                for name, descriptor in artifacts.items()
                if task["phase"] != "train"
                or descriptor["role"]
                in ("PUBLIC_TRAIN", "PUBLIC_INPUT", "SYNTHETIC_FIXTURE")
            }
            for key, artifacts in prior.items()
            if key.startswith(task["family"] + "/")
        },
        "prior_receipts": {
            key: pin
            for key, pin in prior_receipts.items()
            if key.startswith(task["family"] + "/")
        },
    }
    context_path = output / "context.json"
    context_path.write_text(
        json.dumps(context, sort_keys=True) + "\n", encoding="utf-8"
    )
    env = dict(os.environ)
    for key_name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        env[key_name] = str(task["vcpus"])
    begin = time.monotonic()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            task["module"],
            "--context",
            str(context_path),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    task_deadline = min(begin + task["planned_wall_s"], deadline)
    try:
        while process.poll() is None:
            if stop.is_set() or time.monotonic() >= task_deadline:
                raise subprocess.TimeoutExpired(process.args, 0)
            try:
                process.wait(timeout=min(0.25, task_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
    except subprocess.TimeoutExpired:
        _terminate(process)
        raise CampaignRefused(
            "execute",
            "WALL_OR_EURO_CAP_REACHED",
            observed_wall_s=time.monotonic() - begin,
        ) from None
    wall_s = time.monotonic() - begin
    if process.returncode:
        raise CampaignRefused(
            "execute",
            "PRODUCER_REFUSED" if process.returncode == 2 else "FAILED_INFRA",
            observed_wall_s=wall_s,
        )
    receipt = _verified_receipt(task, output, plan)
    if receipt["core_s"] > wall_s * task["vcpus"] + 0.05:
        raise CampaignRefused(
            "execute", "CORE_USE_EXCEEDS_ALLOCATION", observed_wall_s=wall_s
        )
    receipt["observed_wall_s"] = wall_s
    receipt["receipt_sha256"] = _sha((output / "receipt.json").read_bytes())
    receipt["attempt_dir"] = output.relative_to(workspace).as_posix()
    return receipt


def _approval(path, pin, plan):
    row = _read(path, pin)
    _closed(
        row,
        {"schema", "plan_digest", "approved_cap_eur", "approved_by", "approval_digest"},
        "approval",
    )
    if (
        row["schema"] != APPROVAL
        or row["plan_digest"] != plan["plan_digest"]
        or row["approved_cap_eur"] != plan["hard_cap_eur"]
        or not row["approved_by"]
        or row["approval_digest"]
        != _digest({k: v for k, v in row.items() if k != "approval_digest"})
    ):
        raise CampaignRefused("approval", "EXACT_PLAN_CAP_APPROVAL_REQUIRED")


def _analysis_with_deadline(operation, seconds):
    if seconds <= 0:
        raise CampaignRefused("analysis", "WALL_OR_EURO_CAP_REACHED")
    if os.name != "posix":
        return operation()  # fixture on noncanonical hosts; real mode is Linux-only

    def timed_out(_signum, _frame):
        raise CampaignRefused("analysis", "WALL_OR_EURO_CAP_REACHED")

    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:
        raise CampaignRefused("analysis", "HOST_TIMER_IN_USE")
    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return operation()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def _finalize(
    family, assembly, score, plan, workspace, registration, rule, producer_receipts
):
    target = workspace / family / "evidence-pack"
    if target.exists():
        receipt = _read(target / "receipt.json")
        if (
            receipt.get("plan_digest") != plan["plan_digest"]
            or receipt.get("family") != family
            or receipt.get("scope") != plan["scope"]
            or any(
                _sha((target / name).read_bytes()) != pin
                for name, pin in receipt["output_byte_pins"].items()
            )
        ):
            raise CampaignRefused("resume", "EVIDENCE_PACK_PIN_MISMATCH")
        report = _read(target / "value-report.json")
        adaptive = _read(target / "adaptive-arms.json")
        return {
            "value_status": report["status"],
            "item_5": report["items"]["5"],
            "adaptive_status": adaptive["status"],
            "score_plugin": (
                "RECORDED_NOT_ADOPTED" if score is not None else "NOT_REGISTERED"
            ),
        }
    output = workspace / assembly["attempt_dir"]
    artifacts = assembly["artifacts"]
    if set(artifacts) != {"manifest", "adaptive_panel", "comparison_bridge"}:
        raise CampaignRefused("analysis", "ASSEMBLY_ARTIFACTS_REQUIRED")
    if (
        artifacts["manifest"]["role"] != "ANALYSIS"
        or artifacts["adaptive_panel"]["role"] != "ANALYSIS"
        or artifacts["comparison_bridge"]["role"] != "ANALYSIS"
    ):
        raise CampaignRefused("analysis", "ANALYSIS_ARTIFACT_ROLE_REQUIRED")
    manifest_path = _descriptor(
        output,
        {k: artifacts["manifest"][k] for k in ("path", "sha256")},
        "analysis",
    )
    adaptive_path = _descriptor(
        output,
        {k: artifacts["adaptive_panel"][k] for k in ("path", "sha256")},
        "analysis",
    )
    manifest, documents, pins = evidence_pipeline.load(
        manifest_path, artifacts["manifest"]["sha256"]
    )
    if manifest["family"] != family or manifest["scope"] != plan["scope"]:
        raise CampaignRefused("analysis", "MANIFEST_FAMILY_OR_SCOPE_MISMATCH")
    if documents["rule"] is not None:
        raise CampaignRefused("analysis", "RULE_MUST_COME_FROM_CAMPAIGN_REGISTRATION")
    outputs = evidence_pipeline.run(manifest, documents, pins)
    panel = _read(adaptive_path, artifacts["adaptive_panel"]["sha256"])
    if panel.get("base_panel") != documents["replay"]:
        raise CampaignRefused("analysis", "ADAPTIVE_REPLAY_IDENTITY_MISMATCH")
    if panel["base_panel"]["source_digest"] != documents["export"]["export_digest"]:
        raise CampaignRefused("analysis", "EXPORT_IDENTITY_MISMATCH")
    bridge_path = _descriptor(
        output,
        {k: artifacts["comparison_bridge"][k] for k in ("path", "sha256")},
        "comparison bridge",
    )
    bridge = _read(bridge_path, artifacts["comparison_bridge"]["sha256"])
    try:
        campaign_entrypoints.verify_bridge(
            bridge,
            family=family,
            scope=plan["scope"],
            manifest_sha256=artifacts["manifest"]["sha256"],
            adaptive_panel_sha256=artifacts["adaptive_panel"]["sha256"],
            export_digest=documents["export"]["export_digest"],
            producer_receipts=producer_receipts,
        )
    except ValueError as exc:
        raise CampaignRefused(
            "comparison bridge", "SOURCE_OR_PANEL_IDENTITY_MISMATCH"
        ) from exc
    adaptive = adaptive_arms.compare(panel, registration, **plan["analysis"])
    if adaptive["status"] != "OK":
        raise CampaignRefused("analysis", "ADAPTIVE_REFERENCE_UNRESOLVED")
    replay = equal_budget.compare(
        documents["replay"], registration=registration, **plan["analysis"]
    )
    evidence = value_bar.seal(
        {
            **{
                k: v
                for k, v in outputs["value-evidence.json"].items()
                if k != "evidence_digest"
            },
            "equal_budget": replay,
        }
    )
    materialized = budget_registration.materialize_value_rule(
        rule, registration, family
    )
    report = value_bar.evaluate(
        evidence,
        materialized,
        bootstrap_replicates=plan["analysis"]["bootstrap_replicates"],
        seed=plan["analysis"]["seed"],
    )
    if plan["scope"] == "SYNTHETIC_FIXTURE":
        report["fixture_only"] = True
    outputs.update(
        {
            "comparison-bridge.json": bridge,
            "equal-budget.json": replay,
            "value-evidence.json": evidence,
            "value-report.json": report,
            "adaptive-arms.json": adaptive,
        }
    )
    if score is not None:
        outputs["score-plugin.json"] = {
            "schema": SCHEMA + ".score-plugin",
            "status": "RECORDED_NOT_ADOPTED",
            "module_receipt_sha256": score["receipt_sha256"],
            "artifacts": score["artifacts"],
        }
    ledger, page = evidence_pipeline.page(outputs, family)
    outputs["ledger.json"] = ledger
    if score is not None:
        page += "\nScore plugin output is pinned locally and is not an adopted scoring rule.\n"
    staging = target.with_name(target.name + f".attempt-{os.getpid()}-{time.time_ns()}")
    staging.mkdir(exist_ok=False)
    for name, body in outputs.items():
        (staging / name).write_text(
            json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    (staging / "evidence.md").write_text(page, encoding="utf-8")
    (staging / "receipt.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA + ".evidence-receipt",
                "plan_digest": plan["plan_digest"],
                "family": family,
                "scope": plan["scope"],
                "value_status": report["status"],
                "input_byte_pins": {
                    "manifest": artifacts["manifest"]["sha256"],
                    "adaptive_panel": artifacts["adaptive_panel"]["sha256"],
                    "comparison_bridge": artifacts["comparison_bridge"]["sha256"],
                },
                "output_byte_pins": {
                    p.name: _sha(p.read_bytes())
                    for p in staging.iterdir()
                    if p.is_file()
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(staging, target)
    return {
        "value_status": report["status"],
        "item_5": report["items"]["5"],
        "adaptive_status": adaptive["status"],
        "score_plugin": (
            "RECORDED_NOT_ADOPTED" if score is not None else "NOT_REGISTERED"
        ),
    }


def run(plan, plan_dir, workspace, *, dry_run, approval=None):
    registration, rule, tasks = validate(plan, plan_dir)
    host = _host(plan)
    if dry_run != (plan["scope"] == "SYNTHETIC_FIXTURE"):
        raise CampaignRefused(
            "mode", "FIXTURE_DRY_RUN_OR_APPROVED_DEVELOPMENT_REQUIRED"
        )
    if not dry_run and approval is None:
        raise CampaignRefused("approval", "OWNER_APPROVAL_REQUIRED")
    if not dry_run:
        if os.name != "posix":
            raise CampaignRefused("host", "LINUX_HOST_REQUIRED")
        _fresh_readiness(plan, plan_dir)
        _approval(*approval, plan)
    sheet = server_sheet(plan, tasks, plan_dir)
    if sheet["total"]["headroom_eur"] < 0:
        raise CampaignRefused("sheet", "PLANNED_CAMPAIGN_EXCEEDS_HARD_CAP")
    workspace.mkdir(parents=True, exist_ok=True)
    state_path = workspace / "checkpoint.json"
    state = _state(state_path, plan)
    if state["last_active_epoch_s"] is not None:
        # After an abrupt stop, bill the unobserved interval conservatively.
        # A provider-side cap remains necessary to stop a host after process death.
        state["billed_wall_s"] += max(0.0, time.time() - state["last_active_epoch_s"])
    state["last_active_epoch_s"] = time.time()
    _save(state_path, state)
    prior = {}
    for task in tasks:
        key = _key(task)
        if key in state["completed"]:
            recorded = state["completed"][key]
            output = workspace / _safe_relative(recorded["attempt_dir"], "resume")
            receipt = _verified_receipt(task, output, plan)
            if recorded["receipt_sha256"] != _sha(
                (output / "receipt.json").read_bytes()
            ):
                raise CampaignRefused("resume", "CHECKPOINT_RECEIPT_MISMATCH")
            prior[key] = _prior_artifacts(output, receipt)
    initial = time.monotonic()
    allowance_s = plan["hard_wall_s"] - state["billed_wall_s"]
    if _hourly_eur(host) > 0:
        allowance_s = min(
            allowance_s,
            (plan["hard_cap_eur"] - host["fixed_eur"]) * 3600 / _hourly_eur(host)
            - state["billed_wall_s"],
        )
    if allowance_s <= 0:
        raise CampaignRefused("cap", "WALL_OR_EURO_CAP_EXHAUSTED")
    deadline = initial + allowance_s
    try:
        for phase in PHASES:
            pending = [
                t
                for t in tasks
                if t["phase"] == phase and _key(t) not in state["completed"]
            ]
            available, available_ram, active = host["vcpus"], host["ram_gb"], {}
            stop = threading.Event()
            with ThreadPoolExecutor(max_workers=host["vcpus"]) as pool:
                while pending or active:
                    for task in list(pending):
                        if (
                            task["vcpus"] <= available
                            and task["peak_ram_gb"] <= available_ram + 1e-9
                        ):
                            attempt = 1
                            while (
                                workspace / _key(task) / f"attempt-{attempt}"
                            ).exists():
                                attempt += 1
                            future = pool.submit(
                                _execute_task,
                                task,
                                plan,
                                plan_dir,
                                workspace,
                                copy.deepcopy(prior),
                                {
                                    key: row["receipt_sha256"]
                                    for key, row in state["completed"].items()
                                },
                                deadline,
                                attempt,
                                stop,
                            )
                            active[future] = task
                            available -= task["vcpus"]
                            available_ram -= task["peak_ram_gb"]
                            pending.remove(task)
                    if not active:
                        raise CampaignRefused("execute", "UNSCHEDULABLE_TASK")
                    done, _ = wait(
                        active,
                        timeout=max(0, min(1, deadline - time.monotonic())),
                        return_when=FIRST_COMPLETED,
                    )
                    if not done and time.monotonic() >= deadline:
                        stop.set()
                        raise CampaignRefused("cap", "EURO_CAP_EXHAUSTED")
                    for future in done:
                        task = active.pop(future)
                        available += task["vcpus"]
                        available_ram += task["peak_ram_gb"]
                        key = _key(task)
                        try:
                            receipt = future.result()
                        except Exception as exc:
                            stop.set()
                            code = (
                                exc.code
                                if isinstance(exc, CampaignRefused)
                                else "FAILED_INFRA"
                            )
                            state["attempts"].append(
                                {
                                    "task": key,
                                    "status": code,
                                    "observed_wall_s": getattr(
                                        exc, "observed_wall_s", None
                                    ),
                                    "core_s": None,
                                    "core_cost_status": "UNKNOWN_IF_NO_COMPLETED_STAGE_RECEIPT",
                                }
                            )
                            state["billed_wall_s"] += time.monotonic() - initial
                            initial = time.monotonic()
                            state["last_active_epoch_s"] = time.time()
                            _save(state_path, state)
                            if isinstance(exc, CampaignRefused):
                                raise
                            raise CampaignRefused("execute", code) from exc
                        state["completed"][key] = receipt
                        prior[key] = _prior_artifacts(
                            workspace / receipt["attempt_dir"], receipt
                        )
                        state["attempts"].append(
                            {
                                "task": key,
                                "status": "OK",
                                "observed_wall_s": receipt["observed_wall_s"],
                                "core_s": receipt["core_s"],
                                "core_cost_status": "PRODUCER_REPORTED",
                            }
                        )
                        state["billed_wall_s"] += time.monotonic() - initial
                        initial = time.monotonic()
                        state["last_active_epoch_s"] = time.time()
                        _save(state_path, state)
        results = {}
        for family in FAMILIES:
            begin, cpu_begin = time.monotonic(), time.process_time()
            reserve = plan["analysis_reserve"][family]
            try:
                results[family] = _analysis_with_deadline(
                    lambda family=family: _finalize(
                        family,
                        state["completed"][f"{family}/assemble/0"],
                        state["completed"].get(f"{family}/score/0"),
                        plan,
                        workspace,
                        registration,
                        rule,
                        {
                            phase: [
                                state["completed"][key]["receipt_sha256"]
                                for key in sorted(state["completed"])
                                if key.startswith(f"{family}/{phase}/")
                            ]
                            for phase in ("reference", "train")
                        },
                    ),
                    min(reserve["wall_s"], deadline - time.monotonic()),
                )
            finally:
                spent_wall = time.monotonic() - begin
                spent_core = time.process_time() - cpu_begin
                row = {
                    "wall_s": spent_wall,
                    "core_s": spent_core,
                    "status": "MEASURED_ATTEMPT",
                }
                state["analysis_costs"].setdefault(family, []).append(row)
                state["billed_wall_s"] += time.monotonic() - initial
                initial = time.monotonic()
                state["last_active_epoch_s"] = time.time()
                _save(state_path, state)
            if spent_core > reserve["core_s"] or time.monotonic() >= deadline:
                raise CampaignRefused("analysis", "ANALYSIS_OR_EURO_CAP_REACHED")
        actual_eur = host["fixed_eur"] + state["billed_wall_s"] / 3600 * _hourly_eur(
            host
        )
        if actual_eur > plan["hard_cap_eur"]:
            raise CampaignRefused("cap", "EURO_CAP_EXHAUSTED")
        sheet["observed"] = {
            "billable_wall_hours_in_runner": state["billed_wall_s"] / 3600,
            "eur_running_charge": actual_eur,
            "producer_core_hours_reported": sum(
                r["core_s"] for r in state["completed"].values()
            )
            / 3600,
            "analysis_core_hours_measured": sum(
                row["core_s"]
                for attempts in state["analysis_costs"].values()
                for row in attempts
            )
            / 3600,
        }
        (workspace / "owner-server-sheet.json").write_text(
            json.dumps(sheet, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        state["last_active_epoch_s"] = None
        _save(state_path, state)
        return {
            "schema": SCHEMA + ".summary",
            "plan_digest": plan["plan_digest"],
            "scope": plan["scope"],
            "challenges": results,
            "sheet": sheet["total"],
            "no_scientific_qualification": True,
        }
    except Exception:
        state["billed_wall_s"] += time.monotonic() - initial
        state["last_active_epoch_s"] = time.time()
        _save(state_path, state)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sheet-only", action="store_true")
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--approval-sha256")
    args = parser.parse_args(argv)
    try:
        plan = _read(args.plan, args.plan_sha256)
        registration, rule, tasks = validate(
            plan,
            args.plan.parent,
            require_ready=not args.sheet_only,
            require_modules=not args.sheet_only,
        )
        del registration, rule
        if args.sheet_only:
            result = server_sheet(plan, tasks, args.plan.parent)
            result["planning_only"] = True
            result["dispatch_authorized"] = False
            result["readiness"] = {}
            result["registration_gaps"] = {}
            result["registration_gap_owner"] = "Data Collection"
            result["entrypoint_status"] = campaign_entrypoints.inspect(ROOT)
            for family in FAMILIES:
                descriptor = plan["readiness"][family]
                observation = _readiness(
                    _descriptor(args.plan.parent, descriptor, "readiness"),
                    descriptor["sha256"],
                    family,
                    require_yes=False,
                )
                result["readiness"][family] = {
                    "yes_count": observation["yes_count"],
                    "non_yes_items": [
                        item["item"]
                        for item in observation["items"]
                        if item["state"] != "YES"
                    ],
                }
                gaps = []
                gaps.extend(
                    f"Data Collection {phase} entrypoint: {state}"
                    for phase, state in result["entrypoint_status"][family].items()
                    if state != "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
                )
                for task in tasks:
                    if task["family"] != family:
                        continue
                    try:
                        _module(task, plan["scope"])
                    except CampaignRefused:
                        gaps.append(_key(task))
                result["registration_gaps"][family] = gaps
        else:
            if args.execute and (args.approval is None or args.approval_sha256 is None):
                raise CampaignRefused("approval", "OWNER_APPROVAL_REQUIRED")
            approval = (args.approval, args.approval_sha256) if args.execute else None
            result = run(
                plan,
                args.plan.parent,
                args.workspace,
                dry_run=args.dry_run,
                approval=approval,
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (CampaignRefused, ValueError, OSError) as exc:
        stage = exc.stage if isinstance(exc, CampaignRefused) else "campaign"
        code = (
            exc.code
            if isinstance(exc, CampaignRefused)
            else "INVALID_OR_UNAVAILABLE_INPUT"
        )
        print(json.dumps({"status": "REFUSED", "stage": stage, "reason": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
