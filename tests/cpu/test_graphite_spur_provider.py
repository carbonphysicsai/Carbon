"""SPUR Compute as Graphite's second model provider (GRAPHITE-SPUR-PROVIDER-01).

The same assertions run for Engy and SPUR wherever the two share a path:
selection, reservation, settlement, admission, the deadline and the
transport. SPUR ships with no recorded rate, so where a test needs a
callable SPUR model it records a synthetic fixture rate on a copy of the
provider (`with_recorded`); that rate is not SPUR's and never leaves the test.
No network, no real key, no grant file.
"""

from __future__ import annotations

import io
import json
import os
import types
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import grant_binding, model_providers, phase3
from carbon.agent_campaign.graphite.ladder import LADDER, Ladder, LadderError
from carbon.agent_campaign.graphite.model import (
    LiveModel,
    ModelAccessRefused,
    ScriptedModel,
)
from carbon.agent_campaign.graphite.model_providers import ENGY, SPUR, identity
from carbon.agent_campaign.graphite.phase4 import owner_only_file
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.development_session import model_provider as mp
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import settled_charge
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from scripts.dev.miner_launchpad import capabilities, runner
from tests.cpu.graphite_fixtures import (
    grant,
    provider,
    reader_script,
    started,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
READER = ROLES[RoleName.READER]
MODEL = READER.start_model
#: A synthetic fixture rate: deliberately Engy's own numbers for the same
#: model name, so only the provider tells the two apart. Not a SPUR rate.
FIXTURE_RATE = mp.Pricing(
    input_nano=ENGY.rates[MODEL].input_nano,
    cached_input_nano=ENGY.rates[MODEL].cached_input_nano,
    output_nano=ENGY.rates[MODEL].output_nano,
    source="declared_list",
    reference="test fixture; not a SPUR rate",
    observed="2026-10-06",
    note="synthetic",
)
SPUR_FIXTURE = SPUR.with_recorded({MODEL: FIXTURE_RATE}, {})
PROVIDERS = {"engy": ENGY, "spur": SPUR_FIXTURE}
CHAT_ADAPTER = {"engy": "engy-chat", "spur": "spur-chat"}

#: The Launchpad's provider choices on main before this change.
MAIN_ADAPTER_IDS = (
    "openai-responses",
    "engy-anthropic",
    "engy-chat",
    "chutes",
    "anthropic",
    "openai-compatible-responses",
    "openai-compatible-chat",
)
MAIN_SUMMARY_DIGEST = (
    "sha256:4831a272e6d0bcf41012d6fd9b18f842345037a01de0b0e0c99bc7c48bd2c0bd"
)
MAIN_CHOICES_DIGEST = (
    "sha256:c1e4a37b1019b0555a01542f34ea78cd1e523bf2136f5b3175d1105feac02bb2"
)


@pytest.fixture
def bound(monkeypatch):
    """The test grant bound to SPUR, as an owner's binding would be."""
    monkeypatch.setattr(
        grant_binding,
        "MODEL_PROVIDER_GRANTS",
        types.MappingProxyType({"graphite-test-grant": "spur"}),
    )


def _bound_to(name, monkeypatch):
    if name == "spur":
        monkeypatch.setattr(
            grant_binding,
            "MODEL_PROVIDER_GRANTS",
            types.MappingProxyType({"graphite-test-grant": "spur"}),
        )


# -- identity -------------------------------------------------------------------------------
def test_same_name_models_are_separate_provider_model_identities():
    assert MODEL in ENGY.rates and MODEL in SPUR_FIXTURE.rates
    assert identity("engy", MODEL) == "engy:" + MODEL
    assert identity("spur", MODEL) == "spur:" + MODEL
    assert identity("engy", MODEL) != identity("spur", MODEL)
    engy = ENGY.select(adapter_id="engy-chat", model_id=MODEL, credential_reference="k")
    spur = SPUR_FIXTURE.select(
        adapter_id="spur-chat", model_id=MODEL, credential_reference="k"
    )
    # Same model name, same fixture numbers: still two run conditions.
    assert engy.model_id == spur.model_id
    assert engy.record() != spur.record()
    assert engy.record()["provider_id"] != spur.record()["provider_id"]
    assert ENGY.record(MODEL) != SPUR_FIXTURE.record(MODEL)
    # Neither provider's admission takes the other's selection.
    assert ENGY.admission_refusal(spur) == "engy_adapter_required"
    assert SPUR_FIXTURE.admission_refusal(engy) == "spur_adapter_required"
    # SPUR's glm-5.2 never borrows Engy's recorded context or ladder store.
    whole = RoleName.CONSTRUCTOR
    assert ENGY.model_settings[whole]["glm-5.2"]
    assert "glm-5.2" not in SPUR_FIXTURE.model_settings[whole]
    assert ENGY.ladder_directory != SPUR.ladder_directory


def test_a_spur_session_records_its_provider_and_an_engy_session_records_nothing(
    tmp_path, bound
):
    # The Engy run has its own grant: the test grant is bound to SPUR here.
    engy, engy_run = started(
        tmp_path / "engy", grant_changes={"grant_id": "graphite-engy-grant"}
    )
    spur, spur_run = started(
        tmp_path / "spur",
        ScriptedModel(reader_script(), model_provider=SPUR_FIXTURE),
        model_provider=SPUR_FIXTURE,
    )
    engy_opened, spur_opened = engy._opened(engy_run), spur._opened(spur_run)
    assert "model_provider" not in engy_opened
    assert spur_opened["model_provider"] == {
        "schema": model_providers.MODEL_PROVIDER_SCHEMA,
        "provider": "spur",
        "identity": "spur:" + MODEL,
    }
    assert spur_opened["model"]["provider_id"] == "spur-chat"
    assert engy_opened["model"]["provider_id"] == "engy-anthropic"
    assert engy_opened["role"]["model"] == spur_opened["role"]["model"] == MODEL


# -- pricing: an empty table, refused typed --------------------------------------------------
def test_spur_ships_no_rate_and_no_context():
    assert model_providers.SPUR_RATES == {}
    assert model_providers.SPUR_CONTEXT_TOKENS == {}
    assert SPUR.ladder == ()
    assert SPUR.rate_refusal("glm-5.2") == "spur_rate_unrecorded"
    with pytest.raises(ValueError, match="spur_rate_unrecorded"):
        SPUR.select(
            adapter_id="spur-chat", model_id="glm-5.2", credential_reference="k"
        )


def test_an_unrecorded_spur_rate_refuses_before_any_reservation_or_call(
    tmp_path, bound
):
    model = ScriptedModel(reader_script(), model_provider="spur")
    graphite = provider(tmp_path / "g", model, model_provider="spur")
    with pytest.raises(ProviderUnavailable, match="spur_rate_unrecorded"):
        started(tmp_path / "g", model, model_provider="spur")
    assert model.requests == []
    assert not any((graphite.root / "runs").iterdir())


# -- spend: the grant must name the provider --------------------------------------------------
@pytest.mark.parametrize("name", ["engy", "spur"])
def test_a_run_refuses_a_grant_that_does_not_name_its_provider(
    tmp_path, monkeypatch, name
):
    other = "spur" if name == "engy" else "engy"
    monkeypatch.setattr(
        grant_binding,
        "MODEL_PROVIDER_GRANTS",
        types.MappingProxyType(
            {} if other == "engy" else {"graphite-test-grant": "spur"}
        ),
    )
    chosen = PROVIDERS[name]
    with pytest.raises(ProviderUnavailable, match=grant_binding.MODEL_PROVIDER_REFUSED):
        provider(tmp_path / "g", model_provider=chosen)
    with pytest.raises(ModelAccessRefused) as refused:
        LiveModel(
            grant=grant(),
            credential_file="/nonexistent/key",
            provider="graphite",
            model_provider=chosen,
        )
    assert refused.value.code == grant_binding.MODEL_PROVIDER_REFUSED


def test_no_committed_grant_names_spur():
    assert dict(grant_binding.MODEL_PROVIDER_GRANTS) == {}
    for path in sorted(GRANTS.glob("*.json")):
        named = types.SimpleNamespace(grant_id=json.loads(path.read_text())["grant_id"])
        assert grant_binding.model_provider_of(named) == "engy"
        assert grant_binding.model_provider_refusal(named, "engy") is None
        assert (
            grant_binding.model_provider_refusal(named, "spur")
            == grant_binding.MODEL_PROVIDER_REFUSED
        )


def test_the_phase3_runner_refuses_spur_before_anything_opens(tmp_path, capsys):
    root = tmp_path / "root"
    argv = [
        "run",
        "--root",
        str(root),
        "--challenge",
        BATTERY_CHALLENGE,
        "--grant",
        str(GRANTS / "GRAPHITE-GRANT-PHASE3-R2.json"),
        "--credential-file",
        str(tmp_path / "never-read"),
        "--runpod-key-env",
        "RUNPOD_API_KEY",
        "--code-ref",
        "0" * 40,
        "--model-provider",
        "spur",
    ]
    with pytest.raises(SystemExit):
        phase3.main(argv)
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(last)["reason_code"] == grant_binding.MODEL_PROVIDER_REFUSED
    assert not root.exists() or not any(root.iterdir())


# -- one path for both: reservation, settlement, admission, deadline, transport ------------
@pytest.mark.parametrize("name", ["engy", "spur"])
def test_reservation_and_settlement_follow_one_rule(name):
    chosen = PROVIDERS[name]
    selection = chosen.select(
        adapter_id=CHAT_ADAPTER[name], model_id=MODEL, credential_reference="k"
    )
    rate, settings = chosen.rates[MODEL], selection.settings
    assert selection.reservation_nano == (
        settings.max_input_tokens * rate.input_nano
        + settings.max_output_tokens * rate.output_nano
    )
    assert selection.pricing == rate
    assert chosen.admission_refusal(selection) is None
    usage = {"nanodollars": 1234, "billing_basis": "metered"}
    # No charge report: the full reservation is booked, never the estimate.
    missing = settled_charge(usage, mp.provider_report({}, selection), selection)
    assert missing["nanodollars"] == selection.reservation_nano
    assert missing["basis"] == "provider charge not reported; full reservation retained"
    assert missing["estimated_nanodollars"] == 1234
    # A reported charge settles the call where the provider reports one.
    reply = {"x_engy": {"charged_micro": 7}}
    reported = settled_charge(usage, mp.provider_report(reply, selection), selection)
    if name == "engy":
        assert reported["nanodollars"] == 7000
    else:
        # SPUR documents no charge report, so nothing in a reply is read.
        assert reported == missing


@pytest.mark.parametrize("name", ["engy", "spur"])
def test_a_whole_session_runs_the_same_way_on_either_provider(
    tmp_path, monkeypatch, name
):
    _bound_to(name, monkeypatch)
    chosen = PROVIDERS[name]
    model = ScriptedModel(reader_script(), model_provider=chosen)
    graphite, run_id = started(tmp_path / "g", model, model_provider=chosen)
    assert graphite.run(run_id) == "succeeded"
    assert len(model.requests) == 3
    assert all(request["model"] == MODEL for request in model.requests)
    record = graphite.session_record(run_id)
    selection = mp.selection_from_record(
        record["model"], credential_file="k", adapters=chosen.registry
    )
    for call in record["calls"]:
        assert call["reservation"]["provider_nanodollars"] == selection.reservation_nano
        settled = call["settlement"]["provider_nanodollars"]
        if name == "engy":
            assert settled == 100_000  # the scripted Engy report
        else:
            assert settled == selection.reservation_nano
    assert graphite.usage(run_id).settled > Decimal(0)


@pytest.mark.parametrize("name", ["engy", "spur"])
def test_admission_deadline_and_transport_are_shared(tmp_path, monkeypatch, name):
    _bound_to(name, monkeypatch)
    chosen = PROVIDERS[name]
    key = tmp_path / "key"
    key.write_text("fixture-not-a-key\n")
    key.chmod(0o600)
    sent = []

    class Opener:
        def open(self, request, timeout):
            sent.append(
                {
                    "url": request.full_url,
                    "bearer": request.get_header("Authorization", "").startswith(
                        "Bearer "
                    ),
                    "timeout": timeout,
                    "body": json.loads(request.data),
                }
            )
            reply = {
                "model": MODEL,
                "choices": [
                    {"message": {"content": "ok"}, "finish_reason": "stop"},
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            }
            return io.BytesIO(json.dumps(reply).encode())

    live = LiveModel(
        grant=grant(),
        credential_file=str(key),
        provider="graphite",
        model_provider=chosen,
        opener=Opener(),
    )
    selection = chosen.select(
        adapter_id=CHAT_ADAPTER[name], model_id=MODEL, credential_reference=str(key)
    )
    transport = live.transport_for(selection)
    assert type(transport) is mp.SelectionTransport
    assert mp.call_deadline_seconds(selection.settings) == (
        selection.settings.timeout_seconds + mp.DEADLINE_MARGIN_SECONDS
    )
    reply = transport(
        {
            "model": MODEL,
            "instructions": "fixture",
            "input": [{"role": "user", "content": "hi"}],
            "tools": [],
            "parallel_tool_calls": False,
            "max_output_tokens": 256,
        }
    )
    assert reply["status"] == "completed"
    assert reply["provider_protocol"] == mp.CHAT_COMPLETIONS
    (call,) = sent
    assert call["url"] == selection.adapter.endpoint
    assert call["bearer"] is True
    assert call["timeout"] == selection.settings.timeout_seconds
    assert call["body"]["model"] == MODEL
    # Another provider's selection, an unpriced model or another key: refused.
    other = PROVIDERS["spur" if name == "engy" else "engy"].select(
        adapter_id=CHAT_ADAPTER["spur" if name == "engy" else "engy"],
        model_id=MODEL,
        credential_reference=str(key),
    )
    with pytest.raises(ModelAccessRefused, match=chosen.adapter_refused):
        live.transport_for(other)
    wrong_key = chosen.select(
        adapter_id=CHAT_ADAPTER[name], model_id=MODEL, credential_reference="other"
    )
    with pytest.raises(ModelAccessRefused, match="credential_reference_mismatch"):
        live.transport_for(wrong_key)


# -- key custody -----------------------------------------------------------------------------
def test_the_spur_key_is_a_file_checked_by_the_engy_rule(tmp_path, capsys, bound):
    assert model_providers.SPUR_CREDENTIAL_PATH == "~/.config/carbon/spur-api-key"
    assert model_providers.SPUR_CREDENTIAL_MODE == 0o600
    key = tmp_path / "spur-api-key"
    key.write_text("fixture-not-a-key\n")
    key.chmod(0o644)
    with pytest.raises(phase3.RunnerRefused):
        owner_only_file(key)
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(last)["reason_code"] == "credential_file_must_be_owner_only"
    key.chmod(0o600)
    assert owner_only_file(key) == str(key)
    # Constructing access never opens the key: a missing file is accepted
    # here and refused only by the transport at the point of use.
    live = LiveModel(
        grant=grant(),
        credential_file=str(tmp_path / "absent"),
        provider="graphite",
        model_provider=SPUR_FIXTURE,
    )
    assert live.credential_reference == str(tmp_path / "absent")
    assert "fixture-not-a-key" not in repr(vars(live))
    assert os.stat(key).st_mode & 0o777 == 0o600


# -- ladder ----------------------------------------------------------------------------------
def test_engys_ladder_is_unchanged_and_spurs_is_its_own(tmp_path):
    engy = Ladder(tmp_path / "engy")
    assert engy.models == LADDER == mp.ENGY_LADDER == ENGY.ladder
    for role in RoleName:
        assert engy.rung(role) == ROLES[role].start_rung
        assert engy.model(role) == ROLES[role].start_model
    spur = Ladder(tmp_path / "spur", models=SPUR.ladder)
    with pytest.raises(LadderError, match="start_model_not_on_the_ladder"):
        spur.rung(RoleName.READER)


def test_unknown_model_provider_is_refused(tmp_path):
    with pytest.raises(ProviderUnavailable, match="unknown_model_provider"):
        provider(tmp_path / "g", model_provider="engy:glm-5.2")
    with pytest.raises(ValueError, match="unknown_model_provider"):
        ScriptedModel([], model_provider="openai")


# -- the miner surfaces never see SPUR -------------------------------------------------------
def test_the_launchpads_provider_choices_are_byte_identical_to_main():
    assert tuple(mp.ADAPTERS) == MAIN_ADAPTER_IDS
    assert digest(canonical(mp.provider_summary())) == MAIN_SUMMARY_DIGEST
    rows = capabilities._registered_providers(
        None, {"reason": "pinned_probe", "next_action": "none"}
    )
    assert digest(canonical(rows)) == MAIN_CHOICES_DIGEST
    assert "spur" not in json.dumps(mp.provider_summary()).lower()


@pytest.mark.parametrize("named", ["spur", "spur-chat"])
def test_a_miner_facing_launch_naming_spur_is_refused(named):
    with pytest.raises(mp.ModelSelectionRefused, match="unknown provider adapter"):
        mp.select(
            provider_id=named,
            model_id="glm-5.2",
            credential={"kind": "file", "reference": "/k"},
        )
    with pytest.raises(Exception, match="unknown_model_provider"):
        runner.RunnerAdapter._launch_choice(
            {}, {"agent": "autonomous", "model_provider": named}, None
        )
