"""Synthetic campaign stage adapter. It copies toy evidence; it solves nothing."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from carbon.development_comparison import campaign_entrypoints, evidence_pipeline
from carbon.development_comparison import evidence_campaign as campaign


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    context = json.loads(args.context.read_text(encoding="utf-8"))
    if (
        context["schema"] != campaign.SCHEMA + ".stage-context"
        or context["scope"] != "SYNTHETIC_FIXTURE"
    ):
        raise ValueError("fixture-only context required")
    family, phase = context["family"], context["phase"]
    if family not in campaign.FAMILIES or phase not in campaign.PHASES:
        raise ValueError("unsupported fixture stage")
    prior = context["prior"]
    if phase in ("train", "assemble", "score") and not any(
        key.startswith(family + "/reference/") for key in prior
    ):
        raise ValueError("reference shards must precede training")
    if phase in ("assemble", "score") and not any(
        key.startswith(family + "/train/") for key in prior
    ):
        raise ValueError("TRAIN must precede assembly")
    if phase == "train" and (
        not any(
            item["role"] == "PUBLIC_TRAIN"
            for artifacts in prior.values()
            for item in artifacts.values()
        )
        or any(
            item["role"] == "HELDOUT_REFERENCE"
            for artifacts in prior.values()
            for item in artifacts.values()
        )
    ):
        raise ValueError("TRAIN must see public TRAIN and no held-out reference")
    outputs = {}
    if phase == "assemble":
        inputs = context["inputs"]
        if set(inputs) != {"manifest", "adaptive_panel"}:
            raise ValueError("both fixture inputs required")
        source = Path(inputs["manifest"]["path"])
        manifest = json.loads(source.read_text(encoding="utf-8"))
        if manifest["scope"] != "SYNTHETIC_FIXTURE" or manifest["family"] != family:
            raise ValueError("fixture source identity mismatch")
        for descriptor in manifest["files"].values():
            if descriptor is not None:
                relative = campaign._safe_relative(descriptor["path"], "fixture")
                old = source.parent / relative
                evidence_pipeline._read(old, descriptor["sha256"])
                new = args.output / relative
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(old, new)
        shutil.copyfile(source, args.output / "manifest.json")
        shutil.copyfile(
            inputs["adaptive_panel"]["path"], args.output / "adaptive_panel.json"
        )
        export_path = args.output / manifest["files"]["export"]["path"]
        export = json.loads(export_path.read_text(encoding="utf-8"))
        producer_receipts = {
            phase: [
                context["prior_receipts"][key]
                for key in sorted(context["prior_receipts"])
                if key.startswith(f"{family}/{phase}/")
            ]
            for phase in ("reference", "train")
        }
        bridge = campaign_entrypoints.seal_bridge(
            {
                "schema": campaign_entrypoints.BRIDGE_SCHEMA,
                "family": family,
                "scope": "SYNTHETIC_FIXTURE",
                "entrypoint_registration_digest": context[
                    "entrypoint_registration_digest"
                ],
                "producer_receipts": producer_receipts,
                "manifest_sha256": campaign._sha(
                    (args.output / "manifest.json").read_bytes()
                ),
                "adaptive_panel_sha256": campaign._sha(
                    (args.output / "adaptive_panel.json").read_bytes()
                ),
                "export_digest": export["export_digest"],
            }
        )
        (args.output / "comparison_bridge.json").write_text(
            json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for name in ("manifest", "adaptive_panel", "comparison_bridge"):
            target = args.output / (name + ".json")
            outputs[name] = {
                "path": target.name,
                "sha256": campaign._sha(target.read_bytes()),
                "role": "ANALYSIS",
            }
    elif phase == "reference":
        for name, role in (
            ("train_marker", "PUBLIC_TRAIN"),
            ("heldout_marker", "HELDOUT_REFERENCE"),
        ):
            target = args.output / (name + ".json")
            target.write_text(
                json.dumps({"synthetic": True, "family": family, "role": role}) + "\n",
                encoding="utf-8",
            )
            outputs[name] = {
                "path": target.name,
                "sha256": campaign._sha(target.read_bytes()),
                "role": role,
            }
    else:
        target = args.output / "fixture-marker.json"
        target.write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "family": family,
                    "phase": phase,
                    "shard": context["shard"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        outputs["marker"] = {
            "path": target.name,
            "sha256": campaign._sha(target.read_bytes()),
            "role": "SYNTHETIC_FIXTURE",
        }
    receipt = {
        "schema": campaign.STAGE_RESULT,
        "plan_digest": context["plan_digest"],
        "family": family,
        "phase": phase,
        "shard": context["shard"],
        "status": "OK",
        "core_s": 0.001,
        "peak_ram_bytes": 1024,
        "artifacts": outputs,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
