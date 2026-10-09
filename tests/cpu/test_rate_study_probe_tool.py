"""SUBMISSION-RATE-STUDY-01's G-sealed probe tool and the scripted prober as
VALIDATOR-30's runner calls it (run sheet D.3; consumer contract #876).

Claims tested:
- every ordinary role's manifest, and its digest, is unchanged: only the
  study Constructor offers `rate_study_next_probe`, and only it records a
  study;
- a study role exists only for the Constructor in a registered study;
- the study toolbox answers the probe from the session's own history,
  exactly as the scripted prober would; the ordinary Constructor's toolbox
  refuses it; malformed and protected-material requests are refused;
- a REPEATED answer visits its recipe, so it is never proposed again;
- `ContractProber` (`propose(feedback)`) proposes what `Prober` does, and the
  S-revealed prober accepts the batch score alone;
- a study brief records its study and the study role's manifest; an ordinary
  brief is exactly as before.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from carbon.agent_campaign.graphite import roles, tools
from carbon.agent_campaign.graphite import study_prober as sp

STUDY = "SUBMISSION-RATE-STUDY-01"
#: The Constructor's manifest digests before the study tool existed.
CONSTRUCTOR_V1 = "sha256:25fecea50643cee04f9ab535164a52d8c09fc4b20a2dce1a7fcbffcc6275f999"
CONSTRUCTOR_V2 = "sha256:2794e2f73e9adee8f0e6884f54c17832ab1ae302ad54c8583c9e66cb689112e4"


def study_constructor():
    return roles.study_role(roles.RoleName.CONSTRUCTOR, STUDY)


def call(role, arguments, name=roles.STUDY_PROBE):
    events = []
    box = tools.GraphiteToolbox(
        role=role, literature_index=None, emit=lambda *a: events.append(a)
    )
    return asyncio.run(box.call(name, arguments, "probe-1")), events


def history(n, view=None):
    prober = sp.Prober(sp.SEALED)
    for _ in range(n):
        prober.propose()
        prober.observe(view or {"state": "SCORED"})
    return prober


# -- manifests -------------------------------------------------------------------------
def test_ordinary_roles_are_unchanged_and_never_offer_the_probe():
    constructor = roles.ROLES[roles.RoleName.CONSTRUCTOR]
    assert constructor.manifest_digest(roles.TOOL_TEXT_V1) == CONSTRUCTOR_V1
    assert constructor.manifest_digest(roles.TOOL_TEXT_V2) == CONSTRUCTOR_V2
    for role in roles.ROLES.values():
        assert roles.STUDY_PROBE not in role.tools
        assert role.study is None and "study" not in role.record(roles.TOOL_TEXT_V2)
    assert roles.STUDY_PROBE in roles.TOOL_REGISTRY


def test_the_study_constructor_adds_only_the_probe_and_records_its_study():
    base = roles.ROLES[roles.RoleName.CONSTRUCTOR]
    role = study_constructor()
    assert role.tools == (*base.tools, roles.STUDY_PROBE)
    assert role.prompt == base.prompt and role.start_model == base.start_model
    assert role.record(roles.TOOL_TEXT_V2)["study"] == STUDY
    assert role.manifest_digest(roles.TOOL_TEXT_V2) != CONSTRUCTOR_V2
    assert roles.study_role(roles.RoleName.CONSTRUCTOR) is base


@pytest.mark.parametrize(
    ("name", "study"),
    [
        (roles.RoleName.CONSTRUCTOR, "SUBMISSION-RATE-STUDY-02"),
        (roles.RoleName.PLANNER, STUDY),
        (roles.RoleName.ATTACKER, STUDY),
    ],
)
def test_no_other_study_role_exists(name, study):
    with pytest.raises(ValueError):
        roles.study_role(name, study)


def test_a_role_offering_the_probe_without_a_study_is_refused():
    import dataclasses

    base = roles.ROLES[roles.RoleName.CONSTRUCTOR]
    with pytest.raises(ValueError):
        dataclasses.replace(base, tools=(*base.tools, roles.STUDY_PROBE))
    with pytest.raises(ValueError):
        dataclasses.replace(base, study=STUDY)


# -- the tool --------------------------------------------------------------------------
def test_the_study_toolbox_answers_as_the_scripted_prober_would():
    prober = history(5)
    result, _ = call(study_constructor(), {"history_json": json.dumps(prober.history)})
    assert result["status"] == "OK"
    assert result["strategy"] == prober.propose()


def test_the_ordinary_constructor_refuses_the_probe():
    constructor = roles.ROLES[roles.RoleName.CONSTRUCTOR]
    result, _ = call(constructor, {"history_json": "[]"})
    assert result["status"] == tools.REFUSED_MANIFEST


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({}, "probe_arguments"),
        ({"history_json": 1}, "probe_arguments"),
        ({"history_json": "[]", "extra": 1}, "probe_arguments"),
        ({"history_json": "not json"}, "probe_history_json"),
        ({"history_json": "{}"}, "probe_history_malformed"),
        ({"history_json": '[{"strategy": {}}]'}, "probe_history_malformed"),
        (
            {"history_json": " " * (sp.MAX_HISTORY_BYTES + 1)},
            "probe_history_too_large",
        ),
    ],
)
def test_a_malformed_probe_request_is_refused(arguments, code):
    result, _ = call(study_constructor(), arguments)
    assert result["status"] == "REFUSED_INVALID_REQUEST"
    assert result["reason_code"] == code


def test_a_probe_naming_protected_material_is_refused():
    marker = sorted(tools.PROTECTED_MARKERS)[0]
    result, _ = call(study_constructor(), {"history_json": json.dumps([marker])})
    assert result["status"] == tools.REFUSED_PROTECTED


def test_a_repeated_answer_is_never_proposed_again():
    first = sp.next_probe(sp.SEALED, [])
    again = sp.next_probe(
        sp.SEALED, [{"strategy": first, "view": {"state": sp.REPEATED}}]
    )
    assert again != first
    same = sp.next_probe(
        sp.SEALED, [{"strategy": first, "view": {"state": "UNAVAILABLE"}}]
    )
    assert same == first


# -- the contract prober ---------------------------------------------------------------
def test_the_contract_prober_proposes_what_the_prober_does():
    contract, plain = sp.sealed(), sp.Prober(sp.SEALED)
    feedback = None
    for _ in range(20):
        proposed = contract.propose(feedback)
        assert proposed == plain.propose()
        feedback = {"state": "SCORED"}
        plain.observe(feedback)
    with pytest.raises(sp.ProberRefused):
        contract.propose(None)


def test_the_revealed_contract_prober_takes_the_batch_score_alone():
    contract = sp.revealed()
    first = contract.propose()
    second = contract.propose(0.25)
    assert first != second
    assert contract.prober.history[0]["view"] == {
        "state": "SCORED",
        "batch_score": 0.25,
    }


# -- briefs (the provider imports POSIX-only modules) ----------------------------------
def test_a_study_brief_records_its_study_and_an_ordinary_brief_does_not():
    pytest.importorskip("fcntl")
    from carbon.agent_campaign.graphite.provider import SessionBrief

    common = {
        "role": roles.RoleName.CONSTRUCTOR,
        "initial_observation": {"challenge": "x"},
        "checkout_commit": "0" * 40,
        "checkout_manifest_digest": "sha256:" + "0" * 64,
    }
    ordinary = SessionBrief(**common).document()
    assert "study" not in ordinary
    assert ordinary["tool_manifest_digest"] == CONSTRUCTOR_V2
    studied = SessionBrief(**common, study=STUDY).document()
    assert studied["study"] == STUDY
    assert studied["tool_manifest_digest"] == study_constructor().manifest_digest(
        roles.TOOL_TEXT_V2
    )
    with pytest.raises(ValueError):
        SessionBrief(**common, study="SUBMISSION-RATE-STUDY-02")
