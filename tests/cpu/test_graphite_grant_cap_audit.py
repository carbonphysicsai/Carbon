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


def _assert_snapshot_matches_current(shown):
    # Retain the complete current-source regeneration control.
    assert shown == audit.audit()


def test_historical_v1_v2_v3_snapshots_preserve_their_source_bindings():
    directory = audit.ROOT / "docs/development/evidence/role-output-cap-audit"
    previous_bytes = (directory / "audit-v1.json").read_bytes()
    previous = json.loads(previous_bytes)
    second_bytes = (directory / "audit-v2.json").read_bytes()
    second = json.loads(second_bytes)
    third_bytes = (directory / "audit-v3.json").read_bytes()
    current = json.loads(third_bytes)
    assert hashlib.sha256(third_bytes).hexdigest() == (
        "53124307c91faa286099b808a73ac73762499e574439505b79837a3cb87a7b95"
    )
    assert hashlib.sha256(previous_bytes).hexdigest() == (
        "d799faa3d25b592e1109e62f63835e9e8945716f9d8cc24995051bb459584916"
    )
    assert previous["grant_count"] == 33
    assert hashlib.sha256(second_bytes).hexdigest() == (
        "2de048c86dd2dfb8bb1cfb8c3cd4a33fdfc143fee1a96e66774a77a8a5d3a8cc"
    )
    assert second["snapshot_version"] == 2
    assert second["source_revision"] == ("e13f973a0da7b887bcbf28796ca895fc7e697451")
    assert second["supersedes"] == {
        "path": "docs/development/evidence/role-output-cap-audit/audit-v1.json",
        "sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "grant_count": 33,
    }
    assert current.pop("snapshot_version") == 3
    assert current.pop("source_revision") == (
        "b94fb52a08c78055fd2fc0e642d0e883f52b8464"
    )
    assert current.pop("supersedes") == {
        "path": "docs/development/evidence/role-output-cap-audit/audit-v2.json",
        "sha256": hashlib.sha256(second_bytes).hexdigest(),
        "grant_count": 34,
    }
    # V3 remains the historical 34-grant target-binding source refresh.
    # The prospective v4 control below binds the current 35-grant inventory.
    assert current["grants"] == second["grants"]
    assert current["profiles"] == second["profiles"]
    assert current["grant_count"] == 34
    old_id = "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-5"
    new_id = "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-6"
    historical_rows = {row["grant_id"]: row for row in previous["grants"]}
    rows = {row["grant_id"]: row for row in current["grants"]}
    assert historical_rows[old_id]["status"] == "MAPPED"
    assert historical_rows[old_id]["replaced_by"] is None
    assert new_id not in historical_rows
    assert rows[old_id]["status"] == "REPLACED"
    assert rows[old_id]["replaced_by"] == new_id
    assert rows[new_id]["status"] == "MAPPED"
    assert rows[new_id]["replaced_by"] is None


def test_v4_binds_the_named_qwen_grant_and_preserves_the_prior_snapshot():
    directory = audit.ROOT / "docs/development/evidence/role-output-cap-audit"
    previous_bytes = (directory / "audit-v3.json").read_bytes()
    previous = json.loads(previous_bytes)
    current_bytes = (directory / "audit-v4.json").read_bytes()
    current = json.loads(current_bytes)
    # V4 is historical: v5 below re-pins model_provider.py prospectively.
    assert hashlib.sha256(current_bytes).hexdigest() == (
        "a868929497e989ba0a53431bfd7e0061b76b3377d34538b4316a36f477691ccf"
    )
    assert current.pop("snapshot_version") == 4
    assert current.pop("source_revision") == (
        "09c03aeea4b681fb532235407c070387a48c4ae1"
    )
    assert current.pop("supersedes") == {
        "path": "docs/development/evidence/role-output-cap-audit/audit-v3.json",
        "sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "grant_count": 34,
    }
    assert current["grant_count"] == 35
    qwen_id = "GRAPHITE-GRANT-MODEL-QWEN-CONSTRUCTOR-1"
    qwen = [row for row in current["grants"] if row["grant_id"] == qwen_id]
    assert len(qwen) == 1 and qwen[0]["status"] == "MAPPED"
    assert qwen[0]["monetary_ceiling_usd"] == "14.94"
    assert qwen[0]["worst_case_run_cost_usd"] == "14.91"
    assert qwen[0]["permitted_runs"] == 1
    assert {row["grant_id"] for row in previous["grants"]}.isdisjoint({qwen_id})
    assert [row for row in current["grants"] if row["grant_id"] != qwen_id] == (
        previous["grants"]
    )
    assert current["profiles"] == previous["profiles"]
    changed_sources = {
        path
        for path, value in current["source_sha256"].items()
        if value != previous["source_sha256"][path]
    }
    # phase3.py: the 09c03aeea import and call-site redirect to
    # level4_lowering, no logic and no grant figure changed.
    assert changed_sources == {
        "carbon/agent_campaign/graphite/grant_binding.py",
        "carbon/agent_campaign/graphite/phase3.py",
    }


def test_v5_rebinds_the_provider_source_and_preserves_the_prior_snapshot():
    directory = audit.ROOT / "docs/development/evidence/role-output-cap-audit"
    previous_bytes = (directory / "audit-v4.json").read_bytes()
    previous = json.loads(previous_bytes)
    current_bytes = (directory / "audit-v5.json").read_bytes()
    current = json.loads(current_bytes)
    # V5 is historical: v6 below re-pins model_provider.py after S17.
    assert hashlib.sha256(current_bytes).hexdigest() == (
        "bdee338a3bf7a3479688dfb1491278501b0e119669ba58bcdff52236d99cc1c1"
    )
    assert current.pop("snapshot_version") == 5
    assert current.pop("source_revision") == (
        "d5046aae7cc0bea529d015d5548d9a00b744392c"
    )
    assert current.pop("supersedes") == {
        "path": "docs/development/evidence/role-output-cap-audit/audit-v4.json",
        "sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "grant_count": 35,
    }
    assert current["grant_count"] == 35
    assert current["grants"] == previous["grants"]
    assert current["profiles"] == previous["profiles"]
    changed_sources = {
        path
        for path, value in current["source_sha256"].items()
        if value != previous["source_sha256"][path]
    }
    # model_provider.py: the Launchpad published-limit and timeout defaults
    # (661e042db, 692107229, 9e8d4ff86, d5046aae7); no grant, price, cap or
    # capacity row changed.
    assert changed_sources == {"carbon/development_session/model_provider.py"}


def test_v6_rebinds_the_streamed_provider_source_and_preserves_v5():
    directory = audit.ROOT / "docs/development/evidence/role-output-cap-audit"
    previous_bytes = (directory / "audit-v5.json").read_bytes()
    previous = json.loads(previous_bytes)
    current = json.loads((directory / "audit-v6.json").read_bytes())
    assert current.pop("snapshot_version") == 6
    assert current.pop("source_revision") == (
        "356df4481cb7fbf2a6fec62b26d585e0b1e06ffb"
    )
    assert current.pop("supersedes") == {
        "path": "docs/development/evidence/role-output-cap-audit/audit-v5.json",
        "sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "grant_count": 35,
    }
    # Keep exact current-source regeneration: every public file hash, source
    # pin, registered selection and capacity must match the real audit.
    _assert_snapshot_matches_current(current)
    assert current["grant_count"] == 35
    assert current["grants"] == previous["grants"]
    assert current["profiles"] == previous["profiles"]
    changed_sources = {
        path
        for path, value in current["source_sha256"].items()
        if value != previous["source_sha256"][path]
    }
    # model_provider.py: the S17 stream transport (062e3aa96) merged with the
    # published-limit defaults; no grant, price, cap or capacity row changed.
    assert changed_sources == {"carbon/development_session/model_provider.py"}


@pytest.mark.parametrize(
    "name", ["audit-v2.json", "audit-v3.json", "audit-v4.json", "audit-v5.json"]
)
def test_historical_source_pins_cannot_pass_current_regeneration_control(name):
    directory = audit.ROOT / "docs/development/evidence/role-output-cap-audit"
    stale = json.loads((directory / name).read_bytes())
    for field in ("snapshot_version", "source_revision", "supersedes"):
        stale.pop(field)
    with pytest.raises(AssertionError):
        _assert_snapshot_matches_current(stale)
