"""The backbone picker carries each entry's accepted settings, so the page offers only fields the entry takes (E4)."""

from scripts.dev.miner_launchpad import toolbox


def test_each_catalog_recipe_names_the_settings_its_schema_takes():
    items = toolbox.catalog_recipes("electric-motor-magnetics", "1.3")
    assert items
    for item in items:
        assert set(item["settings"]) == {"configuration", "train_use"}
        assert all(isinstance(name, str) for name in item["settings"]["train_use"])
    assert any("steps" in item["settings"]["train_use"] for item in items)
