"""The large-profile publication moved the construction-limits digest of every
allowlist-v7 version, and of no other (Validator ruling A+ on
PROOF_RUN_UNRESOLVED_CULPRIT_20261024.md; a pre-publish move, no new kit versions).

Old = rc22 8c90c831c, where the kits published today's profile. Putting that
profile back reproduces the old digest exactly, so the profile is the only field
that moved. The routes' agreement with the new digests is
test_published_policy_is_enforced."""

import pytest

from carbon.battery import construction_bundle_material as battery_material
from carbon.challenge_kit import physical_material, served_versions
from carbon.challenge_kit import version_registry as registry

MOVED = {
    ("battery-fastcharge-ageing-development-v1", "2.1"): (
        "8202e99b53ef09ff3b30bd68f352e7bde2b995a70e3808878a74a63cadc5c177",
        "fd00c106beb09b2d06c336fb36f0fc3aea0afe285b4181f0bb8037e8cfd5e200",
    ),
    ("chip-cold-plate", "1.2"): (
        "1b249c44ea5788dc32cb3319820cb36bce227351f91488c12c75c1bc46299a40",
        "f6bf90a17128e687a05c66be9baec2b0cfffbb8a794c433d6cf8f90c45d626f6",
    ),
    ("chip-cold-plate", "1.3"): (
        "2afcf9f956bba3b8d8122efe82b3ca4239ca13119f7f4f5bd9d4e0e343a75777",
        "ba4842de66f3745b6ad32545608d8bc86f78cb794fd4e2095b20b2101a8a9148",
    ),
    ("chip-cold-plate", "1.4"): (
        "19ef124c22c8533d781ac9add9527e911e534ebe322f64fd4ca23e93f639932c",
        "bf94ffc1d6008c5abb81203c3bd54c232f3b3a923e3ef93a19e9a8d57a0c547d",
    ),
    ("electric-motor-magnetics", "1.3"): (
        "a081ccac9ac9e93712a2047ac2abbb5c746ff8da4091d318916285f74e65ef89",
        "912b1bc71b830ddbfdb5368e7b8ddcc0de4bba0c6a8054f492b8efddaa349863",
    ),
    ("electric-motor-magnetics", "1.4"): (
        "43f3c2c3d9c7f3b6672cd59be012038526c4a937aa6fa1cc82ad3444eb365fa0",
        "3c3a854f4e035b70b542d91222b83d4bb3fcb674c60526f00bf51c3e3d3c4b78",
    ),
    ("f02", "2.2"): (
        "0d2358581a88c4ab6648fcfb41a139792e23fb988202b610f883d66838725a25",
        "1d6894f7880550b0d06c1ebd9cb1e093fc5ec4af21925cd88cd2ca95106a9b91",
    ),
    ("f02", "2.3"): (
        "4a7a5cf5826abf5b872b6db1ddd67b06d1f85b7217be492732180181490010d9",
        "8f7c043dc8a69eff83e181868b3b60c3603da8f8c5b9ec3b9568dfb5c4cf8ebf",
    ),
    ("f02", "2.4"): (
        "827e396bfe19d2ee162482f48d22150ee2894af1622d5778a55630644594e5f1",
        "10836cbdd3a266cd73152c27e980e8f2e7db191bd3077b8b0bcd06321c34c281",
    ),
    ("f08-ribbed-bracket", "1.3"): (
        "c0d3bf0691f22090088d77f441f7bb9da69557a3314c6add8bb6c673922c2217",
        "58a1fceb1941bb249e6d32aa516de9e3890565830265e94c52b9e160e6b7dac7",
    ),
    ("f08-ribbed-bracket", "1.4"): (
        "31dc6f822bfed31d02d032d11b150c32a2bb01210d2e42453ae896af2172cfa3",
        "746a0666ee74c51d2fbfdb9667a090ca90bf8f3a86b16e8a5d823d146c91730f",
    ),
    ("f08-ribbed-bracket", "1.5"): (
        "9ada93ee419c2adbe91e7e8aae8176f35e2d60b11484ad9e9814b772ae4cf63b",
        "2c54ee8493a87bb2f04bf6deabf85d18f865a917165f8df92943c90d24f698cf",
    ),
}


def _digest(challenge_id, version):
    if challenge_id == battery_material.challenge.CHALLENGE.challenge_id:
        material = battery_material.versioned_material(version)
    else:
        material = physical_material.bundle_material(challenge_id, version)
    return material["construction_kit"]["construction_limits_digest"]


def test_exactly_the_v7_versions_moved():
    assert set(MOVED) == registry.keys(allowlist="v7")


@pytest.mark.parametrize(("challenge_id", "version"), sorted(MOVED))
def test_a_v7_version_moved_by_its_resource_profile_alone(
    challenge_id, version, monkeypatch
):
    old, new = MOVED[(challenge_id, version)]
    assert _digest(challenge_id, version) == "sha256:" + new
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    assert _digest(challenge_id, version) == "sha256:" + old


def test_every_other_version_keeps_its_bytes(monkeypatch):
    current = {
        key: _digest(*key) for key in sorted(registry.VERSIONS) if key not in MOVED
    }
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    assert current == {key: _digest(*key) for key in current}
