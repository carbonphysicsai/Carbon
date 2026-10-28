"""The large-profile publication moved the construction-limits digest of every
allowlist-v7 version, and of no other (Validator ruling A+ on
PROOF_RUN_UNRESOLVED_CULPRIT_20261024.md; a pre-publish move, no new kit versions).

Old = rc22 8c90c831c, where the kits published today's profile (the four graph route v2
versions re-pinned at the 648/947 wall, OWNER-REBUILD-WALL-11MIN-01). Putting that
profile back reproduces the old digest exactly, so the profile is the only field
that moved. MOVED is frozen publication history, not a list of all future
registrations. Later approved versions have a separate current-profile contract
below, with no invented rc22 identity. The routes' agreement with the new
digests is test_published_policy_is_enforced."""

import pytest
import rc43_surfaces

from carbon.battery import construction_bundle_material as battery_material
from carbon.challenge_kit import physical_material, served_versions
from carbon.challenge_kit import version_registry as registry
from carbon.development_session import bundle_construction_worker as bundle

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
        "a44c6b5a8ccceb41431adb73b7eedc3a9378df6f57e4c59c73e9bc1a103be2df",
        "afd16c41239081cef4a4447b6fc725d3506c72fb489ad79b13ffe0c7a7c930a0",
    ),
    ("electric-motor-magnetics", "1.3"): (
        "a081ccac9ac9e93712a2047ac2abbb5c746ff8da4091d318916285f74e65ef89",
        "912b1bc71b830ddbfdb5368e7b8ddcc0de4bba0c6a8054f492b8efddaa349863",
    ),
    ("electric-motor-magnetics", "1.4"): (
        "e15f5610fd997f7f43d3021281be22d39183a4575c71684d5804edff53663a1d",
        "a6c1c9f13bed863ae427caaf6898c311dbda59f4f654184fea87c2ce8f37a40d",
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
        "a458fc6e76e6aea6fb404a9297f25dcb95f66c99a677a99ddc81e711bcbf3c46",
        "eec25b85d0cd31b5b35db0eb6441cb8428b2c2f874de7c9c6512c16807071dfa",
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
        "91413de3c6663533f004ff72398b0d122057b4b1dfde4250125e8eb17ba88b2b",
        "c50a11fd96f410b633ddf9440b760667a8da5dc2ad38808986dadf14d2e22afc",
    ),
    # The pool-graded versions (M2/M3; new, pre-publish): old = the kit with the pre-publication profile put back.
    ("f08-ribbed-bracket", "1.6"): (
        "00e33107ce20ae438172c13ef52a168b3324c95999909c4ff388b0277157dba8",
        "44a9dbf57444cdf6b484fe9b76aa690c3acb7bf24667060dc2971f6b3220d4d8",
    ),
    ("f02", "2.5"): (
        "3b069925092b317c2a6cb56c5e6e249cfd3992821d9d4f1571720f2167350caa",
        "567f31adcab3cb3ab0b7385eb2c1a89f63016a61fa130489c6ea3b5eb87e04e1",
    ),
    ("electric-motor-magnetics", "1.5"): (
        "2c6257bbb147e832eb4ff788a83f7aa9f9749417c1cf6cf3a2da0a6678b30378",
        "391dbddcf047326654b172f3e8b34cd6fa10070cbdec071981867e8b4e0f186f",
    ),
    ("chip-cold-plate", "1.5"): (
        "645a2b205484bfae21f0bd2c765e5c47f7b99cf9ebf47c61894f45af97b58a78",
        "7bfb4366cba785d11546aa6882ae13c3a457cba6e88df02b662becf61d68ee72",
    ),
}

# These registrations did not exist at rc22. Their owner-approved construction
# predecessor is a current contract, not a counterfactual historical digest.
NEW_REGISTRATIONS = {
    (registry.COOLING, "1.6"): "1.5",
    (registry.F08, "1.7"): "1.6",
}
CURRENT_PROFILE_VERSIONS = registry.keys(allowlist="v7") | registry.keys(allowlist="v8")


def _digest(challenge_id, version):
    if challenge_id == battery_material.challenge.CHALLENGE.challenge_id:
        material = battery_material.versioned_material(version)
    else:
        material = physical_material.bundle_material(challenge_id, version)
    return material["construction_kit"]["construction_limits_digest"]


def test_exactly_the_v7_versions_moved():
    assert not set(MOVED) & set(NEW_REGISTRATIONS)
    assert set(MOVED) | set(NEW_REGISTRATIONS) == CURRENT_PROFILE_VERSIONS


@pytest.mark.parametrize(("challenge_id", "version"), sorted(MOVED))
def test_a_v7_version_moved_by_its_resource_profile_alone(
    challenge_id, version, monkeypatch
):
    old, new = MOVED[(challenge_id, version)]
    assert _digest(challenge_id, version) == "sha256:" + new
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    rc43_surfaces.learning_rate_as_in_rc43(monkeypatch)
    assert _digest(challenge_id, version) == "sha256:" + old


def test_every_other_version_keeps_its_bytes(monkeypatch):
    current = {
        key: _digest(*key)
        for key in sorted(registry.VERSIONS)
        if key not in CURRENT_PROFILE_VERSIONS
    }
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    assert current == {key: _digest(*key) for key in current}


@pytest.mark.parametrize("key", sorted(NEW_REGISTRATIONS))
def test_new_registrations_publish_and_enforce_their_current_profile(key, monkeypatch):
    before = NEW_REGISTRATIONS[key]
    assert registry.VERSIONS[key].predecessor == before
    material = physical_material.bundle_material(*key)
    predecessor = physical_material.bundle_material(key[0], before)
    assert material["train"] == predecessor["train"]
    assert material["allowlist_bytes"] == predecessor["allowlist_bytes"]
    limits = material["construction_limits_document"]
    assert limits["reconstruction_resource_policy"] == (
        predecessor["construction_limits_document"]["reconstruction_resource_policy"]
    )
    kit = material["construction_kit"]
    binding = {
        "challenge_id": key[0],
        "challenge_version": key[1],
        **{
            field: kit[field]
            for field in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        },
    }
    declared = served_versions.worker_resources(*key)
    assert declared is not None
    assert bundle.verify_direct_resource_policy(binding, limits, declared) == (
        kit["construction_limits_digest"]
    )
    # A prospective change detector only: this alternate digest is never
    # recorded as a historical rc22 pin or used to reinterpret old evidence.
    current = _digest(*key)
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    assert _digest(*key) != current
