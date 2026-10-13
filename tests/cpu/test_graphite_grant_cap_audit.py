"""Public audit and actual pre-transport refusal; no key, network or spend."""

import copy
import hashlib
import json
from decimal import Decimal

import pytest
from graphite_fixtures import brief, provider, spec

from carbon.agent_campaign.graphite import model_providers
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite.model import ScriptedModel, text
from carbon.agent_campaign.graphite.roles import RoleName
from scripts.dev import graphite_grant_cap_audit as audit


def test_current_kimi_cap_reprices_the_full_call_and_reduces_registered_capacity():
    selected = audit.selection(RoleName.CONSTRUCTOR, "kimi-k3")
    assert selected.settings.max_output_tokens == 32768
    assert selected.reservation_nano == 2_364_211_200
    assert audit.capacity(selected, Decimal("10.99"))["calls_at_full_reservation"] == 4
    assert Decimal(selected.reservation_nano) / audit.NANO <= Decimal("10.99")
    # Earlier output cap, same input window and registered pricing.
    previous = model_providers.ENGY.select(
        adapter_id=model_providers.ENGY.default_adapter,
        model_id="kimi-k3",
        credential_reference="/audit/no-credential",
        settings={**selected.settings.record(), "max_output_tokens": 2048},
    )
    assert previous.reservation_nano == 2_064_691_200
    assert audit.capacity(previous, Decimal("10.99"))["calls_at_full_reservation"] == 5
    assert (
        selected.reservation_nano - previous.reservation_nano
        == (32768 - 2048) * selected.pricing.output_nano
    )
    assert not audit.capacity(selected, Decimal("2.10"))["reservation_fits"]
    assert audit.capacity(previous, Decimal("2.10"))["reservation_fits"]


@pytest.mark.parametrize("output_cap,dispatched", [(2048, 1), (32768, 0)])
def test_raised_role_cap_cannot_dispatch_more_than_its_grant_reserves(
    tmp_path, monkeypatch, output_cap, dispatched
):
    # Same 2.10 fixture grant lies between old and current full reservations.
    # Only the cap changes; the real selector, session record and ledger run.
    settings = copy.deepcopy(gp.MODEL_SETTINGS)
    settings[RoleName.CONSTRUCTOR]["kimi-k3"]["max_output_tokens"] = output_cap
    monkeypatch.setattr(gp, "MODEL_SETTINGS", settings)
    model = ScriptedModel([text("Synthetic fixture report.")])
    graphite = provider(
        tmp_path / "graphite", model, grant_changes={"worst_case_run_cost": "2.10"}
    )
    graphite.ladder.start_rungs[RoleName.CONSTRUCTOR] = graphite.ladder.top
    handle = graphite.start(spec(graphite, brief(RoleName.CONSTRUCTOR)), "cap-audit")
    graphite.run(handle.provider_run_id)
    assert len(model.requests) == dispatched
    selected = graphite.session_record(handle.provider_run_id)["model"]
    assert selected["settings"]["max_output_tokens"] == output_cap
    if not dispatched:
        assert graphite.session_record(handle.provider_run_id)["outcome"][
            "failure"
        ] == {
            "code": "run_cap_reached",
            "dimension": "provider_nanodollars",
        }
        usage = graphite.usage(handle.provider_run_id)
        assert usage.settled == usage.pending == Decimal(0)
    else:
        assert model.requests[0]["max_output_tokens"] == output_cap


def test_every_public_grant_is_counted_and_bound_to_its_actual_file_bytes():
    shown = audit.audit()
    paths = sorted((audit.ROOT / "docs/development/graphite/grants").glob("*.json"))
    assert shown["grant_count"] == len(paths) > 0
    assert len(shown["grants"]) == len(paths)
    for row, path in zip(shown["grants"], paths, strict=True):
        assert row["file"] == path.relative_to(audit.ROOT).as_posix()
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["status"] in {
            "MAPPED",
            "REPLACED",
            "NO_INFERENCE",
            "RATE_UNRECORDED",
            "WORKLOAD_UNMAPPED",
            "UNRESOLVED",
        }
    # No inference-provider rate becomes a fabricated zero-cost successful audit.
    spur = [row for row in shown["profiles"] if row["provider"] == "spur"]
    assert len(spur) == 6
    assert all(row["status"] == "RATE_UNRECORDED" and not row["models"] for row in spur)
    assert shown["amount_changes"] == "HUMAN_INPUT"
    assert set(shown["source_sha256"]) == set(audit.SOURCES)
    for path, sha in shown["source_sha256"].items():
        assert sha == hashlib.sha256((audit.ROOT / path).read_bytes()).hexdigest()
    assert "no-credential" not in json.dumps(shown)


def test_no_grants_is_an_error_and_a_new_unmapped_grant_never_reports_mapped(tmp_path):
    with pytest.raises(ValueError, match="public_grant_inventory_empty"):
        audit.audit(tmp_path)
    directory = tmp_path / "docs/development/graphite/grants"
    directory.mkdir(parents=True)
    document = json.loads(
        (
            audit.ROOT / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json"
        ).read_bytes()
    )
    document["grant_id"] = "fixture-unmapped"
    (directory / "unknown.json").write_text(json.dumps(document), encoding="utf-8")
    shown = audit.audit(tmp_path)
    assert shown["grant_count"] == 1
    assert shown["grants"][0]["status"] == "WORKLOAD_UNMAPPED"


def test_missing_owner_amount_stays_unresolved(tmp_path):
    directory = tmp_path / "docs/development/graphite/grants"
    directory.mkdir(parents=True)
    document = json.loads(
        (
            audit.ROOT / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE2.json"
        ).read_bytes()
    )
    document["worst_case_run_cost"] = "HUMAN_INPUT"
    (directory / "missing.json").write_text(json.dumps(document), encoding="utf-8")
    row = audit.audit(tmp_path)["grants"][0]
    assert row["status"] == "UNRESOLVED" and row["reason"] == "grant_value_missing"
    assert "roles" not in row
