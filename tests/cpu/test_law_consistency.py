import copy
import json

import pytest

from carbon.challenge_pipeline.onboarding import law_consistency as lc
from carbon.challenge_pipeline.onboarding import packet
from scripts.dev.onboarding import law_consistency_examples as examples


def fixture(root):
    folder = root / "docs/development/challenge_pipeline"
    folder.mkdir(parents=True)
    source = folder / "packet.md"
    source.write_text(
        "PUBLIC SYNTHETIC: eight reviewed facet projections; not qualified."
    )
    values = {
        "objective": "MINIMIZE_TIME",
        "hard_limits": {"temp_c": 45},
        "observer_scope": "CHARGING_ONLY",
        "P": {"role": "population"},
        "Q": {"role": "diagnostic"},
        "w": {"role": "weights"},
        "boundary": {"bands": 2},
        "NONE_FEASIBLE": {"redraw": False},
    }
    law = {"schema": "fixture.v1", **values}
    path = folder / "law.json"
    path.write_text(json.dumps(law))
    bindings = {
        "schema": lc.SCHEMA,
        "challenge": "motor",
        "law": {
            "path": path.relative_to(root).as_posix(),
            "sha256": packet.digest(path.read_bytes()),
            "schema": "fixture.v1",
        },
        "checks": [
            {
                "id": f,
                "facet": f,
                "packet_value": v,
                "packet_source": {
                    "path": source.relative_to(root).as_posix(),
                    "sha256": packet.digest(source.read_bytes()),
                    "excerpt": source.read_text(),
                },
                "law_pointer": "/" + f,
            }
            for f, v in values.items()
        ],
    }
    return bindings, law, path


def test_eight_facets_exact_types_and_no_authority(tmp_path):
    spec, _, _ = fixture(tmp_path)
    out = lc.check(tmp_path, spec)
    assert out["checklist_clear"] and out["checks_examined"] == 8
    assert not out["unbound_facets"] and not out["authority_granted"]


@pytest.mark.parametrize(
    "facet,value",
    [
        ("objective", "MAXIMIZE_TIME"),
        ("hard_limits", {"temp_c": 46}),
        ("observer_scope", "WHOLE_PROGRAMME"),
        ("boundary", {"bands": 5}),
        ("NONE_FEASIBLE", {"redraw": True}),
    ],
)
def test_semantic_projection_mutations_give_precise_pointer_diff(
    tmp_path, facet, value
):
    spec, law, path = fixture(tmp_path)
    law[facet] = value
    path.write_text(json.dumps(law))
    spec["law"]["sha256"] = packet.digest(path.read_bytes())
    row = next(c for c in lc.check(tmp_path, spec)["checks"] if c["facet"] == facet)
    assert row["state"] == "CONTRADICTED"
    assert all(d["pointer"].startswith("/" + facet) for d in row["diff"])


def test_p_q_swaps_and_boolean_numeric_coercion_are_refused(tmp_path):
    spec, law, path = fixture(tmp_path)
    law["P"], law["Q"] = law["Q"], law["P"]
    path.write_text(json.dumps(law))
    spec["law"]["sha256"] = packet.digest(path.read_bytes())
    rows = lc.check(tmp_path, spec)["checks"]
    assert all(c["state"] == "CONTRADICTED" for c in rows if c["facet"] in {"P", "Q"})
    assert lc.differences(1, True, "/x")[0]["state"] == "TYPE_MISMATCH"


def test_missing_path_is_not_explicit_null_and_partial_is_not_green(tmp_path):
    spec, _, _ = fixture(tmp_path)
    spec["checks"][0]["packet_value"] = None
    spec["checks"][0]["law_pointer"] = "/missing"
    row = lc.check(tmp_path, spec)["checks"][0]
    assert not row["law_present"] and row["diff"][0]["state"] == "MISSING_LAW_FIELD"
    spec["checks"] = spec["checks"][:1]
    assert not lc.check(tmp_path, spec)["checklist_clear"]


def test_stale_source_or_law_remains_unresolved(tmp_path):
    spec, _, _ = fixture(tmp_path)
    spec["checks"][0]["packet_source"]["sha256"] = "0" * 64
    assert lc.check(tmp_path, spec)["checks"][0]["state"] == "UNRESOLVED_SOURCE"
    spec["law"]["sha256"] = "0" * 64
    assert all(
        c["state"] == "UNRESOLVED_SOURCE" for c in lc.check(tmp_path, spec)["checks"]
    )


def test_existing_battery_motor_f02_sources_replay_without_inventing_facets():
    outputs = examples.build()
    for family in ("battery-v3", "motor", "f02"):
        spec = json.loads(outputs[family + "-bindings.json"])
        report = lc.check(examples.ROOT, spec)
        assert all(
            c["state"] == "CONSISTENT_PROJECTION" for c in report["checks"]
        ), report
        assert report["unbound_facets"] and not report["checklist_clear"]
        assert not report["authority_granted"]
    assert outputs == examples.build()


def test_closed_schema_nonfinite_and_nonpublic_input_refused(tmp_path):
    spec, _, _ = fixture(tmp_path)
    spec["checks"][0]["packet_value"] = float("nan")
    with pytest.raises(packet.DraftError):
        lc.validate(spec)
    spec["checks"][0]["packet_value"] = "ok"
    bad = copy.deepcopy(spec)
    bad["law"]["path"] = "docs/development/hidden/truth.json"
    with pytest.raises(packet.DraftError):
        lc.check(tmp_path, bad)
