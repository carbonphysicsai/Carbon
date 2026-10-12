"""Synthetic documents shaped like #1114's producer stage outputs only."""

import hashlib
import json

import pytest
from test_evidence_campaign import _fixture as campaign_fixture
from test_evidence_pipeline import bundle

from carbon.development_comparison import campaign_entrypoints, evidence_pipeline
from carbon.development_comparison import evidence_campaign as campaign
from carbon.development_comparison.campaign_adapters import assemble


def _write(path, document, role):
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    return {"path": str(path), "sha256": campaign._sha(path.read_bytes()), "role": role}


def _context(tmp_path, family="battery-v3"):
    _, docs = bundle(family, full_f02=family == "f02")
    export = docs["export"]
    row = {
        "schema": assemble.TRAIN_SCHEMAS[family],
        "case_id": "fixture-train-0",
        "inputs": {"setting": 1},
        "outputs": {"value": 2.0},
        "fixture": True,
    }
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    train = {
        "schema": assemble.TRAIN,
        "family": family,
        "record_schema": assemble.TRAIN_SCHEMAS[family],
        "jsonl_sha256": hashlib.sha256(raw).hexdigest(),
        "records": [row],
        "export": {"rows": 1},
    }
    prior, pins = {}, {}
    for phase in ("reference", "train"):
        folder = tmp_path / phase
        folder.mkdir(parents=True)
        artifacts = {}
        if phase == "reference":
            artifacts["panel-export"] = _write(
                folder / "panel-export.json", export, "HELDOUT_REFERENCE"
            )
            artifacts["reference-records-000"] = _write(
                folder / "reference-records-000.json",
                {
                    "schema": assemble.RECORDS,
                    "family": family,
                    "chunk": 0,
                    "records": [{"dir": "fixture", "record": {"case_id": "a"}}],
                },
                "HELDOUT_REFERENCE",
            )
        else:
            artifacts["train"] = _write(folder / "train.json", train, "PUBLIC_TRAIN")
            artifacts["train-records-000"] = _write(
                folder / "train-records-000.json",
                {
                    "schema": assemble.RECORDS,
                    "family": family,
                    "chunk": 0,
                    "records": [{"dir": "fixture", "record": {"case_id": "b"}}],
                },
                "PUBLIC_TRAIN",
            )
            if family == "f02":
                artifacts["train-diagnostics-000"] = _write(
                    folder / "train-diagnostics-000.json",
                    {
                        "schema": assemble.RECORDS,
                        "family": family,
                        "chunk": 0,
                        "records": [{"dir": "fixture", "record": {"case_id": "b"}}],
                    },
                    "PUBLIC_TRAIN",
                )
        artifacts["stage-summary"] = _write(
            folder / "stage-summary.json",
            {
                "schema": assemble.SUMMARY,
                "family": family,
                "phase": phase,
                "entrypoint": campaign_entrypoints.ENTRYPOINTS[family][phase],
                "vcpus": 2,
                "steps": [],
                "counts": (
                    {"export_digest": export["export_digest"]}
                    if phase == "reference"
                    else {"train_rows": len(train["records"])}
                ),
                "meter": {},
            },
            "ANALYSIS",
        )
        receipt = {
            "schema": campaign.STAGE_RESULT,
            "plan_digest": "sha256:" + "0" * 64,
            "family": family,
            "phase": phase,
            "shard": 0,
            "status": "OK",
            "core_s": 1.0,
            "peak_ram_bytes": 4096,
            "artifacts": {
                name: {**descriptor, "path": descriptor["path"].split("/")[-1]}
                for name, descriptor in artifacts.items()
            },
        }
        pin = _write(folder / "receipt.json", receipt, "ANALYSIS")["sha256"]
        key = f"{family}/{phase}/0"
        prior[key], pins[key] = artifacts, pin
    context = {
        "schema": assemble.CONTEXT,
        "plan_digest": "sha256:" + "0" * 64,
        "entrypoint_registration_digest": campaign_entrypoints.digest(),
        "scope": "SYNTHETIC_FIXTURE",
        "family": family,
        "phase": "assemble",
        "shard": 0,
        "shards": 1,
        "vcpus": 2,
        "inputs": {},
        "prior": prior,
        "prior_receipts": pins,
        "analysis": {"bootstrap_replicates": 100, "confidence": 0.95, "seed": 7},
    }
    return context, export


@pytest.mark.parametrize("family", ["battery-v3", "motor", "f02"])
def test_producer_contract_sources_are_bound_and_train_is_public(tmp_path, family):
    context, export = _context(tmp_path, family)
    sources = assemble.load_producer_sources(context)
    assert sources.export == export
    assert sources.train["family"] == family
    assert set(sources.producer_receipts) == {"reference", "train"}
    assert sources.train_jsonl.endswith(b"\n")


def test_missing_or_changed_receipt_refuses_before_assembly(tmp_path):
    context, _ = _context(tmp_path)
    context["prior_receipts"].pop("battery-v3/train/0")
    with pytest.raises(
        assemble.AssemblyRefused, match="EXACT_PRODUCER_STAGE_SET_REQUIRED"
    ):
        assemble.load_producer_sources(context)
    context, _ = _context(tmp_path / "fresh")
    context["prior_receipts"]["battery-v3/train/0"] = "sha256:" + "a" * 64
    with pytest.raises(assemble.AssemblyRefused, match="PRODUCER_RECEIPT_PIN_MISMATCH"):
        assemble.load_producer_sources(context)


def test_missing_chunk_or_unregistered_vcpu_refuses(tmp_path):
    context, _ = _context(tmp_path)
    context["prior"]["battery-v3/reference/0"].pop("reference-records-000")
    with pytest.raises(
        assemble.AssemblyRefused,
        match="PRODUCER_RECEIPT_CONTENT_MISMATCH|PRODUCER_RECORD_CHUNKS_INCOMPLETE",
    ):
        assemble.load_producer_sources(context)
    context, _ = _context(tmp_path / "fresh")
    context["vcpus"] = 1
    with pytest.raises(assemble.AssemblyRefused, match="PRODUCER_SUMMARY_MISMATCH"):
        assemble.load_producer_sources(context)


def test_cross_plan_receipt_and_export_summary_mismatch_refuse(tmp_path):
    context, _ = _context(tmp_path)
    context["plan_digest"] = "sha256:" + "1" * 64
    with pytest.raises(
        assemble.AssemblyRefused, match="PRODUCER_RECEIPT_CONTENT_MISMATCH"
    ):
        assemble.load_producer_sources(context)

    context, _ = _context(tmp_path / "fresh")
    summary = context["prior"]["battery-v3/reference/0"]["stage-summary"]
    path = tmp_path / "fresh/reference/stage-summary.json"
    body = json.loads(path.read_text())
    body["counts"]["export_digest"] = "sha256:" + "2" * 64
    summary["sha256"] = _write(path, body, "ANALYSIS")["sha256"]
    receipt_path = path.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["artifacts"]["stage-summary"]["sha256"] = summary["sha256"]
    context["prior_receipts"]["battery-v3/reference/0"] = _write(
        receipt_path, receipt, "ANALYSIS"
    )["sha256"]
    with pytest.raises(
        assemble.AssemblyRefused, match="PRODUCER_EXPORT_DIGEST_MISMATCH"
    ):
        assemble.load_producer_sources(context)


def test_fixture_assembly_seals_producer_receipts_and_runs_comparison(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _, _ = campaign_fixture(plan_dir)
    context, export = _context(tmp_path / "producer")
    for name in ("manifest", "adaptive_panel"):
        path = plan_dir / "battery-v3" / (name + ".json")
        context["inputs"][name] = {
            "path": str(path),
            "sha256": campaign._sha(path.read_bytes()),
            "role": "SYNTHETIC_FIXTURE",
        }
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    output = tmp_path / "assembled"
    assert assemble.main(["--context", str(context_path), "--output", str(output)]) == 0
    receipt = json.loads((output / "receipt.json").read_text())
    manifest, documents, pins = evidence_pipeline.load(
        output / "manifest.json", receipt["artifacts"]["manifest"]["sha256"]
    )
    assert documents["export"] == export
    assert (
        evidence_pipeline.run(manifest, documents, pins)["value-evidence.json"]["scope"]
        == "DEVELOPMENT"
    )
    bridge = json.loads((output / "comparison_bridge.json").read_text())
    campaign_entrypoints.verify_bridge(
        bridge,
        family="battery-v3",
        scope="SYNTHETIC_FIXTURE",
        manifest_sha256=receipt["artifacts"]["manifest"]["sha256"],
        adaptive_panel_sha256=receipt["artifacts"]["adaptive_panel"]["sha256"],
        export_digest=export["export_digest"],
        producer_receipts=assemble.load_producer_sources(context).producer_receipts,
    )


def test_public_assembly_refuses_without_registered_comparison_builders(tmp_path):
    context, _ = _context(tmp_path)
    context["scope"] = "PUBLIC_DEVELOPMENT"
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    output = tmp_path / "assembled"
    assert assemble.main(["--context", str(context_path), "--output", str(output)]) == 2
    assert not output.exists()
