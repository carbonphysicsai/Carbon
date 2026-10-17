"""Direct practice admission binds the same recipe and owner graph as Battery."""

from types import SimpleNamespace

import pytest
from test_battery_direct_practice import _recipe

from carbon.battery.construction_kit import construction_kit
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import staging, submission
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import RunnerAdapter


def _admitted(tmp_path, *, stage=True):
    kit = construction_kit()
    root = tmp_path / "campaign"
    ledger = CampaignLedger(root)
    manifest = {
        "owner": "miner",
        "challenge": {"id": kit["id"], "version": kit["version"]},
        "construction_mode": "direct",
    }
    (root / "campaign-manifest.json").write_bytes(canonical(manifest))
    raw = b'{"documents":{}}'
    if stage:
        ResearchWorkspace(ledger, "miner").put(staging.WORKSPACE_MANIFEST, raw)
    return SimpleNamespace(campaign={"root": str(root)}), _recipe(submission.name(raw))


def test_direct_preflight_uses_owner_workspace_and_registered_kit(tmp_path):
    admitted, strategy = _admitted(tmp_path)
    found = RunnerAdapter._direct_recipe(admitted, strategy)
    assert found.to_dict() == strategy
    assert found.digest.startswith("sha256:")


def test_direct_preflight_refuses_missing_or_changed_source_before_task(tmp_path):
    admitted, strategy = _admitted(tmp_path, stage=False)
    with pytest.raises(Rejected, match="construction_recipe_graph_workspace_missing"):
        RunnerAdapter._direct_recipe(admitted, strategy)
    ResearchWorkspace(CampaignLedger(tmp_path / "campaign"), "miner").put(
        staging.WORKSPACE_MANIFEST,
        b'{"documents":{"forward":"sha256:' + b"0" * 64 + b'"}}',
    )
    with pytest.raises(Rejected, match="construction_recipe_graph_workspace_missing"):
        RunnerAdapter._direct_recipe(admitted, strategy)


def test_direct_preflight_never_falls_back_to_legacy_or_unserved_bundle(tmp_path):
    admitted, strategy = _admitted(tmp_path)
    with pytest.raises(Rejected, match="construction_recipe_malformed"):
        RunnerAdapter._direct_recipe(
            admitted,
            {
                "schema_version": "1.0",
                "challenge_id": strategy["challenge"]["id"],
                "backbone": "mlp",
                "parameters": {},
            },
        )
    bundle = {
        **strategy,
        "source": {
            "kind": "bundle",
            "bundle_ref": {
                "schema": "carbon.library-bundle-ref.v1",
                "bundle_digest": "sha256:" + "a" * 64,
                "language": "python",
                "runtime_profile_id": "fixture-runtime",
                "environment_digest": "sha256:" + "b" * 64,
            },
        },
        "procedure": {
            **strategy["procedure"],
            "entrypoint": {"module": "candidate", "name": "build"},
        },
    }
    with pytest.raises(Rejected, match="construction_reconstruction_unserved"):
        RunnerAdapter._direct_recipe(admitted, bundle)
