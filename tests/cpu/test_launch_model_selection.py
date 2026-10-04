"""Launch-time model selection and battery feedback mode (C-MLP-02).

A launch may name the provider and model Carbon's agent calls, and a battery
campaign's feedback mode. The key file is never in the request: it is the one
the runner profile configures for that provider, and a provider without one is
refused by name before anything is created - never served with another
provider's key. The choice freezes when the campaign is created; a resume
keeps the frozen one.

Every key here is a planted fixture file under tmp_path. No provider, chain or
container is contacted.
"""

import json
import logging
from pathlib import Path

import pytest
from test_miner_launchpad_runner import (
    KEY,
    Chain,
    configured,
    product_campaign,
    run_id,
)

from carbon.development_session import research_campaign
from carbon.development_session.model_provider import ENGY_DEFAULT_MODEL, select
from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.operations import FIELDS, OPERATIONS
from scripts.dev.miner_launchpad.runner import (
    PATH_FIELDS,
    RunnerAdapter,
    validated_profile,
)

BATTERY = {
    "challenge": "battery-fastcharge-ageing-development-v1",
    "challenge_version": "1.0",
}
BURGERS = {"challenge": "burgers-dynamics-v1", "challenge_version": "1.0"}
ENGY_KEY = "sk-engy-PLANTED-SPECIMEN-7f3a9c"
OPENAI_KEY = "sk-openai-PLANTED-SPECIMEN-2b81"
LAUNCH_FIELDS = {"model_provider", "model", "feedback_mode"}


@pytest.fixture(autouse=True)
def _named_challenge(monkeypatch):
    """Burgers is retired, so a launch must name its Challenge. A launch body
    here that names none names the registered DEVELOPMENT fixture Challenge,
    exactly as the other launch tests do."""
    from scripts.dev.miner_launchpad.journey_fixture import (
        launch_with_fixture_challenge,
    )

    launch_with_fixture_challenge(monkeypatch.setattr)


def key_file(tmp_path, name, secret, mode=0o600):
    keys = tmp_path / "keys"
    keys.mkdir(mode=0o700, exist_ok=True)
    path = keys / name
    path.write_text(secret + "\n")
    path.chmod(mode)
    return path


def profile(tmp_path, *, credentials=None):
    tmp_path.chmod(0o700)
    paths = {name: str(tmp_path / name) for name in PATH_FIELDS | {"operator_config"}}
    paths["api_key_file"] = str(key_file(tmp_path, "openai.key", OPENAI_KEY))
    cfg = {**configured(tmp_path), "paths": paths}
    if credentials is not None:
        cfg["provider_credentials"] = credentials
    return cfg


def host(tmp_path, monkeypatch, cfg, chain=None):
    bridge = RunnerAdapter(
        tmp_path / "browser.sqlite3", principal="alice", registration=chain or Chain()
    )
    monkeypatch.setattr(bridge, "configured", lambda: cfg)
    started = []
    monkeypatch.setattr(bridge, "_start", lambda *args: started.append(args))
    return bridge, started


def engy_profile(tmp_path):
    engy = key_file(tmp_path, "engy.key", ENGY_KEY)
    return profile(tmp_path, credentials={"engy-anthropic": str(engy)}), engy


def capture_run(monkeypatch, bridge):
    """Run `_run` with the campaign replaced by one that records its args."""
    seen = {}

    async def entry(args, *, ledger):
        seen["args"] = args

    monkeypatch.setattr(research_campaign, "execute", entry)
    monkeypatch.setattr(bridge, "_cleanup", lambda ledger: True)
    return seen


# -- Both doors -------------------------------------------------------------


def test_both_doors_carry_the_launch_choice():
    launch = OPERATIONS["launch"]
    assert LAUNCH_FIELDS <= launch.optional
    assert not LAUNCH_FIELDS & launch.required
    for field in LAUNCH_FIELDS:
        assert FIELDS[field][0] == "string" and FIELDS[field][1]
    tools = {tool.name: tool for tool in make_operation_tools(object())}
    schema = tools[PREFIX + "launch"].parameters["properties"]
    assert LAUNCH_FIELDS <= set(schema)
    # The specimen: the schema check can fail - practice carries none of them.
    assert not LAUNCH_FIELDS & set(tools[PREFIX + "practice"].parameters["properties"])
    assert "strategy" in tools[PREFIX + "practice"].parameters["properties"]


# -- Replay identity --------------------------------------------------------


def test_a_request_without_the_fields_keeps_its_historical_digest(tmp_path):
    from carbon.development_session.profile import canonical, digest

    tmp_path.chmod(0o700)
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3", principal="alice")
    cfg = configured(tmp_path)
    request = {"agent": "autonomous", "profile": "p", "idempotency_key": KEY}
    _, historical, _ = bridge._launch_identity(cfg, request)
    assert historical == digest(canonical({"profile": "p"}))
    _, chosen, _ = bridge._launch_identity(
        cfg, {**request, "model_provider": "engy-anthropic"}
    )
    assert chosen != historical


def test_a_changed_model_under_the_same_key_is_a_conflict(tmp_path, monkeypatch):
    cfg, _ = engy_profile(tmp_path)
    chain = Chain()
    bridge, started = host(tmp_path, monkeypatch, cfg, chain)
    first = {"profile": "opaque-profile", "model_provider": "engy-anthropic"}
    launched = bridge.launch({**first, "model": ENGY_DEFAULT_MODEL}, KEY)
    # The same request replays, reading no chain and starting nothing.
    assert bridge.launch({**first, "model": ENGY_DEFAULT_MODEL}, KEY) == launched
    assert chain.reads == 1 and len(started) == 1
    for changed in (
        {**first, "model": "qwen3.8-27b"},
        {**first, "model_provider": "engy-chat"},
        {"profile": "opaque-profile"},
    ):
        with pytest.raises(Rejected, match="research_launch_replay_conflict"):
            bridge.launch(changed, KEY)
    assert len(started) == 1 and len(bridge.recent()) == 1


# -- Credentials come from the profile -------------------------------------


def test_the_chosen_provider_runs_with_its_profile_key(tmp_path, monkeypatch):
    cfg, engy = engy_profile(tmp_path)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    identity = bridge.launch(
        {
            "profile": "opaque-profile",
            "model_provider": "engy-anthropic",
            "model": "qwen3.8-27b",
        },
        KEY,
    )["id"]
    _, _, root, product, choice = started[0]
    assert choice.selection.provider_id == "engy-anthropic"
    assert choice.selection.model_id == "qwen3.8-27b"
    product_campaign(root, identity)  # the ledger a launch's root holds
    seen = capture_run(monkeypatch, bridge)
    bridge._run(identity, cfg, root, product, choice)
    args = seen["args"]
    assert args.command == "run"
    assert args.model_selection == {
        "provider_id": "engy-anthropic",
        "model_id": "qwen3.8-27b",
    }
    assert args.api_key_file == engy
    # The campaign's own builder accepts what the runner passed.
    assert research_campaign.supplied_selection(args).model_id == "qwen3.8-27b"


@pytest.mark.parametrize("provider", ["anthropic", "engy-chat"])
def test_an_unconfigured_provider_is_refused_by_name_before_anything(
    tmp_path, monkeypatch, provider
):
    """Never served with another provider's key: the profile has an OpenAI key
    and an Engy Messages key, and neither stands in. The specimen: the same
    launch creates its campaign once that provider's key is configured."""
    cfg, _ = engy_profile(tmp_path)
    chain = Chain()
    bridge, started = host(tmp_path, monkeypatch, cfg, chain)
    fresh = "request-key-unconfigured"
    request = {"profile": "opaque-profile", "model_provider": provider}
    if provider == "anthropic":
        request["model"] = "claude-fixture-model"
    with pytest.raises(Rejected, match="model_provider_credential_not_configured"):
        bridge.launch(request, fresh)
    assert chain.reads == 0 and started == [] and bridge.recent() == []
    assert not (Path(cfg["campaigns_root"]) / run_id(fresh)).exists()

    extra = key_file(tmp_path, provider + ".key", "sk-other-fixture")
    cfg["provider_credentials"][provider] = str(extra)
    bridge.launch(request, fresh)
    assert len(started) == 1 and len(bridge.recent()) == 1
    assert Path(started[0][4].selection.credential.reference) == extra


def test_a_key_file_others_can_read_is_refused(tmp_path, monkeypatch):
    cfg, engy = engy_profile(tmp_path)
    engy.chmod(0o644)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    request = {"profile": "opaque-profile", "model_provider": "engy-anthropic"}
    with pytest.raises(Rejected, match="model_provider_credential_unusable"):
        bridge.launch(request, KEY)
    engy.chmod(0o600)
    bridge.launch(request, KEY)
    assert len(started) == 1


def test_the_profile_credential_map_is_closed(tmp_path):
    cfg = {
        **profile(tmp_path),
        "schema": "carbon.launchpad.runner-profile.v2",
        "enabled": True,
    }
    assert validated_profile({**cfg, "provider_credentials": {}})
    for invalid in (
        {"not-a-provider": "/k"},
        {"engy-anthropic": "relative/key"},
        {"engy-anthropic": 1},
        ["engy-anthropic"],
    ):
        with pytest.raises(ValueError):
            validated_profile({**cfg, "provider_credentials": invalid})


@pytest.mark.parametrize(
    "request_fields,code",
    [
        ({"model": ENGY_DEFAULT_MODEL}, "model_provider_required"),
        ({"model_provider": "not-an-adapter"}, "unknown_model_provider"),
        (
            {"model_provider": "engy-anthropic", "model": "gpt-4o"},
            "model_selection_refused",
        ),
        (
            {"model_provider": "openai-compatible-chat", "model": "m"},
            "model_provider_endpoint_not_configured",
        ),
        (
            {"model_provider": "engy-anthropic", "agent": "none"},
            "model_selection_needs_the_autonomous_agent",
        ),
    ],
)
def test_an_unusable_selection_is_refused_by_name(
    tmp_path, monkeypatch, request_fields, code
):
    cfg, _ = engy_profile(tmp_path)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    with pytest.raises(Rejected, match=code):
        bridge.launch({"profile": "opaque-profile", **request_fields}, KEY)
    assert started == [] and bridge.recent() == []


def test_the_key_appears_nowhere_it_is_recorded(tmp_path, monkeypatch, caplog):
    """Planted keys, scanned for in the request records, the manifest blocks a
    campaign freezes from what the runner passed, every refusal and the logs.
    The positive specimen: the same scan finds each key in its key file."""
    from carbon.battery.campaign import provider_plan

    caplog.set_level(logging.DEBUG)
    cfg, engy = engy_profile(tmp_path)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    request = {"profile": "opaque-profile", "model_provider": "engy-anthropic"}
    identity = bridge.launch(request, KEY)["id"]
    refusals = []
    for bad in (
        {**request, "model": "gpt-4o"},
        {**request, "model_provider": "anthropic", "model": "m"},
        {**request, "feedback_mode": "LOUD"},
    ):
        try:
            bridge.launch(bad, "request-key-refused-01")
        except Rejected as refused:
            refusals.append(f"{refused!r} {refused.code} {refused.status}")
    assert len(refusals) == 3
    _, _, root, product, choice = started[0]
    product_campaign(root, identity)
    seen = capture_run(monkeypatch, bridge)
    bridge._run(identity, cfg, root, product, choice)
    selection = research_campaign.supplied_selection(seen["args"])
    budget = {"ceilings": {"provider_attempts": 5, "provider_nanodollars": 10**9}}
    recorded = [
        (tmp_path / "browser.sqlite3").read_bytes(),
        json.dumps(selection.manifest_record()).encode(),
        json.dumps(provider_plan("autonomous", budget, selection)).encode(),
        json.dumps(bridge.get(identity)).encode(),
        " ".join(refusals).encode(),
        caplog.text.encode(),
    ]

    def leaks(blob, secret):
        return secret.encode() in blob

    for secret in (ENGY_KEY, OPENAI_KEY):
        assert not any(leaks(blob, secret) for blob in recorded)
    # Nor the key file's location, in what the manifest freezes.
    assert str(engy).encode() not in recorded[1] + recorded[2]
    assert leaks(engy.read_bytes(), ENGY_KEY)
    assert leaks(Path(cfg["paths"]["api_key_file"]).read_bytes(), OPENAI_KEY)


# -- Battery feedback mode --------------------------------------------------


@pytest.mark.parametrize("mode", ["", "full", "WITHHELD", "SCORE_WITHHELD "])
def test_an_invalid_feedback_mode_is_refused(tmp_path, monkeypatch, mode):
    bridge, started = host(tmp_path, monkeypatch, profile(tmp_path))
    with pytest.raises(Rejected, match="invalid_feedback_mode"):
        bridge.launch(
            {"profile": "opaque-profile", **BATTERY, "feedback_mode": mode}, KEY
        )
    assert started == []


@pytest.mark.parametrize(
    ("challenge", "refusal"),
    [
        # The registered fixture Challenge offers only FULL (C-MLP-04: each
        # Challenge's campaign declares its own modes), so a mode only
        # battery's campaign declares is refused for it.
        ({}, "feedback_mode_not_offered_by_challenge"),
        # Burgers is retired: refused as retired, before any mode is read.
        (BURGERS, "challenge_retired"),
    ],
)
def test_a_mode_the_challenge_does_not_offer_is_refused(
    tmp_path, monkeypatch, challenge, refusal
):
    bridge, started = host(tmp_path, monkeypatch, profile(tmp_path))
    with pytest.raises(Rejected, match=refusal):
        bridge.launch(
            {
                "profile": "opaque-profile",
                **challenge,
                "feedback_mode": "SCORE_WITHHELD",
            },
            KEY,
        )
    assert started == []
    # FULL is every Challenge's, so the fixture Challenge accepts it.
    if not challenge:
        bridge.launch(
            {"profile": "opaque-profile", "feedback_mode": "FULL"},
            "fixture-full-mode-launch",
        )
        assert started[-1][4].feedback_mode == "FULL"
    # The specimen: the battery Challenge's campaign offers the mode.
    bridge.launch(
        {"profile": "opaque-profile", **BATTERY, "feedback_mode": "SCORE_WITHHELD"},
        "battery-specimen-launch",
    )
    assert started[-1][4].feedback_mode == "SCORE_WITHHELD"


def test_a_withheld_score_needs_a_campaign_that_reads_the_mode(tmp_path, monkeypatch):
    """Fail closed: a battery campaign that does not know SCORE_WITHHELD would
    run with full feedback, so the launch is refused rather than dispatched."""
    from carbon.battery import campaign as battery

    bridge, started = host(tmp_path, monkeypatch, profile(tmp_path))
    request = {
        "profile": "opaque-profile",
        **BATTERY,
        "feedback_mode": "SCORE_WITHHELD",
    }
    monkeypatch.delattr(battery, "FEEDBACK_MODES", raising=False)
    with pytest.raises(Rejected, match="invalid_feedback_mode"):
        bridge.launch(request, KEY)
    assert started == []
    monkeypatch.setattr(
        battery, "FEEDBACK_MODES", ("FULL", "SCORE_WITHHELD"), raising=False
    )
    bridge.launch(request, KEY)
    assert started[0][4].feedback_mode == "SCORE_WITHHELD"


def test_the_runner_takes_its_modes_from_the_battery_campaign(tmp_path, monkeypatch):
    """One list: a mode the battery campaign declares is accepted and
    described, with no second copy in the runner to update."""
    from carbon.battery import campaign as battery
    from scripts.dev.miner_launchpad import operations

    monkeypatch.setattr(
        battery, "FEEDBACK_MODES", (*battery.FEEDBACK_MODES, "FIXTURE_NEW_MODE")
    )
    bridge, started = host(tmp_path, monkeypatch, profile(tmp_path))
    bridge.launch(
        {"profile": "opaque-profile", **BATTERY, "feedback_mode": "FIXTURE_NEW_MODE"},
        KEY,
    )
    assert started[0][4].feedback_mode == "FIXTURE_NEW_MODE"
    for mode in battery.FEEDBACK_MODES:
        assert mode in operations._feedback_modes()


def test_the_described_modes_are_the_battery_modes():
    from carbon.battery import campaign as battery
    from scripts.dev.miner_launchpad import operations

    described = operations.FIELDS["feedback_mode"][1]
    for mode in battery.FEEDBACK_MODES:
        assert mode in described


# -- Resume -----------------------------------------------------------------


def test_a_resume_keeps_the_frozen_choice(tmp_path, monkeypatch):
    """A frozen manifest decides: the launch's fields are not applied again,
    and the key is the frozen provider's, from the profile. The specimen: the
    same `_run` without a manifest applies them."""
    cfg, engy = engy_profile(tmp_path)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    identity = bridge.launch(
        {
            "profile": "opaque-profile",
            **BATTERY,
            "model_provider": "engy-anthropic",
            "model": "qwen3.8-27b",
            "feedback_mode": "FULL",
        },
        KEY,
    )["id"]
    _, _, root, product, choice = started[0]
    product_campaign(root, identity)
    seen = capture_run(monkeypatch, bridge)
    bridge._run(identity, cfg, root, product, choice)
    assert seen["args"].feedback_mode == "FULL"
    assert seen["args"].model_selection["model_id"] == "qwen3.8-27b"

    frozen = select(
        provider_id="engy-anthropic",
        model_id=ENGY_DEFAULT_MODEL,
        credential={"kind": "file", "reference": "unset"},
    )
    (root / "campaign-manifest.json").write_text(
        json.dumps(
            {"provider": {"agent": "autonomous", "model_selection": frozen.record()}}
        )
    )
    bridge._run(identity, cfg, root, product, choice)
    args = seen["args"]
    assert args.command == "resume"
    assert not hasattr(args, "model_selection") and not hasattr(args, "feedback_mode")
    assert args.api_key_file == engy

    # The frozen provider's key removed from the profile: refused by name,
    # never answered with the profile's other key.
    del cfg["provider_credentials"]["engy-anthropic"]
    with pytest.raises(Rejected, match="model_provider_credential_not_configured"):
        bridge._frozen_credential(cfg, root)


def test_options_and_capabilities_offer_only_configured_providers(
    tmp_path, monkeypatch
):
    from scripts.dev.miner_launchpad import capabilities

    cfg, _ = engy_profile(tmp_path)
    bridge, _ = host(tmp_path, monkeypatch, cfg)
    rows = {row["provider_id"]: row for row in bridge._model_providers(cfg)}
    assert rows["engy-anthropic"]["availability"] == "available"
    assert rows["openai-responses"]["availability"] == "available"
    assert rows["engy-chat"]["reason"] == "model_provider_credential_not_configured"
    assert rows["openai-compatible-chat"]["reason"] == (
        "model_provider_endpoint_not_configured"
    )
    options = {"agents": [], "model_providers": list(rows.values())}
    listed = {
        p["id"]: p
        for p in capabilities._registered_providers(options, capabilities.NO_PROFILE)
    }
    assert listed["engy-anthropic"]["availability"] == "available"
    assert listed["engy-chat"]["availability"] == "unavailable"
    assert "provider_credentials.engy-chat" in listed["engy-chat"]["next_action"]
    assert ENGY_KEY not in json.dumps(listed)


def test_the_page_sends_the_chosen_provider_and_model():
    script = (
        Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/app.js"
    ).read_text()
    assert "pendingResearch.body.model_provider = provider.id" in script
    assert "pendingResearch.body.model = wizard.model" in script


# -- Model settings ----------------------------------------------------------


def test_both_doors_carry_model_settings_as_an_object():
    launch = OPERATIONS["launch"]
    assert "model_settings" in launch.optional
    assert FIELDS["model_settings"][0] == "object"
    tools = {tool.name: tool for tool in make_operation_tools(object())}
    assert "model_settings" in tools[PREFIX + "launch"].parameters["properties"]
    # The specimen: practice carries no model settings.
    assert "model_settings" not in tools[PREFIX + "practice"].parameters["properties"]


def test_a_chosen_output_cap_reaches_the_campaign_and_its_record(tmp_path, monkeypatch):
    """The cap flows launch -> choice -> args -> the campaign's own selection
    builder -> the provider plan the manifest freezes, and sizes the per-call
    reservation. The specimen: the same launch without settings takes the
    model's own maximum (OWNER-LAUNCHPAD-PROD-02; it kept 2048 before), so the
    miner's cap is what binds."""
    from carbon.battery.campaign import provider_plan

    cfg, _ = engy_profile(tmp_path)
    bridge, started = host(tmp_path, monkeypatch, cfg)
    request = {
        "profile": "opaque-profile",
        "model_provider": "engy-anthropic",
        "model_settings": {"max_output_tokens": 16384},
    }
    identity = bridge.launch(request, KEY)["id"]
    _, _, root, product, choice = started[0]
    assert choice.selection.settings.max_output_tokens == 16384
    product_campaign(root, identity)
    seen = capture_run(monkeypatch, bridge)
    bridge._run(identity, cfg, root, product, choice)
    assert seen["args"].model_selection["settings"] == {"max_output_tokens": 16384}
    selection = research_campaign.supplied_selection(seen["args"])
    assert selection.settings.max_output_tokens == 16384
    budget = {"ceilings": {"provider_attempts": 5, "provider_nanodollars": 10**9}}
    plan = provider_plan("autonomous", budget, selection)
    assert plan["model_selection"]["settings"]["max_output_tokens"] == 16384

    default_request = {k: v for k, v in request.items() if k != "model_settings"}
    bridge.launch(default_request, "request-key-default-settings")
    default = started[1][4]
    assert default.settings is None
    assert default.selection.settings.max_output_tokens == 131072
    assert selection.reservation_nano < default.selection.reservation_nano


@pytest.mark.parametrize(
    "request_fields,code",
    [
        ({"model_settings": {"max_output_tokens": 16384}}, "model_provider_required"),
        (
            {"model_provider": "engy-anthropic", "model_settings": 16384},
            "model_selection_refused",
        ),
        (
            {"model_provider": "engy-anthropic", "model_settings": {"top_p": 1}},
            "model_selection_refused",
        ),
        (
            {
                "model_provider": "engy-anthropic",
                "model_settings": {"max_output_tokens": 255},
            },
            "model_selection_refused",
        ),
        (
            {
                "model_provider": "engy-anthropic",
                "model_settings": {"max_output_tokens": 131073},
            },
            "model_selection_refused",
        ),
    ],
)
def test_unusable_model_settings_are_refused_before_anything(
    tmp_path, monkeypatch, request_fields, code
):
    cfg, _ = engy_profile(tmp_path)
    chain = Chain()
    bridge, started = host(tmp_path, monkeypatch, cfg, chain)
    with pytest.raises(Rejected, match=code):
        bridge.launch({"profile": "opaque-profile", **request_fields}, KEY)
    assert started == [] and bridge.recent() == [] and chain.reads == 0
    # The specimen: the bounds themselves are accepted.
    for cap in (256, 131072):
        bridge.launch(
            {
                "profile": "opaque-profile",
                "model_provider": "engy-anthropic",
                "model_settings": {"max_output_tokens": cap},
            },
            f"request-key-bound-{cap}",
        )
    caps = [s[4].selection.settings.max_output_tokens for s in started]
    assert caps == [256, 131072]
