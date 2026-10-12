"""Receipt-bound source loading for a prospective campaign assembly stage.

Only the producer's sealed panel and PUBLIC_TRAIN rows cross this boundary.
Missing or inconsistent source receipts refuse assembly before a comparison
document can be emitted. No solver, model or comparator is run here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search import budget_registration, producer_panels
from carbon.development_comparison import (
    campaign_entrypoints,
    evidence_campaign,
    evidence_pipeline,
)
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb
from carbon.development_comparison.campaign_adapters import assembly_design

CONTEXT = evidence_campaign.SCHEMA + ".stage-context"
TRAIN = evidence_campaign.SCHEMA + ".producer-train.v1"
SUMMARY = evidence_campaign.SCHEMA + ".producer-summary.v1"
RECORDS = evidence_campaign.SCHEMA + ".producer-records.v1"
TRAIN_SCHEMAS = {
    "battery-v3": "carbon.battery-v3.train-record.v1",
    "motor": "carbon.motor-10p12s.train-record.v1",
    "f02": "carbon.f02.train-record.v1",
}
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


class AssemblyRefused(ValueError):
    """A source is missing, unpinned, or contradicts the producer contract."""


@dataclass(frozen=True)
class ProducerSources:
    family: str
    scope: str
    export: dict
    train: dict
    train_jsonl: bytes
    reference_summary: dict
    train_summary: dict
    producer_receipts: dict[str, list[str]]
    reference_artifacts: dict
    train_artifacts: dict


def _read(descriptor, role):
    if type(descriptor) is not dict or set(descriptor) != {"path", "sha256", "role"}:
        raise AssemblyRefused("CLOSED_PRODUCER_ARTIFACT_REQUIRED")
    if descriptor["role"] != role or not SHA.fullmatch(str(descriptor["sha256"])):
        raise AssemblyRefused("PRODUCER_ROLE_OR_PIN_MISMATCH")
    path = Path(descriptor["path"])
    try:
        return evidence_campaign._read(path, descriptor["sha256"])
    except (evidence_campaign.CampaignRefused, evidence_pipeline.Refusal) as exc:
        raise AssemblyRefused("PRODUCER_ARTIFACT_UNAVAILABLE") from exc


def _source(context, family, phase, required, role):
    key = f"{family}/{phase}/0"
    prior = context["prior"].get(key)
    pin = context["prior_receipts"].get(key)
    if type(prior) is not dict or not SHA.fullmatch(str(pin)):
        raise AssemblyRefused("PRODUCER_RECEIPT_MISSING")
    if not required <= set(prior):
        raise AssemblyRefused("PRODUCER_ARTIFACT_MISSING")
    fixed = (
        {"panel-export", "stage-summary", "candidate-view", "cost-ledger"}
        | (
            {"bindings", "comparator-materials"}
            if family in ("f02", "motor")
            else set()
        )
        | ({"comparator-witness-manifest"} if family == "f02" else set())
        if phase == "reference"
        else {"train", "stage-summary", "carbon-predictions", "carbon-receipt"}
    )
    chunks = (
        ("reference-records", "comparator-witness")
        if phase == "reference" and family == "f02"
        else (
            ("reference-records",)
            if phase == "reference"
            else (
                ("train-records", "train-diagnostics")
                if family == "f02"
                else ("train-records",)
            )
        )
    )
    if any(
        name not in fixed
        and not any(re.fullmatch(prefix + r"-[0-9]{3}", name) for prefix in chunks)
        for name in prior
    ):
        raise AssemblyRefused("UNREGISTERED_PRODUCER_ARTIFACT")
    if any(
        type(descriptor) is not dict
        or set(descriptor) != {"path", "sha256", "role"}
        or not SHA.fullmatch(str(descriptor["sha256"]))
        for descriptor in prior.values()
    ):
        raise AssemblyRefused("CLOSED_PRODUCER_ARTIFACT_REQUIRED")
    if any(prior[name].get("role") != expected for name, expected in role.items()):
        raise AssemblyRefused("PRODUCER_ROLE_OR_PIN_MISMATCH")
    try:
        receipt = evidence_campaign._read(
            Path(prior["stage-summary"]["path"]).parent / "receipt.json", pin
        )
    except (evidence_campaign.CampaignRefused, evidence_pipeline.Refusal) as exc:
        raise AssemblyRefused("PRODUCER_RECEIPT_PIN_MISMATCH") from exc
    if (
        receipt.get("schema") != evidence_campaign.STAGE_RESULT
        or receipt.get("plan_digest") != context["plan_digest"]
        or receipt.get("family") != family
        or receipt.get("phase") != phase
        or receipt.get("status") != "OK"
        or receipt.get("shard") != 0
        or receipt.get("artifacts")
        != {
            name: {
                **descriptor,
                "path": Path(descriptor["path"]).name,
            }
            for name, descriptor in prior.items()
        }
    ):
        raise AssemblyRefused("PRODUCER_RECEIPT_CONTENT_MISMATCH")
    return prior, pin


def _chunks(artifacts, prefix, family, role):
    names = sorted(name for name in artifacts if name.startswith(prefix + "-"))
    if not names or names != [f"{prefix}-{i:03d}" for i in range(len(names))]:
        raise AssemblyRefused("PRODUCER_RECORD_CHUNKS_INCOMPLETE")
    for i, name in enumerate(names):
        row = _read(artifacts[name], role)
        if (
            type(row) is not dict
            or set(row) != {"schema", "family", "chunk", "records"}
            or row["schema"] != RECORDS
            or row["family"] != family
            or row["chunk"] != i
            or type(row["records"]) is not list
        ):
            raise AssemblyRefused("PRODUCER_RECORD_CHUNK_INVALID")
        if any(
            type(record) is not dict or set(record) != {"dir", "record"}
            for record in row["records"]
        ):
            raise AssemblyRefused("PRODUCER_RECORD_CHUNK_INVALID")


def _registered_comparison_inputs(
    family, scope, export, raw, reference, train_artifacts
):
    """Read the exact #1114 additions and check their independent identities."""
    view = _read(reference["candidate-view"], "PUBLIC_INPUT")
    safe = copy.deepcopy(export)
    for entry in safe["questions"]:
        entry.pop("settled", None)
        for _, _, panel in cb._panels(entry):
            for row in panel:
                row["values"] = {
                    q: 0.0 for q in row["values"] if not q.startswith("refined.")
                }
    if view != {
        "schema": "carbon.development-evidence-campaign.producer-candidate-view.v1",
        "family": family,
        "export_digest": export["export_digest"],
        "export": safe,
    }:
        raise AssemblyRefused("CANDIDATE_VIEW_LEAK_OR_IDENTITY_MISMATCH")
    ledger = _read(reference["cost-ledger"], "HELDOUT_REFERENCE")
    expected = {
        (r["band"], r["candidate"], r["condition"]) for r in cb._physical_rows(export)
    }
    if (
        type(ledger) is not dict
        or set(ledger) != {"schema", "family", "export_digest", "basis", "rows"}
        or ledger["schema"]
        != "carbon.development-evidence-campaign.producer-cost-ledger.v1"
        or ledger["family"] != family
        or ledger["export_digest"] != export["export_digest"]
        or type(ledger["basis"]) is not str
        or not ledger["basis"]
        or type(ledger["rows"]) is not list
        or len(ledger["rows"]) != len(expected)
    ):
        raise AssemblyRefused("COST_LEDGER_INVALID")
    seen = set()
    for row in ledger["rows"]:
        if type(row) is not dict or set(row) != {
            "band",
            "candidate",
            "condition",
            "solves",
            "wall_s",
            "core_s",
        }:
            raise AssemblyRefused("COST_LEDGER_INVALID")
        key = (row["band"], row["candidate"], row["condition"])
        if (
            key not in expected
            or key in seen
            or type(row["solves"]) is not list
            or not row["solves"]
        ):
            raise AssemblyRefused("COST_LEDGER_INVENTORY_MISMATCH")
        seen.add(key)
        walls, cores = [], []
        for solve in row["solves"]:
            if type(solve) is not dict or set(solve) != {
                "source",
                "rung",
                "status",
                "wall_s",
                "core_s",
            }:
                raise AssemblyRefused("COST_LEDGER_SOLVE_INVALID")
            wall, core = solve["wall_s"], solve["core_s"]
            if (
                type(wall) not in (int, float)
                or wall <= 0
                or not float(wall) < float("inf")
                or (
                    core is not None
                    and (
                        type(core) not in (int, float)
                        or core < 0
                        or not float(core) < float("inf")
                    )
                )
            ):
                raise AssemblyRefused("COST_LEDGER_SOLVE_INVALID")
            if core is None and family != "battery-v3":
                raise AssemblyRefused("COST_LEDGER_CPU_MISSING")
            walls.append(wall)
            cores.append(core)
        if row["wall_s"] != sum(walls) or row["core_s"] != (
            None if None in cores else sum(cores)
        ):
            raise AssemblyRefused("COST_LEDGER_TOTAL_MISMATCH")
    predictions = _read(train_artifacts["carbon-predictions"], "MODEL")
    receipt = _read(train_artifacts["carbon-receipt"], "MODEL")
    receipt_pin = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                receipt, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )
    if (
        type(receipt) is not dict
        or type(receipt.get("train")) is not dict
        or (
            scope == "PUBLIC_DEVELOPMENT"
            and receipt.get("schema") != "carbon.development-carbon-arm-receipt.v1"
        )
        or (
            scope == "PUBLIC_DEVELOPMENT"
            and receipt["train"].get("fixture") is not False
        )
        or receipt.get("scope") != scope
        or receipt.get("export_digest") != export["export_digest"]
        or receipt["train"].get("sha256") != "sha256:" + hashlib.sha256(raw).hexdigest()
        or type(predictions) is not dict
        or predictions.get("scope") != scope
        or predictions.get("source_receipt_digest") != receipt_pin
        or predictions.get("model_id") != receipt.get("model_id")
    ):
        raise AssemblyRefused("CARBON_RECEIPT_OR_TRAIN_IDENTITY_MISMATCH")
    try:
        evidence_pipeline._predictions(export, predictions)
    except (ValueError, KeyError, TypeError, evidence_pipeline.Refusal) as exc:
        raise AssemblyRefused("CARBON_PREDICTIONS_INVALID") from exc
    return ledger, predictions, receipt


def _comparator_materials(sources):
    """Resolve the producer's model-neutral comparator, preserving fine witnesses."""
    if sources.family == "battery-v3":
        return None
    material = _read(
        sources.reference_artifacts["comparator-materials"], "HELDOUT_REFERENCE"
    )
    if sources.family == "motor":
        if material.get("export_digest") != sources.export["export_digest"]:
            raise AssemblyRefused("MOTOR_COMPARATOR_IDENTITY_MISMATCH")
        return material
    names = sorted(
        name
        for name in sources.reference_artifacts
        if re.fullmatch(r"comparator-witness-[0-9]{3}", name)
    )
    rows = []
    for i, name in enumerate(names):
        chunk = _read(sources.reference_artifacts[name], "HELDOUT_REFERENCE")
        if (
            type(chunk) is not dict
            or set(chunk) != {"schema", "family", "export_digest", "chunk", "rows"}
            or chunk["schema"]
            != "carbon.development-evidence-campaign.producer-f02-witness.v1"
            or chunk["family"] != "f02"
            or chunk["export_digest"] != sources.export["export_digest"]
            or chunk["chunk"] != i
            or type(chunk["rows"]) is not list
            or not chunk["rows"]
            or len(chunk["rows"]) > 96
        ):
            raise AssemblyRefused("F02_WITNESS_CHUNK_INVALID")
        rows.extend(chunk["rows"])
    try:
        pb.validate_materials(sources.export, material, witness_rows=rows)
    except (ValueError, KeyError, TypeError) as exc:
        raise AssemblyRefused("F02_COMPARATOR_WITNESS_INVALID") from exc
    return {
        "schema": evidence_pipeline.F02_FINE_BUNDLE,
        "scope": sources.scope,
        "export_digest": sources.export["export_digest"],
        "materials": material,
        "witness_rows": rows,
        "witness_manifest_sha256": sources.reference_artifacts[
            "comparator-witness-manifest"
        ]["sha256"],
    }


def load_producer_sources(context):
    """Validate #1114's one-shard reference/TRAIN receipt and output contract."""
    fields = {
        "schema",
        "plan_digest",
        "entrypoint_registration_digest",
        "scope",
        "family",
        "phase",
        "shard",
        "shards",
        "vcpus",
        "inputs",
        "prior",
        "prior_receipts",
        "analysis",
    }
    if (
        type(context) is not dict
        or set(context) != fields
        or context["schema"] != CONTEXT
    ):
        raise AssemblyRefused("STAGE_CONTEXT_INVALID")
    family = context["family"]
    scope = context["scope"]
    if family not in TRAIN_SCHEMAS or scope not in {
        "PUBLIC_DEVELOPMENT",
        "SYNTHETIC_FIXTURE",
    }:
        raise AssemblyRefused("FAMILY_OR_SCOPE_INVALID")
    if (
        context["phase"] != "assemble"
        or context["shard"] != 0
        or context["shards"] != 1
        or type(context["vcpus"]) is not int
        or context["vcpus"] < 1
        or context["entrypoint_registration_digest"] != campaign_entrypoints.digest()
        or not SHA.fullmatch(str(context["plan_digest"]))
        or type(context["inputs"]) is not dict
        or type(context["analysis"]) is not dict
        or type(context["prior"]) is not dict
        or type(context["prior_receipts"]) is not dict
    ):
        raise AssemblyRefused("STAGE_IDENTITY_MISMATCH")
    keys = {f"{family}/{phase}/0" for phase in ("reference", "train")}
    if set(context["prior"]) != keys or set(context["prior_receipts"]) != keys:
        raise AssemblyRefused("EXACT_PRODUCER_STAGE_SET_REQUIRED")
    reference, ref_pin = _source(
        context,
        family,
        "reference",
        (
            {"panel-export", "stage-summary", "candidate-view", "cost-ledger"}
            | (
                {"bindings", "comparator-materials"}
                if family in ("f02", "motor")
                else set()
            )
            | ({"comparator-witness-manifest"} if family == "f02" else set())
        ),
        {
            "panel-export": "HELDOUT_REFERENCE",
            "stage-summary": "ANALYSIS",
            "candidate-view": "PUBLIC_INPUT",
            "cost-ledger": "HELDOUT_REFERENCE",
            **(
                {
                    "bindings": "HELDOUT_REFERENCE",
                    "comparator-materials": "HELDOUT_REFERENCE",
                }
                if family in ("f02", "motor")
                else {}
            ),
            **(
                {"comparator-witness-manifest": "HELDOUT_REFERENCE"}
                if family == "f02"
                else {}
            ),
        },
    )
    train_artifacts, train_pin = _source(
        context,
        family,
        "train",
        {"train", "stage-summary", "carbon-predictions", "carbon-receipt"},
        {
            "train": "PUBLIC_TRAIN",
            "stage-summary": "ANALYSIS",
            "carbon-predictions": "MODEL",
            "carbon-receipt": "MODEL",
        },
    )
    _chunks(reference, "reference-records", family, "HELDOUT_REFERENCE")
    _chunks(train_artifacts, "train-records", family, "PUBLIC_TRAIN")
    if family == "f02":
        _chunks(train_artifacts, "train-diagnostics", family, "PUBLIC_TRAIN")
        names = sorted(
            n for n in reference if re.fullmatch(r"comparator-witness-[0-9]{3}", n)
        )
        if not names or names != [
            f"comparator-witness-{i:03d}" for i in range(len(names))
        ]:
            raise AssemblyRefused("F02_WITNESS_CHUNKS_INCOMPLETE")
        manifest = _read(reference["comparator-witness-manifest"], "HELDOUT_REFERENCE")
        if (
            type(manifest) is not dict
            or set(manifest) != {"schema", "family", "export_digest", "chunks"}
            or manifest["schema"]
            != "carbon.development-evidence-campaign.producer-f02-witness-manifest.v1"
            or manifest["family"] != family
            or type(manifest["chunks"]) is not list
            or len(manifest["chunks"]) != len(names)
        ):
            raise AssemblyRefused("F02_WITNESS_MANIFEST_INVALID")
        for i, name in enumerate(names):
            item = manifest["chunks"][i]
            if (
                type(item) is not dict
                or set(item) != {"order", "name", "sha256"}
                or item
                != {
                    "order": i,
                    "name": name + ".json",
                    "sha256": reference[name]["sha256"][7:],
                }
            ):
                raise AssemblyRefused("F02_WITNESS_MANIFEST_PIN_MISMATCH")
    export = _read(reference["panel-export"], "HELDOUT_REFERENCE")
    train = _read(train_artifacts["train"], "PUBLIC_TRAIN")
    ref_summary = _read(reference["stage-summary"], "ANALYSIS")
    train_summary = _read(train_artifacts["stage-summary"], "ANALYSIS")
    try:
        producer_panels.adapt_export(export)
    except ValueError as exc:
        raise AssemblyRefused("PANEL_EXPORT_INVALID") from exc
    if export["family"] != family:
        raise AssemblyRefused("PANEL_FAMILY_MISMATCH")
    if family == "f02" and manifest["export_digest"] != export["export_digest"]:
        raise AssemblyRefused("F02_WITNESS_EXPORT_MISMATCH")
    if (
        type(train) is not dict
        or set(train)
        != {"schema", "family", "record_schema", "jsonl_sha256", "records", "export"}
        or train["schema"] != TRAIN
        or train["family"] != family
        or train["record_schema"] != TRAIN_SCHEMAS[family]
        or type(train["records"]) is not list
        or not train["records"]
        or any(row.get("schema") != train["record_schema"] for row in train["records"])
    ):
        raise AssemblyRefused("PUBLIC_TRAIN_INVALID")
    raw = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in train["records"]
    ).encode()
    if hashlib.sha256(raw).hexdigest() != train["jsonl_sha256"]:
        raise AssemblyRefused("PUBLIC_TRAIN_JSONL_PIN_MISMATCH")
    for phase, summary in (("reference", ref_summary), ("train", train_summary)):
        if (
            type(summary) is not dict
            or summary.get("schema") != SUMMARY
            or summary.get("family") != family
            or summary.get("phase") != phase
            or summary.get("entrypoint")
            != campaign_entrypoints.ENTRYPOINTS[family][phase]
            or summary.get("vcpus") != context["vcpus"]
            or type(summary.get("counts")) is not dict
            or type(summary.get("steps")) is not list
            or type(summary.get("meter")) is not dict
        ):
            raise AssemblyRefused("PRODUCER_SUMMARY_MISMATCH")
    if ref_summary["counts"].get("export_digest") != export["export_digest"]:
        raise AssemblyRefused("PRODUCER_EXPORT_DIGEST_MISMATCH")
    if train_summary["counts"].get("train_rows") != len(train["records"]):
        raise AssemblyRefused("PRODUCER_TRAIN_COUNT_MISMATCH")
    _registered_comparison_inputs(
        family, scope, export, raw, reference, train_artifacts
    )
    sources = ProducerSources(
        family,
        scope,
        export,
        train,
        raw,
        ref_summary,
        train_summary,
        {"reference": [ref_pin], "train": [train_pin]},
        reference,
        train_artifacts,
    )
    _comparator_materials(sources)
    return sources


def _fixture_input(context, name):
    descriptor = context["inputs"].get(name)
    if (
        type(descriptor) is not dict
        or set(descriptor) != {"path", "sha256", "role"}
        or descriptor["role"] != "SYNTHETIC_FIXTURE"
        or not SHA.fullmatch(str(descriptor["sha256"]))
    ):
        raise AssemblyRefused("PINNED_FIXTURE_INPUT_REQUIRED")
    path = Path(descriptor["path"])
    _read(descriptor, "SYNTHETIC_FIXTURE")
    return path, descriptor["sha256"]


def assemble_fixture(context, sources, output):
    """Exercise the complete assembly boundary on synthetic documents only.

    A public comparison needs registered builders for model predictions,
    competitor materials and measured per-design replay costs. The producer's
    v1 receipts do not provide them, so this route cannot yield public evidence.
    """
    if sources.scope != "SYNTHETIC_FIXTURE":
        raise AssemblyRefused("COMPARISON_BUILDERS_NOT_REGISTERED")
    if set(context["inputs"]) != {"manifest", "adaptive_panel"}:
        raise AssemblyRefused("FIXTURE_COMPARISON_INPUTS_REQUIRED")
    manifest_path, manifest_pin = _fixture_input(context, "manifest")
    adaptive_path, adaptive_pin = _fixture_input(context, "adaptive_panel")
    try:
        manifest, documents, _ = evidence_pipeline.load(manifest_path, manifest_pin)
    except evidence_pipeline.Refusal as exc:
        raise AssemblyRefused("FIXTURE_COMPARISON_INVALID") from exc
    if (
        manifest["scope"] != sources.scope
        or manifest["family"] != sources.family
        or manifest["analysis"] != context["analysis"]
        or documents["export"] != sources.export
    ):
        raise AssemblyRefused("PRODUCER_COMPARISON_IDENTITY_MISMATCH")
    adaptive = _read(context["inputs"]["adaptive_panel"], "SYNTHETIC_FIXTURE")
    if (
        type(adaptive) is not dict
        or adaptive.get("base_panel") != documents["replay"]
        or adaptive["base_panel"].get("source_digest")
        != sources.export["export_digest"]
    ):
        raise AssemblyRefused("ADAPTIVE_REPLAY_IDENTITY_MISMATCH")
    output.mkdir(parents=True, exist_ok=True)
    for descriptor in manifest["files"].values():
        if descriptor is None:
            continue
        relative = evidence_campaign._safe_relative(descriptor["path"], "fixture")
        source = manifest_path.parent / relative
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shutil.copyfile(manifest_path, output / "manifest.json")
    shutil.copyfile(adaptive_path, output / "adaptive_panel.json")
    evidence_pipeline.load(output / "manifest.json", manifest_pin)
    bridge = campaign_entrypoints.seal_bridge(
        {
            "schema": campaign_entrypoints.BRIDGE_SCHEMA,
            "family": sources.family,
            "scope": sources.scope,
            "entrypoint_registration_digest": context["entrypoint_registration_digest"],
            "producer_receipts": sources.producer_receipts,
            "manifest_sha256": manifest_pin,
            "adaptive_panel_sha256": adaptive_pin,
            "export_digest": sources.export["export_digest"],
        }
    )
    (output / "comparison_bridge.json").write_text(
        json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = {}
    for name in ("manifest", "adaptive_panel", "comparison_bridge"):
        path = output / (name + ".json")
        artifacts[name] = {
            "path": path.name,
            "sha256": evidence_campaign._sha(path.read_bytes()),
            "role": "ANALYSIS",
        }
    return artifacts


def registered_design(context, sources):
    """Build, but do not run, the comparison from the sealed producer outputs."""
    if context["inputs"]:
        raise AssemblyRefused("UNREGISTERED_ASSEMBLY_INPUT")
    ledger = _read(sources.reference_artifacts["cost-ledger"], "HELDOUT_REFERENCE")
    predictions = _read(sources.train_artifacts["carbon-predictions"], "MODEL")
    receipt = _read(sources.train_artifacts["carbon-receipt"], "MODEL")
    comparator = _comparator_materials(sources)
    bindings = (
        None
        if sources.family == "battery-v3"
        else _read(sources.reference_artifacts["bindings"], "HELDOUT_REFERENCE")
    )
    try:
        replay, bound = assembly_design.build(
            sources.export, ledger, predictions, receipt, comparator, bindings
        )
        context_value = assembly_design.value_context(sources.export, predictions)
        base_rule = json.loads(
            (
                assembly_design.ROOT
                / "docs/development/challenge_pipeline/value-bar-v1.json"
            ).read_text()
        )
        registration_name = (
            "equal-budget-registration-v2-f02-menu.json"
            if sources.family == "f02"
            else "equal-budget-registration-v1.json"
        )
        registration = json.loads(
            (
                assembly_design.ROOT
                / "docs/development/challenge_pipeline"
                / registration_name
            ).read_text()
        )
        rule = budget_registration.materialize_value_rule(
            base_rule, registration, sources.family
        )
    except (
        assembly_design.DesignRefused,
        budget_registration.BudgetRegistrationError,
        evidence_pipeline.Refusal,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise AssemblyRefused("REGISTERED_COMPARISON_DESIGN_INVALID") from exc
    return {
        "export": sources.export,
        "comparator": comparator,
        "carbon": predictions,
        "replay": replay,
        "bindings": bound,
        "context": context_value,
        "rule": rule,
    }


def assemble_registered(context, sources, output):
    """Public assembly remains closed until independent adaptive policy custody exists."""
    documents = registered_design(context, sources)
    if documents["replay"]["cost_basis"] != "MEASURED":
        raise AssemblyRefused("MEASURED_COMPLETE_PANEL_CPU_COST_REQUIRED")
    # #1056 requires an independently registered calibration policy and a
    # pre-experiment receipt. #1114's TRAIN follows reference in this runner;
    # neither its digest nor locally invented constants establish chronology.
    # No public comparison bridge is emitted until that custody exists.
    raise AssemblyRefused("PRE_EXPERIMENT_ADAPTIVE_POLICY_RECEIPT_REQUIRED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.process_time()
    try:
        context = evidence_pipeline._json(args.context.read_bytes())
        sources = load_producer_sources(context)
        artifacts = (
            assemble_fixture(context, sources, args.output)
            if sources.scope == "SYNTHETIC_FIXTURE"
            else assemble_registered(context, sources, args.output)
        )
    except (
        AssemblyRefused,
        evidence_pipeline.Refusal,
        evidence_campaign.CampaignRefused,
        json.JSONDecodeError,
        UnicodeError,
        OSError,
    ) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2
    receipt = {
        "schema": evidence_campaign.STAGE_RESULT,
        "plan_digest": context["plan_digest"],
        "family": sources.family,
        "phase": "assemble",
        "shard": 0,
        "status": "OK",
        "core_s": round(time.process_time() - started, 3),
        "peak_ram_bytes": 0,
        "artifacts": artifacts,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
