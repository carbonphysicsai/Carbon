"""GRAPHITE-D35: the phase-4 Attacker opens with its model's whole context.

Owner, 2026-10-05, relayed by the Test Lead: "yes for attacker budget", with
GRAPHITE-D34 (the Constructor's whole context) as the precedent. The
mechanism is D34's own: `roles.MODEL_SETTINGS` keyed by role, read by
`GraphiteProvider._selection`.

Claims tested:
- a new Attacker session no longer opens at `DEFAULT_SETTINGS` (65,536); on
  its starting model, glm-5.2, it gets 262,144 input tokens, the 600 s
  timeout and `engy-chat`, the route that reports each call's charge; every
  rung gets its own window;
- a model with no recorded context is refused before anything opens;
- every other role is unchanged: only the Constructor and the Attacker are
  named, and the rest keep `DEFAULT_SETTINGS`;
- a session recorded before this change resumes from every crash point with
  the settings it recorded and replays byte-identically (invariant 10);
- the grant's money cap still binds at the whole window: the run's token
  allowance holds exactly as many full reservations as fit, and a kimi-k3
  session, whose one call reserves more than the allowance, stops typed
  before its first call;
- the dry run and `phase4 prelive` print the `attacker_model` block;
- a mutation per guard: switching each protection off fails its test.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from decimal import Decimal

import pytest
from test_graphite_phase4 import (  # the stand-in's material: an autouse fixture
    StandIn,
    _stand_in_material,  # noqa: F401
    _synthetic_adapter,
    stand_in_modules,
)
from test_graphite_phase4_prelive import _committed_by_digest, _gate, _grant_copy

from carbon.agent_campaign.controller import SimulatedCrash
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import phase3, phase4, roles
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.pods import ScriptedPods
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.model_provider import (
    DEFAULT_SETTINGS,
    ENGY_LADDER,
    select,
)
from carbon.development_session.profile import digest
from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS
from carbon.development_session.research_tools import PREFIX
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

SCORING = challenge_scoring.scoring_for(BATTERY_CHALLENGE)
KEY = phase4.session_key(1)
#: Each rung's whole window: Engy's published context, at most 1,048,576.
WINDOWS = {
    "deepseek-v4-flash-0731": 1048576,
    "qwen3.8-27b": 1001536,
    "glm-5.3-flash": 262144,
    "glm-5.2": 262144,
    "kimi-k3": 1048576,
}
WHOLE = {
    "max_input_tokens": 262144,
    "max_output_tokens": 4096,
    "reasoning_effort": "low",
    "timeout_seconds": 600,
}
#: One glm-5.2 call at its whole window and the Attacker's 4,096-token output
#: cap (GRAPHITE-ATTACKER-STOP-RULE-01): 262,144 x 680 + 4,096 x 1,500 nano.
GLM_RESERVATION_NANO = 262144 * 680 + 4096 * 1500
PROBE = tool(PREFIX + "get_challenge_info", {})


def _grant():
    # Battery's phase-4 grant, as the per-Challenge registry names it.
    entry = phase4.PHASE4_GRANTS[BATTERY_CHALLENGE]
    document = json.loads((phase4.REPOSITORY / entry.grant_file).read_bytes())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def _provider(root, model, **kwargs):
    # A fixed clock and randomness, so a resumed run writes the same bytes.
    kwargs.setdefault("clock", lambda: 1000.0)
    kwargs.setdefault("randomness", lambda n: b"\x01" * n)
    return phase4.AttackerProvider(
        root=root / "graphite",
        grant=_grant(),
        model=model,
        pods=ScriptedPods(),
        adapter=StandIn(),
        scoring=SCORING,
        **kwargs,
    )


def _on_rung(provider, model_id):
    provider.ladder.model = lambda role: model_id
    provider.ladder.rung = lambda role: ENGY_LADDER.index(model_id)
    return provider


def _open(provider):
    """Open (not run) Attacker session 1; returns its run id."""
    brief = phase4.session_brief(provider.adapter, checkout_commit="0" * 40)
    spec = TaskSpec(
        campaign_id=phase4.CAMPAIGN,
        role=ROLES[RoleName.ATTACKER].boundary.value,
        workspace_id=phase4.WORKSPACE,
        credential_ref=phase4.CREDENTIAL_REF,
        profile_digest="sha256:" + "a" * 64,
        instructions_digest=provider.register_brief(brief),
        max_runtime_s=provider.grant.max_runtime_s,
    )
    return provider.start(spec, KEY).provider_run_id


def _opened(provider, run_id):
    return json.loads((provider._dir(run_id) / "session-open.json").read_bytes())


def _state(provider, run_id):
    return json.loads((provider._dir(run_id) / "state.json").read_bytes())


# -- the window ------------------------------------------------------------------------------
def test_an_attacker_session_opens_with_its_models_whole_context_on_engy_chat(
    tmp_path,
):
    """The Attacker no longer runs at `DEFAULT_SETTINGS`: on glm-5.2, its
    starting model, it opens with 262,144 input tokens and the 600 s timeout,
    on the route that reports each call's charge."""
    provider = _provider(tmp_path, ScriptedModel([]))
    opened = _opened(provider, _open(provider))
    assert ROLES[RoleName.ATTACKER].start_model == opened["role"]["model"] == "glm-5.2"
    assert opened["model"]["provider_id"] == phase3.ADAPTER == "engy-chat"
    assert opened["model"]["settings"] == WHOLE
    assert DEFAULT_SETTINGS.max_input_tokens == 65536
    assert opened["model"]["settings"] != DEFAULT_SETTINGS.record()


def test_every_rung_gives_the_attacker_its_own_whole_window(tmp_path):
    """Escalation selects again per rung, so each rung gets its own window;
    the admission ceiling keeps a request plus its output inside the model's
    context."""
    provider = _provider(tmp_path, ScriptedModel([]))
    assert tuple(WINDOWS) == ENGY_LADDER
    for model_id, window in WINDOWS.items():
        settings = provider._selection(model_id, RoleName.ATTACKER).settings
        assert (settings.max_input_tokens, settings.timeout_seconds) == (window, 600)
        assert settings.max_output_tokens == roles.ATTACKER_MAX_OUTPUT_TOKENS
        assert roles.ATTACKER_MAX_OUTPUT_TOKENS == CONTEXT_RESERVE_TOKENS
        assert window - CONTEXT_RESERVE_TOKENS + settings.max_output_tokens <= (
            roles.ENGY_CONTEXT_TOKENS[model_id]
        )


def test_an_unlisted_model_is_refused_before_anything_opens(tmp_path, monkeypatch):
    """Fail closed, as in GRAPHITE-D34: no window is invented for a model the
    context table does not list."""
    monkeypatch.setattr(
        gp, "MODEL_SETTINGS", {**roles.MODEL_SETTINGS, RoleName.ATTACKER: {}}
    )
    provider = _provider(tmp_path, ScriptedModel([]))
    with pytest.raises(ProviderUnavailable, match="model_context_not_recorded"):
        _open(provider)
    run_id = provider.run_id_for(KEY)
    assert not (provider._dir(run_id) / "session-open.json").exists()


def test_every_other_role_keeps_default_settings(tmp_path):
    """Only the Constructor and the Attacker are named; every other role's
    selection is exactly `DEFAULT_SETTINGS` on every rung."""
    assert set(gp.MODEL_SETTINGS) == {RoleName.CONSTRUCTOR, RoleName.ATTACKER}
    assert gp.MODEL_SETTINGS[RoleName.CONSTRUCTOR] == {
        model: {"max_input_tokens": window, "timeout_seconds": 600}
        for model, window in WINDOWS.items()
    }
    provider = _provider(tmp_path, ScriptedModel([]))
    others = [role for role in RoleName if role not in roles.WHOLE_CONTEXT_ROLES]
    assert others == [
        RoleName.PLANNER,
        RoleName.OPTIMIZER,
        RoleName.READER,
        RoleName.WRITER,
    ]
    for role in others:
        for model_id in ENGY_LADDER:
            settings = provider._selection(model_id, role).settings
            assert settings.record() == DEFAULT_SETTINGS.record(), (role, model_id)


# -- a recorded session keeps its settings (invariant 10) -------------------------------------
def _before_d35(root, model, **kwargs):
    """A session opened as the code before GRAPHITE-D35 opened it: engy-chat
    at `DEFAULT_SETTINGS`. Returns (provider, run id)."""
    provider = _provider(root, model, **kwargs)
    without = {
        role: table
        for role, table in roles.MODEL_SETTINGS.items()
        if role is not RoleName.ATTACKER
    }
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(gp, "MODEL_SETTINGS", without)
        return provider, _open(provider)


def _digests(provider, run_id):
    folder = provider._dir(run_id)
    return (
        digest((folder / "session-open.json").read_bytes()),
        digest((folder / "ledger" / "epoch-1" / "plan.json").read_bytes()),
        provider.session_record_digest(run_id),
    )


def test_a_session_recorded_before_d35_resumes_with_its_recorded_settings(tmp_path):
    """Prospective: a session opened at 65,536 tokens and 120 s resumes, from
    every crash point, on a provider that opens new Attacker sessions at the
    whole window, keeps the settings it recorded and writes exactly the bytes
    an uninterrupted run wrote. No reply is resent."""
    script = [PROBE, PROBE, text("done")]
    reference, reference_run = _before_d35(
        tmp_path / "reference", ScriptedModel(script)
    )
    assert reference.run(reference_run) == "succeeded"
    pinned = _digests(reference, reference_run)
    assert _opened(reference, reference_run)["model"]["settings"] == (
        DEFAULT_SETTINGS.record()
    )
    points = reference._checkpoints
    assert points >= 4
    for point in range(1, points + 1):
        root = tmp_path / f"crash-{point:02d}"
        model = ScriptedModel(script)
        crashed, run_id = _before_d35(root, model, crash_at_checkpoint=point)
        with pytest.raises(SimulatedCrash):
            crashed.run(run_id)
        resumed = _provider(root, ScriptedModel([]))
        resumed.model = model
        # A new session on this provider would open at the whole window.
        assert resumed._selection("glm-5.2", RoleName.ATTACKER).settings.record() == (
            WHOLE
        )
        assert resumed.run(run_id) == "succeeded", point
        assert len(model.requests) == 3, point
        assert _digests(resumed, run_id) == pinned, point
        opened = _opened(resumed, run_id)
        assert opened["model"]["settings"] == DEFAULT_SETTINGS.record(), point


# -- the money cap still binds -----------------------------------------------------------------
def test_the_token_allowance_still_binds_at_the_whole_window(tmp_path):
    """The grant's per-run cap is unchanged. Each glm-5.2 call reserves USD
    0.18132992 at the whole window, which fits the battery Attacker's 1.93
    token allowance ten times. With no charge reported every call keeps its
    full reservation, so the eleventh is never admitted: the run stops on the
    money cap after exactly ten calls."""
    model = ScriptedModel([PROBE] * 12 + [text("never sent")], charged_micro=None)
    provider = _provider(tmp_path, model)
    reservation = provider._selection("glm-5.2", RoleName.ATTACKER).reservation_nano
    assert reservation == GLM_RESERVATION_NANO == 184401920
    allowance = provider.budget.token_allowance_usd
    assert str(allowance) == "1.93"
    fits = int(allowance * 10**9) // reservation
    assert fits == 10
    run_id = _open(provider)
    assert provider.run(run_id) == "failed"
    assert _state(provider, run_id)["failure"] == {
        "code": "run_cap_reached",
        "dimension": "provider_nanodollars",
    }
    assert len(model.requests) == fits
    assert provider._tokens_usd(run_id) <= allowance


def test_a_kimi_k3_attacker_session_stops_typed_before_its_first_call(tmp_path):
    """One kimi-k3 call at its whole window reserves USD 2.0647, more than
    the Attacker's 1.93 token allowance: never admitted. Nothing is sent and
    nothing is spent; no grant amount is raised."""
    model = ScriptedModel([text("never sent")])
    provider = _on_rung(_provider(tmp_path, model), "kimi-k3")
    reservation = provider._selection("kimi-k3", RoleName.ATTACKER).reservation_nano
    assert reservation == 1048576 * 1950 + 4096 * 9750 == 2084659200
    assert reservation > 1930000000 == provider.caps()["provider_nanodollars"]
    run_id = _open(provider)
    assert provider.run(run_id) == "failed"
    assert _state(provider, run_id)["failure"] == {
        "code": "run_cap_reached",
        "dimension": "provider_nanodollars",
    }
    assert model.requests == []
    assert provider._tokens_usd(run_id) == 0


# -- the evidence: dry run and prelive print the block ----------------------------------------
ATTACKER_MODEL = {
    "provider_id": "engy-chat",
    "model": "glm-5.2",
    "max_input_tokens": 262144,
    "admission_ceiling_tokens": 258048,
    "max_output_tokens": 4096,
    "timeout_seconds": 600,
    "reservation_usd": "0.18440192",
    "token_allowance_usd": "1.93",
    "calls_at_full_reservation": 10,
    "reservation_fits_token_allowance": True,
}


def test_the_dry_run_prints_the_attacker_model_block(tmp_path, monkeypatch):
    adapter = StandIn()

    def stub_side(store, control, provider, run_id, adapter, atk, **kw):
        return {"attack_knowledge": {"after": kw["view"].digest}}, {}, [], None

    monkeypatch.setattr(phase4, "carbon_side", stub_side)
    monkeypatch.setattr(phase4, "attack_modules", lambda: stand_in_modules(adapter))
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            [
                "run",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                BATTERY_CHALLENGE,
                "--dry-run",
            ]
        )
    assert code == 0
    body = out.getvalue()
    printed = json.loads(body[body.index('{\n "coverage"') :])
    assert printed["dry_run"]["attacker_model"] == ATTACKER_MODEL
    assert printed["dry_run"]["money_cap_usd"] == "1.93"


def test_prelive_prints_the_attacker_model_block(tmp_path, monkeypatch):
    """The release evidence: `phase4 prelive` reports the window, the
    admission ceiling, the timeout and the reservation per call, from the
    session record the gate's live-path session froze."""
    _committed_by_digest(monkeypatch, _grant_copy(tmp_path))
    _code, report = _gate(
        tmp_path, _synthetic_adapter(weak=False), phase4.attack_modules()
    )
    rows = {row["path"]: row for row in report["paths"]}
    assert rows["session_model_ledger_controller"]["status"] == "PASS"
    assert report["attacker_model"] == ATTACKER_MODEL
    assert Decimal(report["attacker_model"]["reservation_usd"]) == Decimal(
        GLM_RESERVATION_NANO
    ) / Decimal(10**9)
    # The same v2 report also names the accepted grant and its Challenge
    # (OWNER-GRAPHITE-TEST-WAVE-05 §3), beside the model block.
    assert report["schema"] == "carbon.graphite.phase4-prelive.v2"
    assert report["challenge"] == BATTERY_CHALLENGE
    assert report["grant"]["grant_id"] == "GRAPHITE-GRANT-PHASE4"
    assert report["grant"]["challenge"] == BATTERY_CHALLENGE


# -- a mutation per guard --------------------------------------------------------------------
def _without_attacker(m):
    m.setattr(
        gp,
        "MODEL_SETTINGS",
        {
            role: table
            for role, table in roles.MODEL_SETTINGS.items()
            if role is not RoleName.ATTACKER
        },
    )


def _lax_selection(self, model_id, role=None):
    """`_selection` that invents `DEFAULT_SETTINGS` for an unlisted model."""
    settings = gp.MODEL_SETTINGS.get(role, {}).get(model_id)
    return select(
        provider_id=self.adapter_id,
        model_id=model_id,
        credential={"kind": "file", "reference": self.model.credential_reference},
        settings=None if settings is None else dict(settings),
    )


def _reselect(record, *, credential_file=None):
    """A resume that re-selects from today's `MODEL_SETTINGS` instead of the
    selection the session record froze."""
    settings = roles.MODEL_SETTINGS[RoleName.ATTACKER][record["model"]]
    return select(
        provider_id=record["provider_id"],
        model_id=record["model"],
        credential={"kind": "file", "reference": credential_file},
        settings=dict(settings),
    )


def _reader_too(m):
    whole = roles.MODEL_SETTINGS[RoleName.ATTACKER]
    m.setattr(gp, "MODEL_SETTINGS", {**roles.MODEL_SETTINGS, RoleName.READER: whole})


#: name: (switch the protection off, the test that guards it). Each guard
#: takes (tmp_path, monkeypatch).
MUTATIONS = {
    # The Attacker is named in MODEL_SETTINGS: without it, 65,536.
    "attacker_whole_context": (
        _without_attacker,
        lambda tmp, mp: (
            test_an_attacker_session_opens_with_its_models_whole_context_on_engy_chat(
                tmp
            )
        ),
    ),
    # A model with no recorded context is refused, never defaulted.
    "unlisted_model_refused": (
        lambda m: m.setattr(gp.GraphiteProvider, "_selection", _lax_selection),
        test_an_unlisted_model_is_refused_before_anything_opens,
    ),
    # No other role gains the whole window.
    "other_roles_unchanged": (
        _reader_too,
        lambda tmp, mp: test_every_other_role_keeps_default_settings(tmp),
    ),
    # A resume rebuilds the recorded selection, never today's.
    "resume_keeps_recorded_settings": (
        lambda m: m.setattr(gp, "selection_from_record", _reselect),
        lambda tmp, mp: (
            test_a_session_recorded_before_d35_resumes_with_its_recorded_settings(tmp)
        ),
    ),
    # The run's token allowance is the session's money cap.
    "token_allowance_binds": (
        lambda m: m.setattr(phase3.Phase3Provider, "caps", gp.GraphiteProvider.caps),
        lambda tmp, mp: test_the_token_allowance_still_binds_at_the_whole_window(tmp),
    ),
    # Prelive's block is the selection the session record froze.
    "prelive_block_from_the_record": (
        _without_attacker,
        test_prelive_prints_the_attacker_model_block,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    (tmp_path / "intact").mkdir()
    (tmp_path / "mutated").mkdir()
    guard(tmp_path / "intact", monkeypatch)  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated", monkeypatch)
