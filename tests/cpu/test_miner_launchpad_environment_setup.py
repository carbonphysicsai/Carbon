"""C-MLP-03 slice 1: a registered miner sets up their environment.

Drives the setup over the real loopback server and the real runner profile
validator. No chain, provider or image is contacted: the onboarding door is a
stub, and the live checks are fixture checks or a fixture HTTP opener.
"""

import http.client
import io
import json
import stat
import threading
import urllib.error
from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import controller as launchpad
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    CHECK_SETTINGS,
    LOCAL_CPU,
    SIGNER_STEP,
    EnvironmentSetup,
    LiveChecks,
    SetupRefused,
    check_quote,
    choices,
)

TOKEN = "x" * 40
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
KEY = "sk-fixture-never-echoed-0123456789"
REVISION = "a" * 40
#: A Chutes price as `model_provider.published_pricing` records it (fixture).
PUBLISHED = {
    "unit": "nanodollars per token",
    "input": 240,
    "cached_input": 24,
    "output_including_reasoning": 2200,
    "source": "provider_published",
    "reference": "https://llm.chutes.ai/v1/models",
    "observed": "2026-10-02T00:00:00Z",
    "note": "fixture: read from the provider's public model list",
}
RUNTIME = {
    "implementation": {
        "revision": REVISION,
        "tree": "b" * 40,
        "source_tree_digest": "sha256:" + "c" * 64,
    },
    "images": ["sha256:" + "d" * 64, "sha256:" + "e" * 64],
}


def agreed(provider_id, model_id):
    """Consent to the quoted maximum, as the page sends it after the tick."""
    quote = check_quote(provider_id, model_id, Path("/never/read"))
    return {"max_cost_nano": quote["max_cost_nano"]}


CONSENT = agreed("engy-chat", "deepseek-v4-flash-0731")


class Onboarding:
    def __init__(self, registered=True):
        self.registered = registered

    def confirm(self, address):
        return {"registered": self.registered, "confirmed": self.registered}

    def requirements(self):
        return {}


class Checks:
    """Fixture live checks: record what they were given, contact nothing."""

    def __init__(self):
        self.calls = []

    def published_pricing(self, provider_id, model_id):
        self.calls.append(("published_pricing", provider_id, model_id))
        return dict(PUBLISHED)

    def inference(self, provider_id, model_id, credential_file, spec=None):
        self.calls.append(("inference", provider_id, credential_file))
        return {
            "models_source": "fixture",
            "models_listed": 1,
            "completion": "answered",
        }

    def compute(self, image, analysis):
        self.calls.append(("compute", image, analysis))
        return RUNTIME

    @staticmethod
    def hermes_files():
        return ["/fixture/hermes/profiles/carbon/config.yaml"]

    def agent(self, hotkey, socket_path=None):
        self.calls.append(("agent", hotkey, socket_path))
        return {"signing": "carbon-miner-signer holds the registered hotkey"}

    @staticmethod
    def operator_config(path):
        if not path.is_file():
            raise SetupRefused("operator_config", "operator_config_invalid")


def files(tmp_path):
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    made = {}
    for name in ("worker.json", "analysis.json", "operator.json"):
        (home / name).write_text("{}")
        made[name] = str(home / name)
    return made


def completed(tmp_path, setup):
    made = files(tmp_path)
    setup.begin({"address": HOTKEY})
    setup.inference(
        {
            "provider_id": "engy-chat",
            "model_id": "deepseek-v4-flash-0731",
            "key": KEY,
            "consent": CONSENT,
        }
    )
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": made["worker.json"],
            "analysis_image_manifest": made["analysis.json"],
        }
    )
    setup.agent({"choice": AUTONOMOUS, "operator_config": made["operator.json"]})
    return made


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


def test_choices_offer_only_launchable_options_each_with_a_cost_basis():
    offered = choices()
    inference = {c["id"]: c for c in offered["inference"]}
    # Slice 2: Engy's Chat Completions route first and the default, Chutes
    # with its published prices, and the generic adapters with an endpoint.
    assert offered["inference"][0]["id"] == "engy-chat"
    assert [c["id"] for c in offered["inference"] if c["default"]] == ["engy-chat"]
    assert inference["chutes"]["pricing"] == "published live by the provider"
    assert inference["chutes"]["model_policy"].startswith("any model id")
    for generic in ("openai-compatible-chat", "openai-compatible-responses"):
        assert inference[generic]["needs_endpoint"] is True
        assert inference[generic]["pricing"] == "yours to declare (optional)"
    assert inference["engy-chat"]["needs_endpoint"] is False
    # Slice 3: this machine's CPU is the default; its own GPU is offered
    # beside it, for practice speed only.
    # Slice 4: a GPU rented on the miner's own provider account.
    assert [c["id"] for c in offered["compute"]] == [
        LOCAL_CPU,
        "this-machine-gpu",
        "rented-gpu",
    ]
    rented = offered["compute"][2]
    # Slice 4b: Targon, a VM reached over SSH, names a VM image.
    assert {p["id"]: p["vm"] for p in rented["providers"]} == {
        "runpod": False,
        "lium": False,
        "targon": True,
    }
    assert [c["id"] for c in offered["compute"] if c["default"]] == [LOCAL_CPU]
    assert "speed only" in offered["compute"][1]["note"]
    # Slice 5: Hermes beside Carbon's own agent.
    assert [c["id"] for c in offered["agent"]] == [AUTONOMOUS, "hermes"]
    for step in ("inference", "compute", "agent"):
        for choice in offered[step]:
            assert choice["cost_basis"] and choice["live_check"]


def test_setup_begins_only_for_a_registered_hotkey(state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(False), checks=Checks())
    with pytest.raises(SetupRefused) as refused:
        setup.begin({"address": HOTKEY})
    assert (refused.value.field, refused.value.code) == (
        "address",
        "hotkey_not_registered",
    )
    with pytest.raises(SetupRefused) as refused:
        setup.inference(
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "key": KEY,
                "consent": CONSENT,
            }
        )
    assert refused.value.field == "address"
    assert not (state / "environment" / "keys").exists()


def test_live_checks_need_consent_and_refusals_name_the_field(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    cases = [
        (
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "key": KEY,
                "consent": False,
            },
            "consent",
        ),
        (
            {
                "provider_id": "openai-compatible-chat",
                "model_id": "m",
                "key": KEY,
                "consent": CONSENT,
            },
            "endpoint",
        ),
        (
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "endpoint": "https://example.org/v1/chat/completions",
                "key": KEY,
                "consent": CONSENT,
            },
            "endpoint",
        ),
        (
            {
                "provider_id": "engy-chat",
                "model_id": "not-on-the-ladder",
                "key": KEY,
                "consent": CONSENT,
            },
            "model_id",
        ),
        (
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "consent": CONSENT,
            },
            "key",
        ),
        (
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "key": "two\nlines",
                "consent": CONSENT,
            },
            "key",
        ),
        ({"provider_id": "engy-chat", "consent": CONSENT}, "model_id"),
        (
            {
                "provider_id": "engy-chat",
                "model_id": "m",
                "consent": CONSENT,
                "extra": 1,
            },
            "extra",
        ),
    ]
    for value, field in cases:
        with pytest.raises(SetupRefused) as refused:
            setup.inference(value)
        assert refused.value.field == field, value


def test_a_live_check_spends_only_on_consent_to_its_quoted_maximum(state):
    """2.2: consent is to an amount the miner was shown. A bare `true` - what a
    client that defaults consent on would send - says nothing about what was
    agreed to, and is refused before any key is written or any check runs."""
    checks = Checks()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    setup.begin({"address": HOTKEY})
    quote = setup.quote(
        {"provider_id": "engy-chat", "model_id": "deepseek-v4-flash-0731"}
    )
    assert quote["max_cost_nano"] == CONSENT["max_cost_nano"]
    assert type(quote["max_cost_nano"]) is int and quote["max_cost_nano"] > 0
    assert "at most $" in quote["statement"] and "free" in quote["statement"]
    base = {
        "provider_id": "engy-chat",
        "model_id": "deepseek-v4-flash-0731",
        "key": KEY,
    }
    for consent, code in (
        (None, "field_required"),
        (True, "live_check_needs_consent"),
        (1, "live_check_needs_consent"),
        ({}, "live_check_needs_consent"),
        ({"max_cost_nano": True}, "consent_does_not_match_quoted_cost"),
        (
            {"max_cost_nano": quote["max_cost_nano"] - 1},
            "consent_does_not_match_quoted_cost",
        ),
        ({"max_cost_nano": None}, "consent_does_not_match_quoted_cost"),
        (
            {"max_cost_nano": quote["max_cost_nano"], "also": 1},
            "live_check_needs_consent",
        ),
    ):
        value = dict(base) if consent is None else {**base, "consent": consent}
        with pytest.raises(SetupRefused) as refused:
            setup.inference(value)
        assert (refused.value.field, refused.value.code) == ("consent", code), consent
    # Nothing ran and nothing was stored on any refusal.
    assert checks.calls == []
    assert not (state / "environment" / "keys").exists()
    # Specimen: the same request with the quoted amount runs the check.
    setup.inference({**base, "consent": CONSENT})
    assert [call[0] for call in checks.calls] == ["inference"]


def test_the_quote_is_the_reservation_bound_of_the_check_that_runs():
    """The quoted maximum is computed from the provider's listed price and the
    settings the check actually sends, not stated loosely."""
    from carbon.development_session.model_provider import ADAPTERS, UNKNOWN_SPEND

    pricing = ADAPTERS["engy-chat"].priced_models["deepseek-v4-flash-0731"]
    assert CONSENT["max_cost_nano"] == (
        CHECK_SETTINGS["max_input_tokens"] * pricing.input_nano
        + CHECK_SETTINGS["max_output_tokens"] * pricing.output_nano
    )
    # A model with no known price has no calculable maximum, and says so; the
    # miner may still agree, but only to that statement.
    unpriced = check_quote("anthropic", "a-model-with-no-listed-price", Path("/x"))
    assert unpriced["max_cost_nano"] is None
    assert UNKNOWN_SPEND in unpriced["statement"]


def test_a_missing_image_names_its_field_and_build_step(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    made = files(tmp_path)
    with pytest.raises(SetupRefused) as refused:
        setup.compute(
            {
                "choice": LOCAL_CPU,
                "image_manifest": str(tmp_path / "absent.json"),
                "analysis_image_manifest": made["analysis.json"],
            }
        )
    assert refused.value.field == "image_manifest"
    assert "c03_worker_image.sh" in refused.value.next_step
    with pytest.raises(SetupRefused) as refused:
        setup.compute(
            {
                "choice": "someone-elses-gpu",
                "image_manifest": made["worker.json"],
                "analysis_image_manifest": made["analysis.json"],
            }
        )
    assert refused.value.field == "choice"


def test_keys_are_owner_only_never_returned_and_the_profile_validates(tmp_path, state):
    checks = Checks()
    attached = []
    setup = EnvironmentSetup(
        state,
        onboarding=Onboarding(),
        checks=checks,
        attach=lambda path: attached.append(path) or True,
    )
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    assert result["attached"] is True and attached == [setup.profile_path]
    assert result["steps"]["review"] == {"ready": True, "profile_written": True}

    root = state / "environment"
    key_file = root / "keys" / "engy-chat.key"
    for path in (
        root,
        root / "keys",
        key_file,
        root / "miner-public.json",
        setup.profile_path,
        setup.record_path,
    ):
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, path
    assert key_file.read_text() == KEY
    # The check is given the key's file, never the key.
    assert checks.calls[0] == ("inference", "engy-chat", key_file)

    # No key anywhere the page or the profile can read.
    for text in (
        json.dumps(result),
        json.dumps(setup.state()),
        setup.profile_path.read_text(),
        setup.record_path.read_text(),
    ):
        assert KEY not in text
    # External signing: the Agent step asked the signer for the registered
    # hotkey, and nothing that could open the miner's key was stored.
    assert checks.calls[-1] == ("agent", HOTKEY, None)
    assert not (root / "miner-password").exists()

    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["principal"] == HOTKEY
    assert cfg["model_selection"] == {
        "provider_id": "engy-chat",
        "model_id": "deepseek-v4-flash-0731",
    }
    public = json.loads((root / "miner-public.json").read_bytes())
    assert public == {"netuid": 567, "hotkey": HOTKEY}
    assert "miner_password_file" not in cfg["paths"]
    assert "signer_socket" not in cfg["paths"]
    # The key is the chosen provider's alone: the pinned default never gets it.
    assert runner.provider_credential(cfg, "engy-chat") == str(key_file)
    assert runner.provider_credential(cfg, "openai-responses") is None
    assert runner.foreign_default_key(cfg)


def test_review_refuses_until_every_step_is_checked(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert refused.value.field == "inference"
    assert not setup.profile_path.exists()


def test_a_changed_step_needs_a_new_review(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    setup.inference(
        {
            "provider_id": "engy-chat",
            "model_id": "qwen3.8-27b",
            "consent": agreed("engy-chat", "qwen3.8-27b"),
        }
    )
    assert setup.state()["steps"]["review"]["profile_written"] is False


def test_a_launch_naming_no_model_runs_with_the_setup_choice(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    cfg = setup.profile()
    choice = runner.RunnerAdapter._launch_choice(
        cfg, {"agent": "autonomous"}, {"id": "battery", "version": "1"}
    )
    assert choice.selection.provider_id == "engy-chat"
    assert choice.selection.model_id == "deepseek-v4-flash-0731"
    # Naming the pinned default explicitly is refused: its key is not this one.
    with pytest.raises(launchpad.Rejected, match="credential_not_configured"):
        runner.RunnerAdapter._launch_choice(
            cfg, {"agent": "autonomous", "model_provider": "openai-responses"}, None
        )


def test_model_selection_must_name_a_configured_launchable_provider(tmp_path, state):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, setup)
    cfg = setup.profile()
    for bad in (
        {"provider_id": "anthropic", "model_id": "m"},  # no key configured
        {"provider_id": "openai-compatible-chat", "model_id": "m"},
        {"provider_id": "engy-chat"},
    ):
        with pytest.raises(ValueError):
            runner.validated_profile({**cfg, "model_selection": bad})


class Opener:
    """A fixture urllib opener: answers by URL and records what was sent."""

    def __init__(self, answers):
        self.answers, self.sent, self.bodies = answers, [], []

    def open(self, request, timeout=None):
        self.sent.append((request.full_url, dict(request.header_items())))
        self.bodies.append(json.loads(request.data) if request.data else None)
        status, body = self.answers[request.full_url]
        if status != 200:
            raise urllib.error.HTTPError(
                request.full_url, status, "refused", {}, io.BytesIO(b"{}")
            )
        return io.BytesIO(json.dumps(body).encode())


def key_file(tmp_path):
    home = tmp_path / "keys"
    home.mkdir(mode=0o700)
    path = home / "k"
    path.write_text(KEY)
    path.chmod(0o600)
    return path


CHAT_REPLY = {
    "choices": [{"message": {"role": "assistant", "content": "ready"}}],
    "usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10},
}


def test_inference_check_lists_models_and_completes_with_its_own_provider(tmp_path):
    opener = Opener(
        {
            "https://api.engy.ai/v1/models": (
                200,
                {"data": [{"id": "deepseek-v4-flash-0731"}]},
            ),
            "https://api.engy.ai/v1/chat/completions": (200, CHAT_REPLY),
        }
    )
    check = LiveChecks(opener=opener).inference(
        "engy-chat", "deepseek-v4-flash-0731", key_file(tmp_path)
    )
    assert check["completion"] == "answered"
    assert check["models_source"] == "https://api.engy.ai/v1/models"
    # The public list is read without a key; the key goes to its own endpoint.
    listing, completion = opener.sent
    assert not any(KEY in v for v in listing[1].values())
    assert completion[0] == "https://api.engy.ai/v1/chat/completions"
    assert completion[1]["Authorization"] == "Bearer " + KEY
    assert KEY not in json.dumps(check)
    # The check sends the quoted output ceiling, so the quote bounds it.
    assert opener.bodies[-1]["max_tokens"] == CHECK_SETTINGS["max_output_tokens"]


def test_inference_check_refusals_name_key_or_model(tmp_path):
    path = key_file(tmp_path)
    unlisted = Opener(
        {"https://api.engy.ai/v1/models": (200, {"data": [{"id": "other"}]})}
    )
    with pytest.raises(SetupRefused) as refused:
        LiveChecks(opener=unlisted).inference(
            "engy-chat", "deepseek-v4-flash-0731", path
        )
    assert refused.value.field == "model_id"
    rejected = Opener({"https://api.openai.com/v1/models": (401, None)})
    with pytest.raises(SetupRefused) as refused:
        LiveChecks(opener=rejected).inference(
            "openai-responses", "gpt-5-mini-2025-08-07", path
        )
    assert refused.value.field == "key"
    assert rejected.sent[0][1]["Authorization"] == "Bearer " + KEY


@pytest.fixture
def server(tmp_path, state):
    controller = launchpad.Controller(tmp_path / "runs.sqlite3")
    server = launchpad.Server(
        controller,
        TOKEN,
        port=0,
        onboarding=Onboarding(),
        state_dir=state,
        setup_checks=Checks(),
    )
    attached = []
    server.setup.attach = lambda path: attached.append(path) or True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def call(server, method, path, body=None, token=TOKEN):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    headers = {"Host": server.authority}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    return response.status, json.loads(response.read())


def test_setup_over_the_loopback_server(tmp_path, server):
    status, body = call(server, "GET", "/api/v1/setup", token=None)
    assert (status, body["error"]) == (401, "authentication_required")
    status, body = call(server, "GET", "/api/v1/setup")
    assert status == 200 and body["registered_hotkey"] is None
    assert body["choices"]["compute"][0]["id"] == LOCAL_CPU

    status, body = call(
        server,
        "POST",
        "/api/v1/setup/inference",
        {
            "provider_id": "engy-chat",
            "model_id": "deepseek-v4-flash-0731",
            "key": KEY,
            "consent": CONSENT,
        },
    )
    assert status == 409 and body == {
        "error": "registration_not_confirmed",
        "field": "address",
    }

    status, body = call(server, "POST", "/api/v1/setup/begin", {"address": HOTKEY})
    assert status == 200 and body["registered_hotkey"] == HOTKEY
    status, body = call(
        server,
        "POST",
        "/api/v1/setup/compute",
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(tmp_path / "absent.json"),
            "analysis_image_manifest": str(tmp_path / "absent.json"),
        },
    )
    assert status == 409 and body["field"] == "image_manifest"
    assert "c03_worker_image.sh" in body["next_step"]
    status, body = call(
        server,
        "POST",
        "/api/v1/setup/inference",
        {
            "provider_id": "engy-chat",
            "model_id": "deepseek-v4-flash-0731",
            "key": KEY,
            "consent": CONSENT,
        },
    )
    assert status == 200 and KEY not in json.dumps(body)
    assert body["steps"]["inference"]["checked"] is True
    status, body = call(server, "POST", "/api/v1/setup/unknown", {})
    assert status == 404


def test_attach_loads_into_an_empty_seat_only(tmp_path, state, monkeypatch):
    controller = launchpad.Controller(tmp_path / "runs.sqlite3")
    server = launchpad.Server(controller, TOKEN, port=0, onboarding=Onboarding())
    try:
        built = []
        monkeypatch.setattr(
            runner.RunnerAdapter,
            "for_profile",
            classmethod(lambda cls, path, **_: built.append(path) or object()),
        )
        profile = state / "runner-profile.json"
        assert server.attach_profile(profile) is True
        assert server.attach_profile(profile) is True
        assert built == [profile]
        # An operator's profile, or another one, is never replaced.
        assert server.attach_profile(state / "other.json") is False
        assert server.research_profile == Path(profile)
    finally:
        server.server_close()


# --- The Agent step asks the miner's own signer (external signing, #445). ---


def test_the_agent_step_takes_no_hotkey_file_or_password(tmp_path, state):
    made = files(tmp_path)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    setup.begin({"address": HOTKEY})
    for field, extra in (
        ("hotkey_file", made["operator.json"]),
        ("password", "fixture-password-never-accepted"),
    ):
        with pytest.raises(SetupRefused) as refused:
            setup.agent(
                {
                    "choice": AUTONOMOUS,
                    "operator_config": made["operator.json"],
                    field: extra,
                }
            )
        assert refused.value.field == field


def test_a_password_left_by_an_earlier_page_is_removed(tmp_path, state):
    made = files(tmp_path)
    checks = Checks()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    setup.begin({"address": HOTKEY})
    stale = state / "environment" / "miner-password"
    stale.write_text("an old password")
    socket = str(tmp_path / "signer.sock")
    setup.agent(
        {
            "choice": AUTONOMOUS,
            "operator_config": made["operator.json"],
            "signer_socket": socket,
        }
    )
    assert not stale.exists()
    assert checks.calls[-1] == ("agent", HOTKEY, Path(socket))
    agent = setup._record()["agent"]
    assert agent["paths"]["signer_socket"] == socket


def _signer_keys():
    pytest.importorskip("bittensor")
    from bittensor.keyfiles import Keypair

    return Keypair.create_from_uri("//Alice"), Keypair.create_from_uri("//Bob")


def test_the_live_agent_check_reaches_a_real_signer_for_the_hotkey():
    from tests.cpu._signer_harness import in_thread_signer

    alice, _ = _signer_keys()
    with in_thread_signer(alice) as signer:
        check = LiveChecks().agent(alice.ss58_address, signer._path)
    assert check == {"signing": "carbon-miner-signer holds the registered hotkey"}


def test_a_signer_refusal_names_the_signer_and_how_to_start_it(tmp_path):
    from tests.cpu._signer_harness import in_thread_signer

    alice, bob = _signer_keys()
    with in_thread_signer(alice) as signer, pytest.raises(SetupRefused) as wrong:
        LiveChecks().agent(bob.ss58_address, signer._path)
    assert wrong.value.field == "signer"
    assert wrong.value.code == "signer_wrong_hotkey"
    assert wrong.value.next_step == SIGNER_STEP
    with pytest.raises(SetupRefused) as absent:
        LiveChecks().agent(alice.ss58_address, tmp_path / "nobody.sock")
    assert absent.value.field == "signer"
    assert absent.value.code == "signer_not_running"
    assert "carbon-miner-signer" in absent.value.next_step
