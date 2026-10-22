"""The backbone catalog (OWNER-BACKBONE-CATALOG-01) reads no size table.

The unversioned table of bounded settings (hidden_channels <= 256, n_layers <=
8, layer_size <= 1024, ...) and the in-process torch loop that read it reached
no served route; both were retired (Validator, 2026-10-21; owner: no
model-size caps). A served catalog setting is checked only by its entry's
pinned build's own vocabulary (`settings`), which has no size cap.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.backbone_catalog import entries, listing, settings

ROOT = Path(__file__).resolve().parents[2]
RETIRED = (
    "carbon/backbone_catalog/torch_loop.py",
    "carbon/backbone_catalog/torch_backbones.py",
    "carbon/motor/catalog_adapter.py",
)
RETIRED_MODULES = {
    "carbon.backbone_catalog.torch_loop",
    "carbon.backbone_catalog.torch_backbones",
    "carbon.motor.catalog_adapter",
}


def test_the_size_table_and_its_readers_are_gone():
    for path in RETIRED:
        assert not (ROOT / path).exists(), path
    for name in ("ENTRIES", "Setting", "TRAINING", "resolve", "document", "entry"):
        assert not hasattr(entries, name), name
    assert entries.CatalogRefused("catalog_entry_unknown", "x").code == (
        "catalog_entry_unknown"
    )


def _imports(path):
    tree = ast.parse(path.read_bytes())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = ".".join(
                    path.relative_to(ROOT).with_suffix("").parts[: -node.level]
                )
                base = package + ("." + base if base else "")
            yield base
            yield from (base + "." + alias.name for alias in node.names)


def test_no_module_imports_a_retired_reader():
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        reached = set(_imports(path)) & RETIRED_MODULES
        assert not reached, (path, reached)


def _item(backbone):
    for item in listing.entries():
        if item["backbone"] == backbone and item["settings_schema"] in (
            settings.LEVERS.schema_id,
            settings.COOLING_LEVERS.schema_id,
        ):
            return item
    pytest.skip(f"no served {backbone} levers entry")


@pytest.mark.parametrize(
    "backbone, arch",
    [
        ("neuralop.FNO", {"hidden": 4096, "layers": 64, "modes": 12}),
        ("neuralop.TFNO", {"hidden": 4096, "layers": 64}),
        ("transolver", {"hidden": 4096, "heads": 8, "layers": 64, "slices": 512}),
    ],
)
def test_a_served_entry_takes_any_positive_architecture_size(backbone, arch):
    configuration, _ = settings.resolve(_item(backbone), {"arch": arch}, {})
    assert {k: configuration["arch"][k] for k in arch} == arch
    with pytest.raises(entries.CatalogRefused) as refused:
        settings.resolve(_item(backbone), {"arch": {"layers": 0}}, {})
    assert refused.value.code == "catalog_setting_invalid"


def test_the_served_settings_document_names_no_size_limit():
    for item in listing.entries():
        document = settings.document(item)
        assert "bounds" not in str(document)
        assert document["limits"].startswith("the rebuild's wall time")
