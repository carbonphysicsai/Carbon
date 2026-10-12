"""Receipt-bound source loading for a prospective campaign assembly stage.

Only the producer's sealed panel and PUBLIC_TRAIN rows cross this boundary.
Missing or inconsistent source receipts refuse assembly before a comparison
document can be emitted. No solver, model or comparator is run here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from carbon.design_search import producer_panels
from carbon.development_comparison import (
    campaign_entrypoints,
    evidence_campaign,
    evidence_pipeline,
)

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
    allowed = (
        {"panel-export", "stage-summary"}
        if phase == "reference"
        else {"train", "stage-summary"}
    )
    prefixes = (
        ("reference-records-",)
        if phase == "reference"
        else ("train-records-", "train-diagnostics-")
    )
    if any(name not in allowed and not name.startswith(prefixes) for name in prior):
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
        {"panel-export", "stage-summary"},
        {"panel-export": "HELDOUT_REFERENCE", "stage-summary": "ANALYSIS"},
    )
    train_artifacts, train_pin = _source(
        context,
        family,
        "train",
        {"train", "stage-summary"},
        {"train": "PUBLIC_TRAIN", "stage-summary": "ANALYSIS"},
    )
    _chunks(reference, "reference-records", family, "HELDOUT_REFERENCE")
    _chunks(train_artifacts, "train-records", family, "PUBLIC_TRAIN")
    if family == "f02":
        _chunks(train_artifacts, "train-diagnostics", family, "PUBLIC_TRAIN")
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
    return ProducerSources(
        family,
        scope,
        export,
        train,
        raw,
        ref_summary,
        train_summary,
        {"reference": [ref_pin], "train": [train_pin]},
    )


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.process_time()
    try:
        context = evidence_pipeline._json(args.context.read_bytes())
        sources = load_producer_sources(context)
        artifacts = assemble_fixture(context, sources, args.output)
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
