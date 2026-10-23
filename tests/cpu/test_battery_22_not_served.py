"""Battery 2.2 is not served (OWNER-BATTERY-OUT-OF-LAUNCH-01): Battery is out of
launch and 2.2 was never completed, so every table agrees on the Battery
versions already served (1.0 to 2.1). Its code (`battery.catalog_version`)
stays, unregistered; registering it again is a new decision."""

from carbon.battery import construction_bundle_material
from carbon.challenge_kit import battery_pack, physical_material, served_versions
from carbon.challenge_registry import registry
from carbon.challenge_registry.campaigns import _direct_campaigns
from carbon.development_session import construction_tensor_codec

BATTERY = "battery-fastcharge-ageing-development-v1"
SERVED = ("1.0", "2.0", "2.1")


def test_no_table_serves_battery_2_2():
    key = (BATTERY, "2.2")
    assert key not in served_versions.CATALOG
    assert key not in served_versions.V7
    assert key not in physical_material.REGISTERED
    assert key not in _direct_campaigns()
    assert all(
        (e.challenge_id, e.version) != key for e in registry.entries()
    ), "the registry lists Battery 2.2"


def test_every_battery_version_table_agrees():
    assert battery_pack.VERSIONS == SERVED
    assert construction_bundle_material.VERSIONS == SERVED
    assert construction_tensor_codec._BATTERY_VERSIONS == SERVED
