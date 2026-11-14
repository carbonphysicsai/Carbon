"""OWNER-MAINNET-QUALIFIED-STANDING-01: a sealed-exam crown is paid off testnet only for a Challenge the policy
qualifies, and only when every pack it was graded on is one that qualification names."""

import contextlib
import hashlib
import json
import shutil
import sqlite3

import pytest

from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import RewardFailure

MOTOR, COOLING = "electric-motor-magnetics", "chip-cold-plate"
PACK = "sha256:ee2348b1738fb13984601473b5624bfefc2f65d8c7c7e91471c2d4c419a5742c"
OTHER_PACK = "sha256:" + "1" * 64
NOW = 10**12


def sealed_first(packs=(PACK,), hotkey="5Hk"):
    promotion = {
        "model_id": "m1",
        "hotkey": hotkey,
        "previous": None,
        "previous_hotkey": None,
        "recipe_digest": "sha256:" + "a" * 64,
        "contract_digest": "sha256:" + "b" * 64,
        "incumbent_reason": we.SEALED_TESTNET_REASON,
        "kind": we.FIRST,
    }
    if packs is not None:
        promotion["evaluation_pack_digests"] = list(packs)
    return promotion


def decide(policy, challenge, promotion):
    return we.decide(policy, challenge, promotion, None, {"5Hk": "5Ck"}, NOW)


def test_v3_qualifies_motor_on_its_pack_only_and_v1_v2_are_unchanged():
    v3 = wd.load_policy("mainnet-winner-v3")
    assert (v3.network, v3.netuid) == ("finney", 116)
    assert v3.qualified_packs(MOTOR) == frozenset({PACK})
    for other in ("chip-cold-plate", "f08-ribbed-bracket", "f02"):
        assert v3.qualified_packs(other) is None
    assert v3.share * 4 == wd.load_policy("mainnet-winner-v2").share * 4
    assert wd.load_policy("mainnet-winner-v2").digest == (
        "sha256:24a72e01bf2de06b163034bb0c952be0b77b353363a9e0749582641e068dc114"
    )
    assert wd.load_policy("mainnet-winner-v1").digest == (
        "sha256:a5b44f59c36b3a090bbd949aca3f9133a73b8ea97ab9ed5849f63a44f7ed1b93"
    )
    assert wd.load_policy("mainnet-winner-v2").qualified_packs(MOTOR) is None
    assert wd.load_policy().version == "testnet-winner-v1"


def test_v3_pins_the_owner_qualification_record_by_sha():
    v3 = wd.load_policy("mainnet-winner-v3")
    [(challenge, record_sha, packs)] = v3.qualified_sealed
    raw = (
        wd.POLICY_DIR.parents[2]
        / ".agent/decisions/2026-11-14-OWNER-MAINNET-QUALIFIED-STANDING-01.md"
    ).read_bytes()
    assert (challenge, packs) == (MOTOR, (PACK,))
    assert record_sha == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_a_qualified_sealed_crown_on_its_pack_is_paid_on_mainnet():
    out = decide(wd.load_policy("mainnet-winner-v3"), MOTOR, sealed_first())
    assert (out["eligible"], out["reason"]) == (True, "first_incumbent_no_baseline")


@pytest.mark.parametrize(
    ("policy", "challenge", "packs", "reason"),
    [
        ("mainnet-winner-v2", MOTOR, (PACK,), "sealed_crown_testnet_only"),
        ("mainnet-winner-v1", MOTOR, (PACK,), "sealed_crown_testnet_only"),
        ("mainnet-winner-v3", COOLING, (PACK,), "sealed_crown_testnet_only"),
        ("mainnet-winner-v3", MOTOR, (OTHER_PACK,), "sealed_crown_pack_not_qualified"),
        (
            "mainnet-winner-v3",
            MOTOR,
            (PACK, OTHER_PACK),
            "sealed_crown_pack_not_qualified",
        ),
        ("mainnet-winner-v3", MOTOR, (), "sealed_crown_pack_not_qualified"),
        ("mainnet-winner-v3", MOTOR, None, "sealed_crown_pack_not_qualified"),
    ],
)
def test_every_other_sealed_crown_still_burns_off_testnet(
    policy, challenge, packs, reason
):
    out = decide(wd.load_policy(policy), challenge, sealed_first(packs))
    assert (out["eligible"], out["reason"]) == (False, reason)


def test_testnet_pays_sealed_crowns_exactly_as_before():
    out = decide(wd.load_policy("testnet-winner-v5-launch"), MOTOR, sealed_first(None))
    assert (out["eligible"], out["reason"]) == (True, "first_incumbent_no_baseline")


def test_pack_digests_are_evidence_not_crown_identity():
    assert we.same_crown(sealed_first(None), sealed_first((PACK,)))
    assert not we.same_crown(sealed_first(None), sealed_first(None, hotkey="other"))


class _Store:
    def __init__(self, path):
        self.path = path

    @contextlib.contextmanager
    def db(self):
        connection = sqlite3.connect(self.path)
        try:
            yield connection
        finally:
            connection.close()


def test_crown_pack_digests_read_single_and_set_bindings(tmp_path):
    path = tmp_path / "pool.sqlite3"
    with sqlite3.connect(path) as c:
        c.execute(
            "CREATE TABLE operations (op_id TEXT, kind TEXT, state TEXT, body TEXT)"
        )
        rows = [
            ("m1", {"evaluation_pack_digest": PACK}),
            ("m1", {"batches": [{"evaluation_pack_digest": OTHER_PACK}, "junk"]}),
            ("m2", {"evaluation_pack_digest": "sha256:" + "2" * 64}),
        ]
        for i, (sub, evidence) in enumerate(rows):
            body = json.dumps({"submission_id": sub, "evidence": evidence})
            c.execute(
                "INSERT INTO operations VALUES (?, 'private_evaluation.v1', 'X', ?)",
                (str(i), body),
            )
        c.execute(
            "INSERT INTO operations VALUES ('9', 'private_evaluation.v1', 'X', 'not json')"
        )
    assert we._crown_pack_digests(_Store(path), "m1") == sorted([PACK, OTHER_PACK])
    assert we._crown_pack_digests(_Store(path), "absent") == []
    assert we._crown_pack_digests(object(), "m1") == []


def _copy_with_v3(tmp_path, mutate):
    directory = tmp_path / "policies"
    shutil.copytree(wd.POLICY_DIR, directory)
    document = json.loads((directory / "mainnet-winner-v3.json").read_text())
    mutate(document)
    (directory / "mainnet-winner-v3.json").write_text(json.dumps(document))
    registry = json.loads((directory / "registry.json").read_text())
    registry["versions"]["mainnet-winner-v3"] = (
        "sha256:" + hashlib.sha256(wd._canonical(document)).hexdigest()
    )
    (directory / "registry.json").write_text(json.dumps(registry))
    return directory


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(qualified_sealed={}),
        lambda d: d.update(qualified_sealed=[]),
        lambda d: d.update(
            qualified_sealed={"not-a-challenge": d["qualified_sealed"][MOTOR]}
        ),
        lambda d: d["qualified_sealed"][MOTOR].update(evaluation_pack_digests=[]),
        lambda d: d["qualified_sealed"][MOTOR].update(
            evaluation_pack_digests=[PACK, PACK]
        ),
        lambda d: d["qualified_sealed"][MOTOR].update(
            evaluation_pack_digests=["ee2348b1"]
        ),
        lambda d: d["qualified_sealed"][MOTOR].update(record_sha256="cbd0a566"),
        lambda d: d["qualified_sealed"][MOTOR].update(extra=1),
        lambda d: d["qualified_sealed"][MOTOR].pop("record_sha256"),
    ],
)
def test_a_malformed_qualification_refuses_the_policy(tmp_path, mutate):
    directory = _copy_with_v3(tmp_path, mutate)
    with pytest.raises(RewardFailure) as refused:
        wd.load_policy("mainnet-winner-v3", directory=directory)
    assert str(refused.value) == "WEIGHT_POLICY_MALFORMED"
