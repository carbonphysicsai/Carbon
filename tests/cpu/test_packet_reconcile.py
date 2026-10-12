import copy

import pytest

from carbon.challenge_pipeline.onboarding import packet
from carbon.challenge_pipeline.onboarding import reconcile as r
from scripts.dev.onboarding import reconcile_examples as examples


def manifest(root):
    for name, text in [
        ("packet", "## Job\nCharging T<=45 C.\n"),
        ("owner", "## Scope\nCharging T<=45 C.\n"),
    ]:
        target = root / f"docs/development/challenge_pipeline/{name}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    docs = {
        name: {
            "path": f"docs/development/challenge_pipeline/{name}.md",
            "sha256": packet.digest(
                (root / f"docs/development/challenge_pipeline/{name}.md").read_bytes()
            ),
            "kind": kind,
        }
        for name, kind in [("packet", "PACKET"), ("owner", "OWNER_DECISION")]
    }
    return {
        "schema": r.SCHEMA,
        "challenge": "motor",
        "documents": docs,
        "checks": [
            examples.check(
                "temperature",
                "hard_limits",
                examples.number("packet", "Charging T<=", "C.", "Job"),
                examples.number("owner", "Charging T<=", "C.", "Scope"),
            )
        ],
    }


def test_matching_scoped_numeric_values_are_not_full_packet_approval(tmp_path):
    out = r.reconcile(tmp_path, manifest(tmp_path))
    assert out["checks"][0]["state"] == "CONSISTENT"
    assert out["coverage"]["checks_examined"] == 1
    assert out["unbound_buyer_fields"]
    assert not out["checklist_clear"] and not out["authority_granted"]


def test_changed_value_reports_precise_contradiction_after_binding_review(tmp_path):
    spec = manifest(tmp_path)
    path = tmp_path / spec["documents"]["packet"]["path"]
    path.write_text("## Job\nCharging T<=46 C.\n")
    stale = r.reconcile(tmp_path, spec)
    assert stale["checks"][0]["state"] == "MISSING_STALE_OR_AMBIGUOUS"
    spec["documents"]["packet"]["sha256"] = packet.digest(path.read_bytes())
    row = r.reconcile(tmp_path, spec)["checks"][0]
    assert row["state"] == "CONTRADICTED"
    assert row["packet"]["value"] == "46" and row["evidence"][0]["value"] == "45"


def test_ambiguous_or_wrong_scope_does_not_green():
    select = examples.number("packet", "Charging T<=", "C.", "Job")
    assert (
        r.extract("## Job\nCharging T<=45 C. Charging T<=46 C.", select)["state"]
        == "MISSING_OR_AMBIGUOUS_CLAUSE"
    )
    assert r.extract("## Other\nCharging T<=45 C.", select)["value"] is None
    select = examples.literal("packet", "charge-only", "CHARGE_ONLY")
    assert r.extract("discharge-only", select)["value"] is None


@pytest.mark.parametrize(
    "path",
    [
        "../private.json",
        "docs/development/hidden/case.json",
        "docs/development/EV5.md",
        "docs/development/journal14.json",
        ".aws/credentials",
    ],
)
def test_nonpublic_sources_unavailable_not_absent(tmp_path, path):
    spec = manifest(tmp_path)
    spec["documents"]["owner"]["path"] = path
    report = r.reconcile(tmp_path, spec)
    assert report["documents"]["owner"]["state"] == "UNAVAILABLE_NOT_ABSENCE"
    assert not report["checklist_clear"]


def test_self_corroboration_unknown_fields_and_arbitrary_regex_refused(tmp_path):
    spec = manifest(tmp_path)
    spec["checks"][0]["evidence"][0]["document"] = "packet"
    with pytest.raises(packet.DraftError, match="corroborate"):
        r.validate(spec)
    spec = manifest(tmp_path)
    spec["checks"][0]["field"] = "qualify"
    with pytest.raises(packet.DraftError):
        r.validate(spec)
    spec = manifest(tmp_path)
    spec["checks"][0]["packet"]["regex"] = "(a+)+$"
    with pytest.raises(packet.DraftError):
        r.validate(spec)


def test_real_battery_motor_cooling_checklists_and_mutations():
    outputs = examples.build()
    import json

    for family in ("battery-v3", "motor", "cooling-cell"):
        spec = json.loads(outputs[family + "-manifest.json"])
        report = r.reconcile(examples.ROOT, spec)
        assert all(c["state"] == "CONSISTENT" for c in report["checks"]), report[
            "checks"
        ]
        assert report["unbound_buyer_fields"] and not report["authority_granted"]
        changed = copy.deepcopy(spec)
        changed["documents"]["owner"]["sha256"] = "0" * 64
        assert all(
            c["state"] != "CONSISTENT"
            for c in r.reconcile(examples.ROOT, changed)["checks"]
        )


def test_example_replay_is_deterministic_and_has_source_pointers():
    assert examples.build() == examples.build()
    assert "OWNER-BATTERY-AMBIENT-MAP-03" in examples.build()["battery-v3-report.json"]
