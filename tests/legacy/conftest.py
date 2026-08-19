"""Collection policy for retained, non-default legacy tests."""

from pathlib import Path

import pytest

_LEGACY_TEST_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Classify only tests collected from this retained legacy directory."""
    for item in items:
        if Path(item.path).resolve().is_relative_to(_LEGACY_TEST_DIR):
            item.add_marker(pytest.mark.legacy)
