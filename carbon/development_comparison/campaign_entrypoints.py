"""Read-only registration bridge to Data Collection's public evidence entrypoints.

This names the merged check/solve/export contracts. It never imports an
entrypoint, checks a Docker engine, invokes a solver, or treats a raw solve
record as a comparison panel. Missing producer and assembly contracts remain
registration gaps for the campaign runner.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "carbon.development-evidence-campaign.entrypoints.v1"
BRIDGE_SCHEMA = "carbon.development-evidence-campaign.comparison-bridge.v1"
ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINTS = {
    "battery-v3": {
        "reference": {
            "module": "scripts.dev.evidence_runs.battery_v3",
            "module_sha256": "d820eca1278bdda7c5c9918d26c960c53cf1315bb0fc2ecfb161f2dd28592d12",
            "kind": "panel-a",
            "plan": "docs/development/evidence/battery-feasibility-02/plans/middle-bands-stage-a-plan.json",
            "plan_sha256": "779076c69a1a22d04d73c1a7c08d9fadddea9c69453ae5daf69fa1e33f275c3c",
            "image_digest": "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940",
            "output_contract": "records.jsonl:carbon.battery.feasibility02-record.v1",
        },
        "train": {
            "module": "scripts.dev.evidence_runs.battery_v3",
            "module_sha256": "d820eca1278bdda7c5c9918d26c960c53cf1315bb0fc2ecfb161f2dd28592d12",
            "kind": "train",
            "plan": "docs/development/evidence/battery-feasibility-02/plans/v3-train-plan.json",
            "plan_sha256": "b42b41f149e317832c5b41d0c533b046ad16962f47416c553c63be8b7bcf60df",
            "image_digest": "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940",
            "output_contract": "export-train:carbon.battery-v3.train-record.v1",
        },
    },
    "motor": {
        "reference": None,  # #1078 registered TRAIN only; Data Collection owns this gap.
        "train": {
            "module": "scripts.dev.evidence_runs.motor_10p12s",
            "module_sha256": "0355eefb28e32859281ab3eb7b6ef5f5c4a5a87a93c5e5463abbb38fdb4964ef",
            "kind": "train-stage1",
            "plan": "docs/development/evidence/motor-feasibility-02/plans/train-stage1-plan.json",
            "plan_sha256": "4a067614ee921d20069504937e3913cebb30226cafe35c489d3a9356a2f4f2cd",
            "image_digest": "sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05",
            "output_contract": "export-train:carbon.motor-10p12s.train-record.v1",
        },
    },
    "f02": {
        "reference": {
            "module": "scripts.dev.evidence_runs.f02",
            "module_sha256": "2d3acb60e1f46ed312170cc6cef8e74cf0a542596bce50b3818a56774627182b",
            "kind": "menu",
            "plan": "docs/development/evidence/reference-packages-01/f02-menu-v2/decks-manifest.json",
            "plan_sha256": "69ae549d7aa12add3ed410dd8534be4a4ab38c40fc578fd43394fa74e62074d7",
            "image_digest": "sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675",
            "output_contract": "ledger.jsonl and cases/ from f02_menu.run",
        },
        "train": {
            "module": "scripts.dev.evidence_runs.f02",
            "module_sha256": "2d3acb60e1f46ed312170cc6cef8e74cf0a542596bce50b3818a56774627182b",
            "kind": "train",
            "plan": "docs/development/evidence/reference-packages-01/f02-menu-v2/train-decks-manifest.json",
            "plan_sha256": "5763d244d15a3a485bf4ad046a0c482f47b698d1051735dcd238d5f907b6d281",
            "image_digest": "sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675",
            "output_contract": "export-train:carbon.f02.train-record.v1",
        },
    },
}


def digest():
    body = {"schema": SCHEMA, "entrypoints": ENTRYPOINTS}
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _digest(body):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                body, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def seal_bridge(body):
    """A trusted assembler binds producer receipts to one comparison export."""
    if type(body) is not dict or set(body) != {
        "schema",
        "family",
        "scope",
        "entrypoint_registration_digest",
        "producer_receipts",
        "manifest_sha256",
        "adaptive_panel_sha256",
        "export_digest",
    }:
        raise ValueError("unsealed comparison bridge required")
    bridge = {**body, "bridge_digest": _digest(body)}
    verify_bridge(
        bridge,
        family=body["family"],
        scope=body["scope"],
        manifest_sha256=body["manifest_sha256"],
        adaptive_panel_sha256=body["adaptive_panel_sha256"],
        export_digest=body["export_digest"],
        producer_receipts=body["producer_receipts"],
    )
    return bridge


def verify_bridge(
    bridge,
    *,
    family,
    scope,
    manifest_sha256,
    adaptive_panel_sha256,
    export_digest,
    producer_receipts,
):
    """Fail closed if any source receipt or comparison identity changes."""
    expected = {
        "schema",
        "family",
        "scope",
        "entrypoint_registration_digest",
        "producer_receipts",
        "manifest_sha256",
        "adaptive_panel_sha256",
        "export_digest",
        "bridge_digest",
    }
    if type(bridge) is not dict or set(bridge) != expected:
        raise ValueError("closed comparison bridge required")
    if (
        bridge["schema"] != BRIDGE_SCHEMA
        or bridge["family"] != family
        or bridge["scope"] != scope
        or bridge["entrypoint_registration_digest"] != digest()
        or bridge["manifest_sha256"] != manifest_sha256
        or bridge["adaptive_panel_sha256"] != adaptive_panel_sha256
        or bridge["export_digest"] != export_digest
        or bridge["producer_receipts"] != producer_receipts
        or type(producer_receipts) is not dict
        or set(producer_receipts) != {"reference", "train"}
    ):
        raise ValueError("comparison bridge identity mismatch")
    for pins in producer_receipts.values():
        if (
            type(pins) is not list
            or not pins
            or any(
                not isinstance(pin, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", pin)
                for pin in pins
            )
        ):
            raise ValueError("producer receipt pins required")
    for value in (manifest_sha256, adaptive_panel_sha256, export_digest):
        if not isinstance(value, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", value
        ):
            raise ValueError("comparison pins required")
    if bridge["bridge_digest"] != _digest(
        {k: v for k, v in bridge.items() if k != "bridge_digest"}
    ):
        raise ValueError("comparison bridge digest mismatch")


def inspect(root=ROOT):
    """Report registered file/plan identities; no image or solver access."""
    root = Path(root)
    result = {}
    for family, phases in ENTRYPOINTS.items():
        result[family] = {}
        for phase, row in phases.items():
            if row is None:
                result[family][phase] = "NOT_REGISTERED"
                continue
            source = root / (row["module"].replace(".", "/") + ".py")
            plan = root / row["plan"]
            if (
                not source.is_file()
                or not plan.is_file()
                or source.is_symlink()
                or plan.is_symlink()
            ):
                result[family][phase] = "FILE_MISSING"
            elif (
                hashlib.sha256(source.read_bytes()).hexdigest() != row["module_sha256"]
            ):
                result[family][phase] = "MODULE_PIN_MISMATCH"
            elif hashlib.sha256(plan.read_bytes()).hexdigest() != row["plan_sha256"]:
                result[family][phase] = "PLAN_PIN_MISMATCH"
            else:
                result[family][phase] = "REGISTERED_FILES_ONLY_IMAGE_NOT_CHECKED"
        result[family]["comparison"] = "ASSEMBLER_NOT_REGISTERED"
    return result
