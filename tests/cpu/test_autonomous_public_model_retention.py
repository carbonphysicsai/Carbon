"""Prospective own-agent public practice retention, with a fixture carrier only."""

import io
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.battery import public_model_retention as retention
from carbon.battery import recipes
from carbon.battery.practice import PROGRAM
from carbon.development_session.profile import canonical, digest
from test_graphite_public_model_retention import (
    IMAGE,
    STRATEGY,
    practice_fixture,
    public_stage,
)


REVISION = "a" * 40


def opt_in():
    return {
        "schema": retention.AUTONOMOUS_OPT_IN_SCHEMA,
        "campaign_id": "cmp-battery-julia",
        "scope": "PUBLIC_AUTONOMOUS_TEST",
        "program_version": retention.AUTONOMOUS_PROGRAM_VERSION,
        "source_commit": REVISION,
    }


def owner_opt_in():
    return {
        **opt_in(),
        "schema": retention.OWNER_OPT_IN_SCHEMA,
        "scope": "PUBLIC_OWNER_DRIVEN_TEST",
        "program_version": retention.OWNER_PROGRAM_VERSION,
    }


def manifest():
    return {
        "campaign_id": "cmp-battery-julia",
        "owner": "miner-requester",
        "agent": "autonomous",
        "provider": {"agent": "autonomous"},
        "challenge": {"id": retention.CHALLENGE},
        "implementation": {"revision": REVISION},
        "public_model_retention": opt_in(),
    }


def test_normal_owner_launch_freezes_distinct_opt_in(tmp_path, monkeypatch):
    from carbon.battery import campaign, research
    from test_battery_research_images import IMAGES, launch, runtime

    marker = tmp_path / retention.OPT_IN_FILE
    marker.write_bytes(canonical(owner_opt_in()))
    selected = retention.launch_opt_in(
        tmp_path, campaign_id="cmp-battery-julia", agent="none"
    )
    document = campaign.manifest_document(
        launch(runtime()),
        owner="miner-requester",
        implementation={"revision": REVISION},
        images=list(IMAGES),
        **selected,
    )
    assert document["agent"] == "none"
    assert retention.frozen_opt_in(document, owner="miner-requester") == owner_opt_in()
    (tmp_path / "campaign-manifest.json").write_bytes(canonical(document))
    seen = []

    class Captured(Exception):
        pass

    def capture(**kwargs):
        seen.append(kwargs)
        raise Captured

    monkeypatch.setattr(research, "BatteryPractice", capture)
    with pytest.raises(Captured):
        campaign.compose(
            ledger=SimpleNamespace(root=tmp_path),
            owner="miner-requester",
            image=None,
            analysis=None,
            connection=None,
        )
    assert seen[-1]["model_retention"] == owner_opt_in()
    for agent in ("graphite", "autonomous"):
        with pytest.raises(ValueError):
            retention.launch_opt_in(
                tmp_path, campaign_id="cmp-battery-julia", agent=agent
            )
    with pytest.raises(ValueError, match="revision"):
        campaign.manifest_document(
            launch(runtime()),
            owner="miner-requester",
            implementation={"revision": "b" * 40},
            images=list(IMAGES),
            **selected,
        )
    marker.unlink()
    assert retention.launch_opt_in(
        tmp_path, campaign_id="cmp-battery-julia", agent="none"
    ) == {}


def test_normal_owner_practice_retains_model(tmp_path):
    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = owner_opt_in()
    practice("normal-owner-trial", STRATEGY)
    row = retention.inventory(ledger, owner="miner-requester")[0]
    assert row["schema"] == retention.OWNER_INVENTORY_SCHEMA
    assert row["state"]["status"] == "RETAINED"
    assert row["artifact_provenance"]["schema"] == retention.OWNER_ARTIFACT_SCHEMA


def test_autonomous_opt_in_is_explicit_frozen_and_revision_bound(tmp_path):
    path = tmp_path / retention.OPT_IN_FILE
    assert retention.launch_opt_in(
        tmp_path, campaign_id="cmp-battery-julia", agent="autonomous"
    ) == {}
    path.write_bytes(canonical(opt_in()))
    assert retention.launch_opt_in(
        tmp_path, campaign_id="cmp-battery-julia", agent="autonomous"
    ) == {"public_model_retention": opt_in()}
    assert retention.frozen_opt_in(manifest(), owner="miner-requester") == opt_in()
    for changed in (
        {"agent": "graphite", "provider": {"agent": "graphite"}},
        {"implementation": {"revision": "b" * 40}},
        {"challenge": {"id": "another"}},
        {"owner": "another"},
    ):
        with pytest.raises(ValueError):
            retention.frozen_opt_in({**manifest(), **changed}, owner="miner-requester")
    for changed in ({"scope": "PRIVATE"}, {"program_version": "future"},
                    {"destination": "https://example.invalid"}):
        path.write_bytes(canonical({**opt_in(), **changed}))
        with pytest.raises(ValueError):
            retention.launch_opt_in(
                tmp_path, campaign_id="cmp-battery-julia", agent="autonomous"
            )


def test_autonomous_writer_versions_without_changing_graphite(public_stage):
    own, files, provenance = retention.retained_program(
        PROGRAM, public_stage, opt_in=opt_in(), identity="own-trial", image=IMAGE
    )
    graphite_opt = {
        **opt_in(), "schema": retention.OPT_IN_SCHEMA,
        "scope": "PUBLIC_GRAPHITE_TEST", "program_version": retention.PROGRAM_VERSION,
    }
    graphite, _, _ = retention.retained_program(
        PROGRAM, public_stage, opt_in=graphite_opt, identity="own-trial", image=IMAGE
    )
    assert retention.AUTONOMOUS_ARTIFACT_SCHEMA in own
    assert retention.GRAPHITE_ARTIFACT_SCHEMA in graphite
    assert own != graphite
    assert provenance["program_version"] == retention.AUTONOMOUS_PROGRAM_VERSION
    assert provenance["staged"]["practice-inputs.json"] == digest(
        public_stage["practice-inputs.json"]
    )
    assert files[retention.STAGED_FILE] == canonical(provenance)
    compile(own, "retained-own-practice", "exec")


def test_autonomous_trial_retains_native_state_and_bound_sidecar(tmp_path):
    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = opt_in()
    result = practice("own-trial", STRATEGY)
    row = retention.inventory(ledger, owner="miner-requester")[0]
    assert retention.inventory(ledger, owner="another-miner") == []
    assert row["schema"] == retention.AUTONOMOUS_INVENTORY_SCHEMA
    assert row["status"] == "COMPLETED"
    assert row["state"]["status"] == "RETAINED"
    assert row["official_eligible"] is False
    body = (ledger.root / row["state"]["path"]).read_bytes()
    assert 0 < len(body) <= retention.MAX_STATE_BYTES
    assert digest(body) == row["state"]["sha256"]
    sidecar = row["artifact_provenance"]
    assert sidecar["schema"] == retention.AUTONOMOUS_ARTIFACT_SCHEMA
    assert sidecar["opt_in"]["source_commit"] == REVISION
    assert sidecar["image"] == IMAGE
    assert sidecar["files"]["fit.json"] == row["artifacts"]["fit.json"]["sha256"]
    assert sidecar["files"]["predictions.json"] == row["artifacts"][
        "predictions.json"
    ]["sha256"]
    assert sidecar["state"]["sha256"] == digest(body)
    assert sidecar["recipe_digest"] == result["recipe_digest"]
    assert recipes.model_from_bytes(body).predict(np.zeros((1, 4))) is not None


def test_native_state_decoder_rejects_object_pickle_payload():
    buffer = io.BytesIO()
    np.savez(buffer, __header__=np.frombuffer(b"{}", dtype=np.uint8),
             object_payload=np.asarray([object()], dtype=object))
    with pytest.raises(ValueError, match="Object arrays cannot be loaded"):
        recipes.model_from_bytes(buffer.getvalue())


def test_autonomous_failure_records_missing_state(tmp_path):
    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = opt_in()
    with pytest.raises(ValueError):
        practice("refused", {**STRATEGY, "backbone": "unknown"})
    row = retention.inventory(ledger, owner="miner-requester")[0]
    assert row["schema"] == retention.AUTONOMOUS_INVENTORY_SCHEMA
    assert row["status"] == "FAILED"
    assert row["state"] == {"status": "NOT_RETAINED"}
