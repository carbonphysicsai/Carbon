"""SUBMISSION-RATE-STUDY-01 arm H's candidate libraries (run sheet D.1): each
committed file is exactly what the builder makes, its order is its public
seed's, it carries nothing hidden, v1 is kept as recorded, and v2 (current)
holds at least 144 distinct, compiling recipes and every v1 recipe."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "rate_study_library", REPOSITORY / "scripts/dev/rate_study/library.py"
)
library = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(library)

#: v1's digest as recorded in run sheet D.1; never re-pinned.
V1_DIGEST = "sha256:31cea3b24b9d895c361d470cd394866776c2a82a3fbbaade2b99f0f20665d72b"


def committed(version):
    return json.loads(library.out(version).read_text())


@pytest.mark.parametrize("version", library.VERSIONS)
def test_the_committed_library_is_the_builders(version):
    assert library.out(version).read_text() == library.render(library.build(version))


def test_the_check_passes_and_v1_is_kept_as_recorded():
    assert library.main(["--check"]) == 0
    assert committed("v1")["library_digest"] == V1_DIGEST
    assert library.CURRENT == "v2"


def test_v1_holds_every_distinct_panel_recipe_once():
    from carbon.battery.value import panel

    digests = [e["strategy_digest"] for e in committed("v1")["entries"]]
    assert len(digests) == len(set(digests))
    assert set(digests) == {
        library.sha256(library.canonical(strategy))
        for source in library.SOURCES
        for _label, strategy, _seeds in panel.PANELS[source]
    }


def test_v2_is_a_superset_of_v1_with_enough_distinct_recipes():
    v1 = {e["strategy_digest"] for e in committed("v1")["entries"]}
    v2 = [e["strategy_digest"] for e in committed("v2")["entries"]]
    assert len(v2) == len(set(v2)) >= library.MINIMUM_V2
    assert v1 <= set(v2)


def test_every_v2_recipe_compiles():
    from carbon.battery.compile import compile_recipe

    for entry in committed("v2")["entries"]:
        compile_recipe(entry["strategy"])


@pytest.mark.parametrize("version", library.VERSIONS)
def test_the_order_is_the_public_seeds_and_the_digest_holds(version):
    document = committed(version)
    assert document["order_seed"] == library.order_seed(version)
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
    for entry in document["entries"]:
        assert entry["strategy_digest"] == library.sha256(
            library.canonical(entry["strategy"])
        )


@pytest.mark.parametrize("version", library.VERSIONS)
def test_no_seed_or_hidden_field_is_carried(version):
    for entry in committed(version)["entries"]:
        assert set(entry) == {"strategy_digest", "strategy", "sources", "position"}
        assert set(entry["strategy"]) == {
            "schema_version",
            "challenge_id",
            "backbone",
            "parameters",
        }
