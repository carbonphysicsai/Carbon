"""Per-model output caps for the whole-context roles (OWNER 2026-10-13: "Max out the available tokens").

Claims tested:
- only kimi-k3 has a cap of its own (32,768) for the Constructor and the Attacker; every other ladder model keeps its
  role's cap (the Constructor's 2,048 default, the Attacker's 4,096 of GRAPHITE-ATTACKER-STOP-RULE-01);
- every model's cap plus the window the loop admits (the window less the 4,096 reserve) fits the model's recorded
  context, so a request cannot overflow it; the four models that open on their whole context cannot take 32,768;
- a cap listed for a model that does not fit is refused loudly, never silently applied or dropped;
- no cap is above the provider's recorded output maximum, and no window or timeout changed.
"""

from __future__ import annotations

import pytest

from carbon.agent_campaign.graphite import roles
from carbon.agent_campaign.graphite.roles import (
    ENGY_CONTEXT_TOKENS,
    MODEL_OUTPUT_CAPS,
    MODEL_SETTINGS,
    RoleName,
    model_settings_for,
    output_cap_fits,
)
from carbon.development_session.model_provider import (
    DEFAULT_SETTINGS,
    ENGY_LADDER,
    output_maximum,
)
from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS

CAP = 32768
HOLDS_WHOLE_CONTEXT = (
    "deepseek-v4-flash-0731",
    "qwen3.8-27b",
    "glm-5.3-flash",
    "glm-5.2",
)


def _cap(role, model):
    settings = MODEL_SETTINGS[role][model]
    return settings.get("max_output_tokens", DEFAULT_SETTINGS.max_output_tokens)


def test_only_kimi_k3_has_a_cap_of_its_own():
    assert MODEL_OUTPUT_CAPS == {"kimi-k3": CAP}
    for role in roles.WHOLE_CONTEXT_ROLES:
        assert _cap(role, "kimi-k3") == CAP
    for model in HOLDS_WHOLE_CONTEXT:
        assert (
            _cap(RoleName.CONSTRUCTOR, model)
            == DEFAULT_SETTINGS.max_output_tokens
            == 2048
        )
        assert (
            _cap(RoleName.ATTACKER, model) == roles.ATTACKER_MAX_OUTPUT_TOKENS == 4096
        )


@pytest.mark.parametrize("role", roles.WHOLE_CONTEXT_ROLES)
@pytest.mark.parametrize("model", ENGY_LADDER)
def test_a_request_the_loop_admits_plus_the_cap_fits_every_models_context(role, model):
    """The loop admits input under `max_input_tokens` less the 4,096 reserve; that plus the cap must fit the context
    the provider publishes. This is the check that keeps the four whole-context models at their safe caps.
    """
    settings = MODEL_SETTINGS[role][model]
    worst = settings["max_input_tokens"] - CONTEXT_RESERVE_TOKENS + _cap(role, model)
    assert worst <= ENGY_CONTEXT_TOKENS[model]
    # The window is untouched: the whole context, at most what `select` accepts (OWNER D34).
    assert settings["max_input_tokens"] == min(
        ENGY_CONTEXT_TOKENS[model], roles.SELECT_MAX_INPUT_TOKENS
    )
    assert settings["timeout_seconds"] == roles.CONSTRUCTOR_TIMEOUT_SECONDS == 600
    assert _cap(role, model) <= output_maximum("engy-chat", model)["max_output_tokens"]


def test_kimi_k3_fits_32768_with_35840_tokens_to_spare():
    context, window = (
        ENGY_CONTEXT_TOKENS["kimi-k3"],
        MODEL_SETTINGS[RoleName.CONSTRUCTOR]["kimi-k3"]["max_input_tokens"],
    )
    assert (context, window) == (1113088, 1048576)
    worst = window - CONTEXT_RESERVE_TOKENS + CAP
    assert worst == 1077248 and context - worst == 35840


def test_the_four_whole_context_models_cannot_take_32768_and_stay_loudly_refused():
    """Raising one of them would let a request overflow its context (an invalid request, which stops a campaign)."""
    assert [m for m in ENGY_LADDER if output_cap_fits(m, ENGY_CONTEXT_TOKENS, CAP)] == [
        "kimi-k3"
    ]
    for model in HOLDS_WHOLE_CONTEXT:
        assert not output_cap_fits(model, ENGY_CONTEXT_TOKENS, CAP)
        assert output_cap_fits(model, ENGY_CONTEXT_TOKENS, CONTEXT_RESERVE_TOKENS)


@pytest.mark.parametrize("model", HOLDS_WHOLE_CONTEXT)
def test_a_listed_cap_that_does_not_fit_is_refused(monkeypatch, model):
    monkeypatch.setattr(roles, "MODEL_OUTPUT_CAPS", {**MODEL_OUTPUT_CAPS, model: CAP})
    with pytest.raises(ValueError, match="output_cap_does_not_fit_context:" + model):
        model_settings_for(ENGY_CONTEXT_TOKENS)


def test_a_provider_whose_context_for_kimi_k3_is_smaller_is_refused_not_raised_silently():
    smaller = {**ENGY_CONTEXT_TOKENS, "kimi-k3": 1048576}
    with pytest.raises(ValueError, match="output_cap_does_not_fit_context:kimi-k3"):
        model_settings_for(smaller)


def test_the_hold_per_call_and_how_many_fit_in_the_shares():
    """kimi-k3's reservation: window x input price + cap x output price. 2.0646912 at 2,048, 2.3642112 now."""
    from carbon.development_session.model_provider import ENGY_MODELS

    price = ENGY_MODELS["kimi-k3"]
    window = MODEL_SETTINGS[RoleName.CONSTRUCTOR]["kimi-k3"]["max_input_tokens"]
    now = window * price.input_nano + CAP * price.output_nano
    before = window * price.input_nano + 2048 * price.output_nano
    assert (before, now) == (2064691200, 2364211200)
    for share_nano, holds_before, holds_now in (
        (10_990_000_000, 5, 4),
        (11_450_000_000, 5, 4),
    ):
        assert share_nano // before == holds_before
        assert share_nano // now == holds_now
