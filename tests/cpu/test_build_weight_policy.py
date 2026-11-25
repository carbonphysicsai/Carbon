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


# -- from the exam registry's launch rows (owner G-LEAD-100) -------------------------------------------------------------

LIVE_RECORD = "sha256:cbd0a566f1f3e90d8c0d7e9cdf78b90359ba265344abdeb5f25433335e259235"


def row(state="launched", *packs, record=RECORD):
    return {
        "state": state,
        "qualified_sealed": {
            "record_sha256": record,
            "evaluation_pack_digests": list(packs or (OTHER_PACK,)),
        },
    }


MOTOR18 = row("launched", LIVE_PACK, record=LIVE_RECORD)


def dry(rows, version="synthetic-v1"):
    return builder.dry_run(BASE, version, rows=rows, registered=REGISTERED)


def test_the_exam_paid_today_alone_gives_the_policy_of_today():
    base = json.loads((wd.POLICY_DIR / f"{BASE}.json").read_bytes())
    out = dry({(MOTOR, "1.8"): MOTOR18})
    made = out["document"]
    assert {k for k in base if made[k] != base[k]} == {"version", "membership_note"}
    assert out["joins"] == [] and out["share_q12"] == out["share_q12_before"] == Q12
    assert (
        out["digest"] == builder.digest(made)
        and builder.RULE in made["membership_note"]
    )


def test_an_exam_joins_at_its_launch_for_an_equal_share(tmp_path):
    rows = {
        (JOINT, "0.1"): row(),
        (MOTOR, "1.8"): MOTOR18,
        (BRACKET, "2.0"): row("launched", NEW_PACK),
    }
    out = dry(rows)
    policy = load(tmp_path, out["document"])
    assert policy.challenges == (MOTOR, BRACKET, JOINT)
    assert out["joins"] == [BRACKET, JOINT]
    assert policy.share == out["share_q12"] == Q12 // 3
    assert out["burned_dust_q12"] == Q12 - 3 * (Q12 // 3)
    assert policy.qualified_packs(BRACKET) == frozenset({NEW_PACK})
    # the order of the rows is not an input
    assert dry(dict(reversed(rows.items()))) == out


def test_two_launched_versions_of_one_exam_are_one_share_and_both_packs(tmp_path):
    rows = {
        (MOTOR, "1.8"): MOTOR18,
        (MOTOR, "1.9"): row("launched", NEW_PACK, record=LIVE_RECORD),
    }
    policy = load(tmp_path, dry(rows)["document"])
    assert policy.challenges == (MOTOR,) and policy.share == Q12
    assert policy.qualified_packs(MOTOR) == frozenset({LIVE_PACK, NEW_PACK})


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        ({}, f"base_challenge_has_no_launch_row:{MOTOR}"),
        ({(JOINT, "0.1"): row()}, f"base_challenge_has_no_launch_row:{MOTOR}"),
        # what a retired exam's king is paid meanwhile is the owner's word, not given
        (
            {
                (MOTOR, "1.8"): row("retired", LIVE_PACK, record=LIVE_RECORD),
                (JOINT, "0.1"): row(),
            },
            f"retired_king_undecided:{MOTOR}",
        ),
        # one version retired while another is launched: its king's pack is never dropped silently
        (
            {
                (MOTOR, "1.8"): row("retired", LIVE_PACK, record=LIVE_RECORD),
                (MOTOR, "1.9"): row("launched", NEW_PACK, record=LIVE_RECORD),
            },
            "live_pack_dropped",
        ),
        (
            {(MOTOR, "1.8"): MOTOR18, (MOTOR, "1.9"): row("launched", NEW_PACK)},
            f"launched_records_differ:{MOTOR}",
        ),
        (
            {(MOTOR, "1.8"): MOTOR18, ("no-such", "1.0"): row()},
            "open_challenge_unregistered",
        ),
    ],
)
def test_rows_that_would_pay_wrong_are_refused(rows, code):
    with pytest.raises(builder.PolicyRefused) as refused:
        dry(rows)
    assert refused.value.code == code


def test_a_retired_exam_the_base_does_not_pay_stays_out(tmp_path):
    rows = {(MOTOR, "1.8"): MOTOR18, (BRACKET, "1.7"): row("retired")}
    assert load(tmp_path, dry(rows)["document"]).challenges == (MOTOR,)


def test_the_dry_run_writes_nothing_and_no_row_is_committed(capsys, monkeypatch):
    before = {p.name: p.read_bytes() for p in wd.POLICY_DIR.iterdir() if p.is_file()}
    assert builder.launch_rows() == {}  # the committed registry launches nothing
    monkeypatch.setattr(
        builder, "launch_rows", lambda registry=None: {(MOTOR, "1.8"): MOTOR18}
    )
    builder.main(["--from-registry", BASE, "synthetic-v1"])
    printed = json.loads(capsys.readouterr().out)
    assert printed["document"]["challenges"] == [MOTOR]
    assert printed["dry_run"].startswith("nothing is written")
    after = {p.name: p.read_bytes() for p in wd.POLICY_DIR.iterdir() if p.is_file()}
    assert after == before


def test_a_refused_or_unregistered_row_stops_the_dry_run(monkeypatch):
    from carbon.challenge_registry import exam_registry

    monkeypatch.setattr(exam_registry, "_REFUSED", {"zz-joint 0.1": "unknown_field: x"})
    with pytest.raises(builder.PolicyRefused) as refused:
        builder.launch_rows()
    assert refused.value.code == "exam_row_refused:zz-joint 0.1"
    monkeypatch.setattr(exam_registry, "_REFUSED", {})
    monkeypatch.setattr(
        exam_registry, "_ROWS", {("zz-joint", "0.1"): ({"launch": row()}, "d")}
    )
    with pytest.raises(builder.PolicyRefused) as refused:
        builder.launch_rows()
    assert refused.value.code == "launched_version_unregistered:zz-joint 0.1"


def test_no_code_that_pays_reads_the_launch_rows():
    for path in sorted((wd.POLICY_DIR.parent).glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "exam_registry" not in text and "build_weight_policy" not in text, path


def test_a_printed_file_is_no_policy_without_its_registry_line(tmp_path):
    """Put in place by hand it still loads as nothing, and the current policy stays what it was."""
    directory = tmp_path / "weight_policies"
    shutil.copytree(wd.POLICY_DIR, directory)
    made = dry({(MOTOR, "1.8"): MOTOR18, (JOINT, "0.1"): row()})["document"]
    (directory / "synthetic-v1.json").write_bytes(builder.render(made))
    with pytest.raises(wd.RewardFailure) as refused:
        wd.load_policy("synthetic-v1", directory)
    assert "WEIGHT_POLICY_UNREADABLE" in str(refused.value)
    assert wd.load_policy(None, directory) == wd.load_policy()
    # nor under a registered name: its digest is another
    (directory / f"{BASE}.json").write_bytes(builder.render(made))
    with pytest.raises(wd.RewardFailure) as refused:
        wd.load_policy(BASE, directory)
    assert "WEIGHT_POLICY_ALTERED" in str(refused.value)
