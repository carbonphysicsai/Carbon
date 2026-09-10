"""Disposable setup never supplies public scientific or deployment authority."""

import subprocess
import sys
from pathlib import Path


def test_localnet_import_has_no_sdk_key_or_network_construction():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import carbon.chain.localnet; assert 'bittensor' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_runtime_driver_owns_only_isolated_disposable_resources():
    root = Path(__file__).parents[2]
    text = (root / "scripts/dev/localnet.sh").read_text()
    assert "--internal" in text and "--publish" not in text and "  -p " not in text
    assert "--privileged" not in text and "docker system prune" not in text
    source = (root / "carbon/chain/localnet.py").read_text()
    assert "policy=bt.Policy(allowed_netuids=[2])" in source
    assert "allow_raw_calls=True" not in source
    assert "set_storage" not in source and "mev_shield_required = False" not in source
    assert "await self.verify()" in source


def test_additional_exam_profiles_remain_fixed_synthetic_owner_inputs():
    from carbon.traineval import FixtureStubProfile

    for name in ("a5_fixture_net5_b", "a5_fixture_net5_c"):
        pin = FixtureStubProfile(localnet_fixture=name).score_pack_pin()
        assert pin.fixture_origin is True and pin.challenge_key.version == "fixture-1.0"
