"""SUBMISSION-RATE-STUDY-01 arm H's candidate library (run sheet D.1): the
committed file is exactly what the builder makes from Carbon's panels, its
order is the public seed's, and it carries nothing hidden."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "rate_study_library", REPOSITORY / "scripts/dev/rate_study/library.py"
)
library = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(library)


def committed():
    return json.loads(library.OUT.read_text())


def test_the_committed_library_is_the_builders():
    assert library.OUT.read_text() == library.render(library.build())
    assert library.main(["--check"]) == 0


def test_every_distinct_panel_recipe_is_in_it_once():
    from carbon.battery.value import panel

    document = committed()
    digests = [e["strategy_digest"] for e in document["entries"]]
    assert len(digests) == len(set(digests))
    expected = {
        library.sha256(library.canonical(strategy))
        for source in library.SOURCES
        for _label, strategy, _seeds in panel.PANELS[source]
    }
    assert set(digests) == expected
    for entry in document["entries"]:
        assert entry["strategy_digest"] == library.sha256(
            library.canonical(entry["strategy"])
        )


def test_the_order_is_the_public_seeds_and_the_digest_holds():
    document = committed()
    keys = [
        hashlib.sha256(
            (document["order_seed"] + ":" + e["strategy_digest"]).encode()
        ).hexdigest()
        for e in document["entries"]
    ]
    assert keys == sorted(keys)
    assert [e["position"] for e in document["entries"]] == list(range(len(keys)))
    body = {k: v for k, v in document.items() if k != "library_digest"}
    assert document["library_digest"] == library.sha256(library.canonical(body))


def test_no_seed_or_hidden_field_is_carried():
    for entry in committed()["entries"]:
        assert set(entry) == {"strategy_digest", "strategy", "sources", "position"}
        assert set(entry["strategy"]) == {
            "schema_version",
            "challenge_id",
            "backbone",
            "parameters",
        }
