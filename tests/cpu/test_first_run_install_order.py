"""A first practice should not wait for the whole catalog: the entries it starts on install first (clean-machine B1)."""

import pathlib

from carbon.backbone_catalog import listing
from scripts.dev.miner_launchpad import toolbox
from scripts.dev.miner_launchpad.starting_entry import (
    MEASURED_START,
    start_first,
    starting_entry,
)


def _newest():
    newest = {}
    for item in listing.load()["entries"]:
        for each in item["challenges"]:
            version = listing._version_key(each["version"])
            if each["id"] not in newest or version > newest[each["id"]][0]:
                newest[each["id"]] = (version, each["version"])
    return {challenge: version[1] for challenge, version in newest.items()}


def test_install_order_is_a_permutation_with_the_first_practice_entries_first():
    items = listing.load()["entries"]
    ordered = start_first(items)
    assert sorted(i["catalog_id"] for i in ordered) == sorted(
        i["catalog_id"] for i in items
    ), "nothing dropped or added"
    assert [i["catalog_id"] for i in items] == [
        i["catalog_id"] for i in listing.load()["entries"]
    ], "the shared manifest is not reordered"
    wanted = []
    for challenge_id, version in sorted(_newest().items()):
        preferred = starting_entry(challenge_id, version)
        if preferred is not None and preferred not in wanted:
            wanted.append(preferred)
    assert wanted, "the catalog names first-practice entries"
    assert [i["catalog_id"] for i in ordered[: len(wanted)]] == wanted
    rest_before = [i["catalog_id"] for i in items if i["catalog_id"] not in wanted]
    assert [
        i["catalog_id"] for i in ordered[len(wanted) :]
    ] == rest_before, "the rest keep their own order"


def test_the_picker_marks_the_one_recommended_entry_per_version():
    for challenge_id, version in sorted(_newest().items()):
        recipes = toolbox.catalog_recipes(challenge_id, version)
        if not recipes:
            continue
        marked = [r["catalog_id"] for r in recipes if r["recommended"]]
        preferred = starting_entry(challenge_id, version)
        assert marked == ([preferred] if preferred is not None else [])


def test_the_catalog_installer_installs_in_that_order():
    source = pathlib.Path("scripts/dev/catalog_install.py").read_text(encoding="utf-8")
    assert 'start_first(pipeline.load()["entries"])' in source


def test_a_newcomer_starts_on_the_baseline_where_one_is_offered_and_the_registry_example_is_unchanged():
    seen = 0
    for challenge_id, version in sorted(_newest().items()):
        ids = [item["catalog_id"] for item in listing.entries(challenge_id, version)]
        baselines = [i for i in ids if i.startswith("v2.") and i.endswith(".prior_krr")]
        start = starting_entry(challenge_id, version)
        if (challenge_id, version) in MEASURED_START:
            continue
        if baselines:
            seen += 1
            assert start == baselines[0]
            assert start in ids, "the baseline is a real, served entry"
        else:
            assert start == listing.preferred(challenge_id, version)
    assert seen, "the catalog offers a baseline on at least one Challenge"
    # The registry's ready example and its digests are not moved by the Launchpad's choice.
    assert listing.preferred("electric-motor-magnetics", "1.4") == "v2.motor.jno.bcat"


def test_cooling_1_6_starts_on_the_measured_entry_because_its_baseline_is_refused_at_freeze():
    """prior_krr on Cooling 1.6 is 63,026 bytes of wiring, over the 32 KiB v6 budget (panel 2026-10-30); the start is
    the receipted, eligible entry with the highest measured total. The other launch versions keep prior_krr.
    """
    ids = [i["catalog_id"] for i in listing.entries("chip-cold-plate", "1.6")]
    assert "v2.cooling.prior_krr" in ids, "the baseline stays in the picker"
    assert (
        starting_entry("chip-cold-plate", "1.6")
        == "v2.cooling.physicsnemo.MeshGraphNet"
    )
    assert MEASURED_START == {
        ("chip-cold-plate", "1.6"): "v2.cooling.physicsnemo.MeshGraphNet"
    }
    for challenge_id, version, expected in (
        ("electric-motor-magnetics", "1.5", "v2.motor.prior_krr"),
        ("f08-ribbed-bracket", "1.7", "v2.f08.prior_krr"),
        ("f02", "2.5", "v2.f02.prior_krr"),
    ):
        assert starting_entry(challenge_id, version) == expected
