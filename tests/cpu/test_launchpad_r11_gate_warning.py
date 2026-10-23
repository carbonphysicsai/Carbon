"""M1 E2E round 11: freezing or submitting a gate-failed practice warns."""

from __future__ import annotations


def _campaign(tmp_path, results):
    import json

    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_campaign import CampaignLedger

    root = tmp_path / "campaign"
    root.mkdir()
    (root / "campaign-manifest.json").write_text(json.dumps({"owner": "alice"}))
    ledger = CampaignLedger(root)
    with ledger.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results"
            "(owner TEXT, id TEXT, body TEXT, digest TEXT)"
        )
        for index, result in enumerate(results):
            body = canonical(result)
            db.execute(
                "INSERT INTO research_results VALUES(?,?,?,?)",
                ("alice", f"r{index}", body, digest(body)),
            )
    return root


def test_freezing_or_submitting_a_gate_failed_practice_warns_but_never_refuses(
    tmp_path,
):
    # R11: an ineligible F02 practice froze and submitted with no word.
    from carbon.development_session.research_campaign import (
        PRACTICE_DUAL_SCHEMA,
        freeze_gate_warning,
    )

    recipe = {"schema": "carbon.construction-recipe.v1", "source": {"kind": "catalog"}}
    other = {**recipe, "source": {"kind": "bundle"}}
    dual = {"schema": PRACTICE_DUAL_SCHEMA, "available": True, "eligible": False}
    root = _campaign(
        tmp_path,
        [
            {"recipe": recipe, "practice_dual": dual},
            {"recipe": other, "practice_dual": {**dual, "eligible": True}},
        ],
    )
    warning = freeze_gate_warning(root, recipe)
    assert warning["code"] == "practice_gate_failed"
    assert "you may still freeze and submit" in warning["plain"]
    assert freeze_gate_warning(root, other) is None
    assert freeze_gate_warning(root, {**recipe, "x": 1}) is None
    assert freeze_gate_warning(tmp_path / "missing", recipe) is None


def test_the_gate_warning_names_the_failed_gate(tmp_path):
    # R11e: the warning said "its practice result names the gate" instead of
    # naming verified_pick.
    from carbon.development_session.research_campaign import (
        PRACTICE_DUAL_SCHEMA,
        freeze_gate_warning,
    )

    recipe = {"schema": "carbon.construction-recipe.v1", "source": {"kind": "catalog"}}
    dual = {
        "schema": PRACTICE_DUAL_SCHEMA,
        "available": True,
        "eligible": False,
        "gates": {"verified_pick": False, "law": True, "paired_repeat": "NOT_TESTED"},
    }
    root = _campaign(tmp_path, [{"recipe": recipe, "practice_dual": dual}])
    warning = freeze_gate_warning(root, recipe)
    assert warning["code"] == "practice_gate_failed"
    assert warning["gates"] == ["verified_pick"]
    assert "the mandatory gate verified_pick," in warning["plain"]
    assert "you may still freeze and submit" in warning["plain"].lower()

    two = {**dual, "gates": {"verified_pick": False, "law": False}}
    (tmp_path / "b").mkdir()
    root2 = _campaign(tmp_path / "b", [{"recipe": recipe, "summary": {"x": two}}])
    assert freeze_gate_warning(root2, recipe)["gates"] == ["law", "verified_pick"]


def test_the_gate_warning_never_fails_a_freeze_or_submit(tmp_path):
    # Validator (R11e receipt): a changed retained result, or a manifest that
    # cannot be read, gives no warning; it never raises.
    from carbon.development_session.research_campaign import (
        PRACTICE_DUAL_SCHEMA,
        CampaignLedger,
        failed_gate_names,
        freeze_gate_warning,
    )

    recipe = {"schema": "carbon.construction-recipe.v1", "source": {"kind": "catalog"}}
    dual = {
        "schema": PRACTICE_DUAL_SCHEMA,
        "available": True,
        "eligible": False,
        "gates": {"verified_pick": False},
    }
    root = _campaign(tmp_path, [{"recipe": recipe, "practice_dual": dual}])
    with CampaignLedger(root).db() as db:
        db.execute("UPDATE research_results SET digest='sha256:changed'")
    assert failed_gate_names(CampaignLedger(root), "alice", recipe) == ()
    assert freeze_gate_warning(root, recipe) is None

    for broken in (b"not json", b"[]", b"{}"):
        (root / "campaign-manifest.json").write_bytes(broken)
        assert freeze_gate_warning(root, recipe) is None
