"""A first practice should not wait for the whole catalog: the entries it starts on install first (clean-machine B1)."""

import pathlib

from carbon.backbone_catalog import listing
from scripts.dev.miner_launchpad import toolbox


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
    ordered = listing.install_order(items)
    assert sorted(i["catalog_id"] for i in ordered) == sorted(
        i["catalog_id"] for i in items
    ), "nothing dropped or added"
    assert [i["catalog_id"] for i in items] == [
        i["catalog_id"] for i in listing.load()["entries"]
    ], "the shared manifest is not reordered"
    wanted = []
    for challenge_id, version in sorted(_newest().items()):
        preferred = listing.preferred(challenge_id, version)
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
        preferred = listing.preferred(challenge_id, version)
        assert marked == ([preferred] if preferred is not None else [])


def test_the_catalog_installer_installs_in_that_order():
    source = pathlib.Path("scripts/dev/catalog_install.py").read_text(encoding="utf-8")
    assert 'listing.install_order(pipeline.load()["entries"])' in source
