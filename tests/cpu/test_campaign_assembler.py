"""Synthetic documents shaped like #1114's producer stage outputs only."""

import copy
import hashlib
import json

import pytest
from test_evidence_campaign import _fixture as campaign_fixture
from test_evidence_pipeline import bundle

from carbon.development_comparison import campaign_entrypoints, evidence_pipeline
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_campaign as campaign
from carbon.development_comparison.campaign_adapters import assemble, assembly_design


def _write(path, document, role):
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    return {"path": str(path), "sha256": campaign._sha(path.read_bytes()), "role": role}


def _reseal_artifact(context, family, phase, name, transform):
    key = f"{family}/{phase}/0"
    descriptor = context["prior"][key][name]
    from pathlib import Path

    path = Path(descriptor["path"])
    body = json.loads(path.read_text())
    transform(body)
    descriptor["sha256"] = _write(path, body, descriptor["role"])["sha256"]
    receipt_path = path.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["artifacts"][name]["sha256"] = descriptor["sha256"]
    context["prior_receipts"][key] = _write(receipt_path, receipt, "ANALYSIS")["sha256"]


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
            view = copy.deepcopy(export)
            for entry in view["questions"]:
                entry.pop("settled", None)
                for _, _, panel in cb._panels(entry):
                    for item in panel:
                        item["values"] = {
                            q: 0.0
                            for q in item["values"]
                            if not q.startswith("refined.")
                        }
            artifacts["candidate-view"] = _write(
                folder / "candidate-view.json",
                {
                    "schema": "carbon.development-evidence-campaign.producer-candidate-view.v1",
                    "family": family,
                    "export_digest": export["export_digest"],
                    "export": view,
                },
                "PUBLIC_INPUT",
            )
            physical = cb._physical_rows(export)
            ledger = {
                "schema": "carbon.development-evidence-campaign.producer-cost-ledger.v1",
                "family": family,
                "export_digest": export["export_digest"],
                "basis": "synthetic metering",
                "rows": [
                    {
                        "band": r["band"],
                        "candidate": r["candidate"],
                        "condition": r["condition"],
                        "solves": [
                            {
                                "source": "fixture",
                                "rung": "standard",
                                "status": "OK",
                                "wall_s": 2,
                                "core_s": None if family == "battery-v3" else 4,
                            }
                        ],
                        "wall_s": 2,
                        "core_s": None if family == "battery-v3" else 4,
                    }
                    for r in physical
                ],
            }
            artifacts["cost-ledger"] = _write(
                folder / "cost-ledger.json", ledger, "HELDOUT_REFERENCE"
            )
            if family in ("f02", "motor"):
                artifacts["bindings"] = _write(
                    folder / "bindings.json", docs["bindings"], "HELDOUT_REFERENCE"
                )
                artifacts["comparator-materials"] = _write(
                    folder / "comparator-materials.json",
                    docs["comparator"],
                    "HELDOUT_REFERENCE",
                )
            if family == "f02":
                rows = []
                sources = {
                    (r["candidate"], r["condition"]): r["reference_source_sha256"]
                    for r in docs["comparator"]["rows"]
                }
                for item in physical:
                    peak = item["values"]["safety"]
                    rows.append(
                        {
                            "candidate": item["candidate"],
                            "condition": item["condition"],
                            "reference_source_sha256": sources[
                                (item["candidate"], item["condition"])
                            ],
                            "window_start_s": 1.0,
                            "dt_s": 0.02,
                            "top_c": [0.0, peak],
                            "peak_top_c": peak,
                        }
                    )
                name = "comparator-witness-000"
                artifacts[name] = _write(
                    folder / (name + ".json"),
                    {
                        "schema": "carbon.development-evidence-campaign.producer-f02-witness.v1",
                        "family": family,
                        "export_digest": export["export_digest"],
                        "chunk": 0,
                        "rows": rows,
                    },
                    "HELDOUT_REFERENCE",
                )
                artifacts["comparator-witness-manifest"] = _write(
                    folder / "comparator-witness-manifest.json",
                    {
                        "schema": "carbon.development-evidence-campaign.producer-f02-witness-manifest.v1",
                        "family": family,
                        "export_digest": export["export_digest"],
                        "chunks": [
                            {
                                "order": 0,
                                "name": name + ".json",
                                "sha256": artifacts[name]["sha256"][7:],
                            }
                        ],
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
            receipt = {
                "schema": "synthetic-model-receipt",
                "scope": "SYNTHETIC_FIXTURE",
                "export_digest": export["export_digest"],
                "model_id": "toy-carbon",
                "train": {"sha256": "sha256:" + train["jsonl_sha256"]},
                "cost": {
                    "fit": {"fit_wall_s": 0.1, "fit_cpu_s": 0.1},
                    "inference": {"wall_s": 0.1, "cpu_s": 0.1},
                },
            }
            artifacts["carbon-receipt"] = _write(
                folder / "carbon-receipt.json", receipt, "MODEL"
            )
            predictions = copy.deepcopy(docs["carbon"])
            predictions["source_receipt_digest"] = (
                "sha256:"
                + hashlib.sha256(
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            )
            artifacts["carbon-predictions"] = _write(
                folder / "carbon-predictions.json", predictions, "MODEL"
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


def test_candidate_view_leak_and_model_receipt_substitution_refuse(tmp_path):
    context, _ = _context(tmp_path / "view")

    def leak(view):
        view["export"]["questions"][0]["reference"][0]["panel"][0]["values"][
            "minutes"
        ] = 123.0

    _reseal_artifact(context, "battery-v3", "reference", "candidate-view", leak)
    with pytest.raises(assemble.AssemblyRefused, match="CANDIDATE_VIEW_LEAK"):
        assemble.load_producer_sources(context)

    context, _ = _context(tmp_path / "model")
    _reseal_artifact(
        context,
        "battery-v3",
        "train",
        "carbon-receipt",
        lambda receipt: receipt.__setitem__("model_id", "substituted"),
    )
    with pytest.raises(
        assemble.AssemblyRefused, match="CARBON_RECEIPT_OR_TRAIN_IDENTITY"
    ):
        assemble.load_producer_sources(context)


def test_f02_witness_chunk_order_is_digest_bound(tmp_path):
    context, _ = _context(tmp_path, "f02")
    _reseal_artifact(
        context,
        "f02",
        "reference",
        "comparator-witness-manifest",
        lambda manifest: manifest["chunks"][0].__setitem__("order", 1),
    )
    with pytest.raises(
        assemble.AssemblyRefused, match="F02_WITNESS_MANIFEST_PIN_MISMATCH"
    ):
        assemble.load_producer_sources(context)


@pytest.mark.parametrize("family", ["battery-v3", "motor", "f02"])
def test_comparison_design_uses_registered_producer_artifacts(tmp_path, family):
    context, _ = _context(tmp_path, family)
    sources = assemble.load_producer_sources(context)
    ledger = assemble._read(
        sources.reference_artifacts["cost-ledger"], "HELDOUT_REFERENCE"
    )
    predictions = assemble._read(sources.train_artifacts["carbon-predictions"], "MODEL")
    receipt = assemble._read(sources.train_artifacts["carbon-receipt"], "MODEL")
    comparator = assemble._comparator_materials(sources)
    bindings = (
        assemble._read(sources.reference_artifacts["bindings"], "HELDOUT_REFERENCE")
        if family != "battery-v3"
        else None
    )
    replay, bound = assembly_design.build(
        sources.export, ledger, predictions, receipt, comparator, bindings
    )
    assert replay["source_digest"] == sources.export["export_digest"]
    assert (
        replay["registrations"]["cost_plan"]
        == assembly_design.registration(family).registration_id
    )
    assert len(bound["jobs"]) == len(sources.export["questions"])
    if family == "battery-v3":
        assert all(
            set(action) == {"5", "15", "25", "35", "40"}
            for action in bound["jobs"][0]["candidates"].values()
        )
        assert (
            replay["cost_basis"] == "ASSUMPTION"
        )  # one-core wall upper bound, not metered CPU
    else:
        assert replay["cost_basis"] == "MEASURED"
    value = assembly_design.value_context(sources.export, predictions)
    assert (
        value["selection"]["selection_receipt_digest"]
        == predictions["source_receipt_digest"]
    )
    assert (
        value["speed"] is None
    )  # the producer measured one batched inference, not per-query latency
    results = evidence_pipeline.run(
        {
            "schema": evidence_pipeline.SCHEMA,
            "scope": "SYNTHETIC_FIXTURE",
            "family": family,
            "method": assembly_design.METHODS[family],
            "files": {},
            "analysis": context["analysis"],
        },
        {
            "export": sources.export,
            "comparator": comparator,
            "carbon": predictions,
            "replay": replay,
            "bindings": bound,
            "context": value,
            "rule": None,
        },
        {"export": sources.export["export_digest"]},
    )
    assert results["value-report.json"]["fixture_only"] is True
    registered = assemble.registered_design(context, sources)
    assert registered["replay"]["source_digest"] == replay["source_digest"]
    assert registered["replay"]["budgets"] == replay["budgets"]
    assert registered["bindings"] == bound
    assert registered["rule"]["rule_id"].startswith("VALUE-BAR-V1:")


def test_value_folds_require_distinct_registered_support_clusters():
    export = {
        "family": "f02",
        "export_digest": "sha256:" + "a" * 64,
        "questions": [
            {"case": "a", "support_case": "bank-a"},
            {"case": "a2", "support_case": "bank-a"},
            {"case": "b", "support_case": "bank-b"},
        ],
    }
    model = {"model_id": "fixture-model", "source_receipt_digest": "sha256:" + "b" * 64}
    folds = assembly_design.value_context(export, model)["folds"]["folds"]
    assert {q for row in folds for q in row["questions"]} == {"a", "a2", "b"}
    assert folds[0]["source_digest"] != folds[1]["source_digest"]
    export["questions"][2]["support_case"] = "bank-a"
    assert assembly_design.value_context(export, model)["folds"] is None


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


@pytest.mark.parametrize(
    "family,reason",
    [
        ("battery-v3", "MEASURED_COMPLETE_PANEL_CPU_COST_REQUIRED"),
        ("f02", "PRE_EXPERIMENT_ADAPTIVE_POLICY_RECEIPT_REQUIRED"),
        ("motor", "PRE_EXPERIMENT_ADAPTIVE_POLICY_RECEIPT_REQUIRED"),
    ],
)
def test_registered_assembly_keeps_real_adaptive_panel_closed(
    tmp_path, family, reason
):
    context, _ = _context(tmp_path, family)
    sources = assemble.load_producer_sources(context)
    output = tmp_path / "public-assembly"
    with pytest.raises(assemble.AssemblyRefused, match=reason):
        assemble.assemble_registered(context, sources, output)
    assert not output.exists()
