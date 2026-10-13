"""Synthetic tuples; no real registration or solve authority."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet, panel
from carbon.challenge_pipeline.onboarding import registration as r


def inputs(challenge="f02"):
    draft = packet.generate(
        {
            "schema": packet.SCHEMA,
            "challenge": challenge,
            "buyer": "synthetic buyer",
            "decision": "synthetic decision",
            "physics": "synthetic physics",
            "solver": "synthetic solver",
        },
        Path("."),
    )
    seed = {
        "schema": panel.SCHEMA,
        "challenge": challenge,
        "designs": [
            {"id": "a", "coordinates": {"power_w": 1}},
            {"id": "b", "coordinates": {"power_w": 2}},
        ],
        "strata": [
            {"id": "cold", "inputs": {"temperature_c": 1}},
            {"id": "warm", "inputs": {"temperature_c": 2}},
        ],
        "rungs": [
            {"id": "standard", "settings": {"dt_s": 1}},
            {"id": "refined", "settings": {"dt_s": 0.5}},
        ],
        "pins": {key: "sha256:" + "1" * 64 for key in panel.PIN_KEYS},
        "cost_cpu_seconds": {
            "standard": {"seconds": 120, "basis": "synthetic estimate"},
            "refined": {"seconds": 240, "basis": "synthetic estimate"},
        },
    }
    return draft, seed


def inventory(first):
    return r.seal_inventory(
        {
            "schema": r.INVENTORY,
            "challenge": first["challenge"],
            "scope": "PUBLIC_DEVELOPMENT",
            "source_commit": "1" * 40,
            "as_of_utc": "2026-10-10T19:00:00Z",
            "namespace": "synthetic-complete-namespace",
            "rows": [
                {
                    "identity": t["physical_identity"],
                    "state": state,
                    "receipt": "synthetic independent receipt",
                    "body": t["body"],
                }
                for t, state in zip(first["tuples"][:2], ("COMPLETED", "SCHEDULED"))
            ],
        }
    )


def test_reuses_generator_and_never_counts_unknown_inventory_as_empty():
    draft, seed = inputs()
    first = r.assemble(draft, seed)
    assert first["registration_status"] == "HOLD_INPUTS"
    assert len(first["tuples"]) == 8
    assert first["new_cases"] is None
    assert first["cost"]["cpu_hours_if_reuse_accepted"] is None
    result = r.assemble(draft, seed, inventory(first))
    assert len(result["completed"]) == len(result["scheduled"]) == 1
    assert len(result["new_cases"]) == 6
    assert result["cost"]["cpu_hours_without_reuse"] == pytest.approx(0.4)
    assert result["cost"]["cpu_hours_if_reuse_accepted"] == pytest.approx(0.3)
    assert result["dispatch_authority"] is False and result["adopted"] is False
    assert "NOT_APPROVED" in result["registration_status"]


def test_renamed_design_duplicate_and_changed_observer():
    draft, seed = inputs("cooling-cell")
    first = r.assemble(draft, seed)
    idx = inventory(first)
    seed["designs"].append({"id": "alias", "coordinates": {"power_w": 1}})
    assert len(r.assemble(draft, seed, idx)["tuples"]) == 8
    seed["pins"]["observer"] = "sha256:" + "2" * 64
    changed = r.assemble(draft, seed, idx)
    assert len(changed["new_cases"]) == 8
    seed["pins"]["observer"] = None
    held = r.assemble(draft, seed, idx)
    assert held["new_cases"] is None
    assert all(t["physical_identity"] is None for t in held["tuples"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(scope="HIDDEN_EVAL"),
        lambda x: x["rows"].append(copy.deepcopy(x["rows"][0])),
        lambda x: x["rows"][0]["body"]["inputs"].update(temperature_c=999),
        lambda x: x.update(challenge="motor"),
    ],
)
def test_snapshot_custody_identity_and_conflicts_fail_closed(mutate):
    draft, seed = inputs()
    idx = inventory(r.assemble(draft, seed))
    mutate(idx)
    idx = r.seal_inventory({k: v for k, v in idx.items() if k != "inventory_digest"})
    with pytest.raises(packet.DraftError):
        r.assemble(draft, seed, idx)


def test_cli_byte_identities_and_output_exclusivity(tmp_path):
    draft, seed = inputs()
    idx = inventory(r.assemble(draft, seed))
    args = []
    for name, value in (("packet", draft), ("seed", seed), ("inventory", idx)):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        args.extend(
            [
                "--" + name,
                str(path),
                "--" + name + "-sha256",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    output = tmp_path / "result.json"
    args.extend(["--output", str(output)])
    assert r.main(args) == 0
    saved = output.read_bytes()
    with pytest.raises(FileExistsError):
        r.main(args)
    assert output.read_bytes() == saved
    args[3] = "0" * 64
    with pytest.raises(packet.DraftError):
        r.main(args)
