"""Actual private generation carrier; engineering control, no agent inference."""

import os
from pathlib import Path

from carbon.development_session.research_generation import generate_roles
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.development_session.research_profile import (
    ROLE_ROOTS,
    freeze_roles,
    public_cases,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity


def test_isolated_generation_matches_registered_roles_and_replays_without_redraw(
    tmp_path,
):
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
            **{
                name: "engineering-only"
                for name in (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                    "owner",
                )
            },
        }
    )
    image = load_image_identity(Path(os.environ["CARBON_C03_IMAGE_MANIFEST"]))
    root = generate_roles(ledger, owner="engineering-only", image=image)
    assert len(public_cases(root, "research-train")) == 72
    assert len(public_cases(root, "research-validation")) == 24
    before = {path.name: path.read_bytes() for path in root.glob("*-cases.json")}
    assert generate_roles(ledger, owner="engineering-only", image=image) == root
    assert before == {
        path.name: path.read_bytes() for path in root.glob("*-cases.json")
    }
    # Pure generator check is engineering verification, separate from campaign.
    expected = tmp_path / "expected"
    (expected / "role-roots").mkdir(parents=True)
    for role in ROLE_ROOTS:
        (expected / "role-roots" / (role + ".bin")).write_bytes(
            (root / "role-roots" / (role + ".bin")).read_bytes()
        )
    freeze_roles(expected)
    assert all((expected / name).read_bytes() == body for name, body in before.items())
    used = ledger.status(owner="engineering-only")["used"]
    assert (
        used["provider_attempts"]
        == used["research_trials"]
        == used["reference_invocations"]
        == 0
    )
    assert 0 < used["numerical_milliseconds"] < 120000
