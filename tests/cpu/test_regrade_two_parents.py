"""Regrade and the retained construction parent (OWNER-BACKBONE-CATALOG-01;
Validator, 2026-10-20): retention records the parent image a model was built
on, and a regrade is refused unless the receiver still serves that bundle's
runtime on exactly that parent image."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_regrade_retained_entry import _regrade, _retained, _rotate

from carbon.challenge_validator import lean_recipe_retention as retention


def test_regrade_refuses_a_parent_other_than_the_retained_one(tmp_path, monkeypatch):
    # Validator (OWNER-BACKBONE-CATALOG-01): retention records the construction
    # parent, and a regrade on a receiver serving that runtime on another
    # parent image, or not serving it at all, is refused before inference.
    from carbon.development_session.gpu_practice import DirectParentRefused

    fixture = _retained(tmp_path, monkeypatch)
    try:
        _rotate(fixture, monkeypatch, tmp_path)
        retained = json.loads(
            (fixture.first["artifact_path"] / "image.json").read_bytes()
        )
        assert (
            retained["parent_image_id"] == fixture.provider.construction_parent.image_id
        )
        other = "sha256:" + "e" * 64
        fixture.provider.construction_parent = replace(
            fixture.provider.construction_parent, image_id=other, config_digest=other
        )
        calls = len(fixture.runner.calls)
        with pytest.raises(
            retention.RetentionUnavailable, match="regrade_construction_parent_differs"
        ):
            _regrade(fixture)

        def not_served(_bundle):
            raise DirectParentRefused("backend_not_served")

        fixture.provider.construction_parents = SimpleNamespace(for_bundle=not_served)
        with pytest.raises(
            retention.RetentionUnavailable,
            match="regrade_construction_parent_unavailable",
        ):
            _regrade(fixture)
        assert len(fixture.runner.calls) == calls
    finally:
        fixture.provider.close()
