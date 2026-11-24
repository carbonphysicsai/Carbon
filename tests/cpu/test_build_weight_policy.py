"""The weight policy builder (owner G-LEAD-67 / 68: a share for each OPEN exam, split equally; Lead 6357: a generated,
digest-pinned file). Every pack digest, record and version here is a synthetic fixture; no policy is registered.
"""

import copy
import json
import shutil

import pytest

from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import Q12
from scripts.dev import build_weight_policy as builder

MOTOR, BRACKET, JOINT = "electric-motor-magnetics", "f08-ribbed-bracket", "zz-joint"
BASE = "mainnet-winner-v4"
LIVE_PACK = "sha256:ee2348b1738fb13984601473b5624bfefc2f65d8c7c7e91471c2d4c419a5742c"
NEW_PACK, OTHER_PACK = "sha256:" + "1" * 64, "sha256:" + "2" * 64
RECORD = "sha256:" + "a" * 64
REGISTERED = (MOTOR, BRACKET, JOINT)
NOW = 10**12


def spec(*opened, packs=(LIVE_PACK, NEW_PACK)):
    return {
        "version": "synthetic-v1",
        "membership_note": "synthetic",
        "open": list(opened),
        "qualified_sealed": {
            c: {
                "record_sha256": RECORD,
                "evaluation_pack_digests": list(packs) if c == MOTOR else [OTHER_PACK],
            }
            for c in opened
        },
    }


def build(document):
    return builder.build(BASE, document, registered=REGISTERED)


def load(tmp_path, document):
    """The built document through the real loader, pinned in a copy of the registry."""
    directory = tmp_path / "weight_policies"
    shutil.copytree(wd.POLICY_DIR, directory)
    (directory / f"{document['version']}.json").write_bytes(builder.render(document))
    registry = json.loads((directory / "registry.json").read_bytes())
    registry["versions"][document["version"]] = builder.digest(document)
    (directory / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return wd.load_policy(document["version"], directory)


def test_the_renderer_and_digest_are_the_registrys_own():
    raw = (wd.POLICY_DIR / f"{BASE}.json").read_bytes().replace(b"\r\n", b"\n")
    document = json.loads(raw)
    assert builder.render(document) == raw
    assert builder.digest(document) == wd.load_policy(BASE).digest


@pytest.mark.parametrize("opened", [(MOTOR,), (MOTOR, BRACKET), REGISTERED])
def test_each_open_exam_gets_an_equal_share_and_nothing_burns_for_an_unopened_one(
    tmp_path, opened
):
    policy = load(tmp_path, build(spec(*opened)))
    assert policy.challenges == opened and policy.share == Q12 // len(opened)
    winners = {c: wd.Winner(f"king-{i}", NOW) for i, c in enumerate(opened)}
    targets = wd.epoch_targets(policy, winners, NOW)
    assert set(targets["winners"].values()) == {Q12 // len(opened)}
    assert targets["burn"] == Q12 - len(opened) * (Q12 // len(opened))  # integer dust


def test_only_the_list_and_its_qualifications_differ_from_the_base(tmp_path):
    base = json.loads((wd.POLICY_DIR / f"{BASE}.json").read_bytes())
    made = build(spec(MOTOR, BRACKET))
    changed = {
        "version",
        "membership_note",
        "challenges",
        "baselines",
        "qualified_sealed",
    }
    assert set(made) == set(base)
    assert {k for k in base if made[k] != base[k]} == changed
    assert made["baselines"] == {MOTOR: None, BRACKET: None}


def test_both_motor_packs_are_payable_and_any_other_is_not(tmp_path):
    policy = load(tmp_path, build(spec(MOTOR)))

    def eligible(pack):
        promotion = {
            "model_id": "m",
            "hotkey": "hk",
            "previous": None,
            "previous_hotkey": None,
            "incumbent_reason": we.SEALED_TESTNET_REASON,
            "kind": we.FIRST,
            "evaluation_pack_digests": [pack],
        }
        return we.decide(policy, MOTOR, promotion, None, {"hk": "ck"}, NOW)["eligible"]

    assert eligible(LIVE_PACK) and eligible(NEW_PACK)
    assert not eligible(OTHER_PACK)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda s: s.update(extra=1), "spec_fields"),
        (lambda s: s.update(version=BASE), "version_already_registered"),
        (lambda s: s.update(membership_note=" "), "membership_note_missing"),
        (lambda s: s.update(open=[]), "open_list"),
        (lambda s: s.update(open=[MOTOR, MOTOR]), "open_list"),
        (lambda s: s.update(open=["no-such"]), "open_challenge_unregistered"),
        (lambda s: s.update(open=[MOTOR, BRACKET]), "open_challenge_not_qualified"),
        (
            lambda s: s["qualified_sealed"].update({BRACKET: {}}),
            "qualified_sealed_malformed",
        ),
        (
            lambda s: s["qualified_sealed"][MOTOR].update(
                evaluation_pack_digests=["HUMAN_INPUT"]
            ),
            "qualified_sealed_malformed",
        ),
        (
            lambda s: s["qualified_sealed"][MOTOR].update(
                evaluation_pack_digests=[NEW_PACK]
            ),
            "live_pack_dropped",
        ),
    ],
)
def test_a_spec_that_would_pay_wrong_is_refused(change, code):
    document = copy.deepcopy(spec(MOTOR))
    change(document)
    with pytest.raises(builder.PolicyRefused) as refused:
        build(document)
    assert refused.value.code == code
