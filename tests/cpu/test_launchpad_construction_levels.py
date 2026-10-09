"""Construction levels chosen at launch, compiled, frozen, committed and
served (LAUNCHPAD-LEVELS-01 S2; OWNER-LADDER-THROUGH-LAUNCHPAD-01).

Claims tested:

1. A launch at level N binds the level's current registered variant, by name
   and digest, from registry data; the manifest freezes it. Level 0 binds
   nothing and its launch identity and manifest are unchanged.
2. A level campaign compiles with `compile_development` (in its own process),
   and practice trains the recipe's Level 0 base, labelled so.
3. Freeze records the variant digest as the recipe's `contract_digest`, and
   the commitment is `daemon.commitment_digest` over it: no schema change.
4. Before anything is signed, submit and commit refuse a level with no
   current variant (`level_not_registered`) and a target whose
   `served_contracts` is absent or does not list the variant
   (`level_not_served_by_target`); a listing target is accepted, and the
   send path's `development_variant_not_served` lifts only there.
5. Both doors take the level fields from the one operations table.

Fixture intakes only; nothing here reaches a network or a chain.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.development_session import construction_level as cl
from carbon.reconstruction import capability_registry as cr
from scripts.dev.miner_launchpad import levels, operations
from scripts.dev.miner_launchpad.controller import Rejected

BATTERY = cr.BATTERY_CHALLENGE
URL = "http://127.0.0.1:9/carbon/v1/battery/intake"
BASE = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "mlp",
    "parameters": {"width": 16, "depth": 1, "steps": 48, "optimizer_family": "muon"},
}


def strategy(**extra):
    value = json.loads(json.dumps(BASE))
    value["parameters"].update(extra)
    return value


def challenge():
    from carbon.challenge_registry.campaigns import challenge_ref

    return {"id": BATTERY, "version": challenge_ref(BATTERY)["version"]}


def facts(*entries):
    return {"challenge": {"id": BATTERY}, "served_contracts": list(entries)}


def entry(found):
    return {
        "level": found["level"],
        "variant": found["variant"],
        "digest": found["digest"],
    }


@pytest.fixture(autouse=True)
def fresh_cache():
    cl._compiled.cache_clear()
    yield
    cl._compiled.cache_clear()


# ---- 1. The binding.


@pytest.mark.parametrize(
    ("level", "arm"), [(1, None), (1, "signed"), (2, None), (3, None), (4, None)]
)
def test_a_level_binds_its_current_registered_variant(level, arm):
    from carbon.reconstruction import development_variants as dv

    found = cl.resolve(BATTERY, level, arm)
    variant = dv.variant(BATTERY, level, arm)
    assert (found["variant"], found["digest"]) == (variant.version, variant.digest)
    assert found["scope"] == "DEVELOPMENT" and found["level"] == level
    assert cr.is_development_variant(found["digest"])


def test_level_0_binds_nothing_and_an_unregistered_level_is_refused():
    assert cl.resolve(BATTERY, 0) is None
    for level, arm in ((5, None), (2, "signed"), (0, "signed")):
        with pytest.raises(cl.LevelRefused) as refused:
            cl.resolve(BATTERY, level, arm)
        assert refused.value.code == "level_not_registered"
    for bad in (True, -1, 6, "2", 2.0):
        with pytest.raises(cl.LevelRefused) as refused:
            cl.resolve(BATTERY, bad)
        assert refused.value.code == "construction_level_invalid"


def test_a_level_with_no_registered_variant_is_refused_from_registry_data(tmp_path):
    registry = json.loads((cr.DEVELOPMENT_VARIANT_DIR / "registry.json").read_text())
    registry["current"] = [e for e in registry["current"] if e["level"] != 3]
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    with pytest.raises(cl.LevelRefused) as refused:
        cl.resolve(BATTERY, 3, directory=tmp_path)
    assert refused.value.code == "level_not_registered"


def test_launch_binding_refuses_by_closed_code_before_anything_is_created():
    found = levels.launch_binding({"construction_level": 2}, challenge(), "none")
    assert found == cl.resolve(BATTERY, 2)
    assert levels.launch_binding({}, challenge(), "graphite") is None
    with pytest.raises(Rejected) as refused:
        levels.launch_binding({"construction_level": 5}, challenge(), "none")
    assert refused.value.code == "level_not_registered"
    assert operations.refusal(refused.value.code)["field"] == "construction_level"
    with pytest.raises(Rejected) as refused:
        levels.launch_binding({"construction_level": 1}, challenge(), "graphite")
    assert refused.value.code == "construction_level_needs_own_selection"
    with pytest.raises(Rejected) as refused:
        levels.launch_binding({"arm": "signed"}, challenge(), "none")
    assert refused.value.code == "construction_level_invalid"


def test_level_0_is_the_launch_it_always_was():
    request = {"agent": "none", "idempotency_key": "k" * 16}
    assert (
        operations.without_level_zero({**request, "construction_level": 0}) == request
    )
    assert operations.without_level_zero({**request, "construction_level": None}) == (
        request
    )
    assert operations.without_level_zero(request) is request
    kept = {**request, "construction_level": 2}
    assert operations.without_level_zero(kept) is kept


def test_the_manifest_freezes_the_binding_and_level_0_records_nothing():
    from carbon.battery import campaign
    from scripts.dev.miner_launchpad.runner import LaunchChoice

    found = cl.resolve(BATTERY, 2)
    args = SimpleNamespace()
    LaunchChoice(construction_level=found).apply(args)
    assert args.construction_level == found
    LaunchChoice().apply(level0 := SimpleNamespace())
    assert not hasattr(level0, "construction_level")
    product = SimpleNamespace(
        campaign_id="cmp-x",
        agent="none",
        budget={},
        manifest_fields=lambda: {"agent": "none"},
    )
    kwargs = {"owner": "o", "implementation": {}, "images": []}
    at_level = campaign.manifest_document(
        product, **kwargs, construction_level=args.construction_level
    )
    plain = campaign.manifest_document(product, **kwargs)
    assert at_level["construction_level"] == found
    assert cl.binding(at_level) == found
    assert "construction_level" not in plain and cl.binding(plain) is None
    # The base contract digest stays the manifest's; the variant's is bound.
    assert at_level["contract_digest"] == plain["contract_digest"]


# ---- 2. The compile, and practice at the level.


def test_practice_compiles_at_the_level_and_trains_the_level_0_base():
    from carbon.battery.compile import compile_recipe
    from carbon.battery.research import BatteryPractice

    found = cl.resolve(BATTERY, 2)
    practice = SimpleNamespace(level=found)
    widened = strategy(muon_spectral=True)
    _compiled, recipe = BatteryPractice.compile(practice, widened)
    _base, expected = compile_recipe(strategy())
    assert recipe == expected
    with pytest.raises(cl.LevelRefused) as refused:
        BatteryPractice.compile(practice, strategy(muon_spectral=3))
    assert refused.value.code == "level_strategy_refused"
    codes = {i["code"] for i in refused.value.issues}
    assert "development.out_of_bounds" in codes
    # At Level 0 the widened field is the base contract's to refuse.
    with pytest.raises(ValueError):
        BatteryPractice.compile(SimpleNamespace(level=None), widened)
    label = cl.practice_label(found)
    assert label["widened_trained"] is False and label["digest"] == found["digest"]


def test_the_level_compile_is_compile_development():
    from carbon.reconstruction import development_variants as dv

    found = cl.resolve(BATTERY, 2)
    value = cl.compile_strategy(found, strategy(muon_spectral=True))
    direct = dv.compile_development(
        strategy(muon_spectral=True), dv.variant(BATTERY, 2)
    )
    assert value["development"] == direct.development
    assert value["recipe_digest"] == direct.construction.recipe_digest
    assert value["commitment_strategy_hash"] == direct.construction.strategy_hash
    assert value["widened_fields"] == sorted(dv.variant(BATTERY, 2).fields())
    base = levels.checked_strategy(found, strategy(muon_spectral=True))
    assert base == strategy()


# ---- 3. Freeze and commitment.


def test_freeze_records_the_variant_digest_and_the_commitment_binds_it():
    from carbon.battery import campaign
    from carbon.battery.daemon import commitment_digest

    found = cl.resolve(BATTERY, 2)
    chosen = strategy(muon_spectral=True)
    compiled, envelope = cl.check_freeze(found, chosen)
    assert envelope is None
    record = cl.candidate_record(found, chosen, "practiced", False, compiled)
    assert record["contract_digest"] == found["digest"]
    assert record["construction_level"]["digest"] == found["digest"]
    manifest = {"contract_digest": cr.contract_digest(BATTERY)}
    digest = campaign.frozen_commitment(record, manifest)
    # The commitment's own schema, unchanged: {challenge, contract, strategy}.
    assert digest == commitment_digest(
        BATTERY, found["digest"], compiled["commitment_strategy_hash"]
    )
    level0 = campaign.frozen_commitment({"strategy": strategy()}, manifest)
    assert level0 != digest
    # A record whose binding differs from its contract digest is not committed.
    altered = {**record, "contract_digest": cl.resolve(BATTERY, 3)["digest"]}
    with pytest.raises(ValueError):
        campaign.frozen_commitment(altered, manifest)


def test_research_freeze_writes_the_level_record(tmp_path, monkeypatch):
    import asyncio

    from carbon.development_session import research_campaign as rc

    found = cl.resolve(BATTERY, 1)
    monkeypatch.setattr(rc, "freeze_refusal", lambda root, s: None)
    monkeypatch.setattr(rc, "report", lambda ledger, owner: None)
    ledger = SimpleNamespace(
        root=tmp_path, checkpoint=lambda: None, status=lambda owner: {}
    )
    prepared = SimpleNamespace(
        ledger=ledger, owner="o", manifest={"construction_level": found}
    )
    chosen = strategy()
    answer = asyncio.run(rc.freeze_candidate(prepared, strategy=chosen, reason="r"))
    record = json.loads((tmp_path / "epoch-1" / "selected-recipe.json").read_bytes())
    assert answer["selection"] == record
    assert record["contract_digest"] == found["digest"]
    assert not (tmp_path / "epoch-1" / cl.LEVEL4_ENVELOPE).exists()


def test_a_level4_directory_is_refused_below_level_4():
    with pytest.raises(cl.LevelRefused) as refused:
        cl.check_freeze(None, strategy(), "/tmp/lowered")
    assert refused.value.code == "level4_directory_needs_level4"


# ---- 4. The target's served contracts, before anything is signed.


def test_lists_matches_by_version_name_and_confirms_by_digest():
    found = cl.resolve(BATTERY, 2)
    other = cl.resolve(BATTERY, 3)
    assert cl.lists(facts(entry(found)), found)
    assert not cl.lists({"challenge": {}}, found)  # field absent
    assert not cl.lists(
        facts({"level": 0, "digest": cr.contract_digest(BATTERY)}), found
    )
    assert not cl.lists(facts(entry(other)), found)
    assert not cl.lists(facts({**entry(found), "variant": other["variant"]}), found)
    assert not cl.lists(facts({**entry(found), "digest": other["digest"]}), found)
    assert cl.deployment_level(facts({"level": 0, "digest": "x"}, entry(found))) == 0
    assert cl.deployment_level({}) is None


def _manifest(level=None, arm=None):
    manifest = {
        "challenge": challenge(),
        "contract_digest": cr.contract_digest(BATTERY),
    }
    if level:
        manifest["construction_level"] = cl.resolve(BATTERY, level, arm)
    return manifest


CFG = {"intakes": {BATTERY: URL}}


def test_require_served_refuses_while_served_contracts_is_absent():
    reads = []

    def read(url):
        reads.append(url)
        return {"challenge": {"id": BATTERY}}

    with pytest.raises(Rejected) as refused:
        levels.require_served(CFG, _manifest(2), read=read)
    assert refused.value.code == "level_not_served_by_target"
    assert reads == [URL]
    assert operations.refusal(refused.value.code)["field"] == "construction_level"


def test_require_served_refuses_a_target_that_does_not_list_the_digest():
    level0 = {"level": 0, "digest": cr.contract_digest(BATTERY)}
    with pytest.raises(Rejected) as refused:
        levels.require_served(CFG, _manifest(2), read=lambda url: facts(level0))
    assert refused.value.code == "level_not_served_by_target"
    with pytest.raises(Rejected) as refused:
        levels.require_served(
            CFG,
            _manifest(2),
            read=lambda url: facts(level0, entry(cl.resolve(BATTERY, 3))),
        )
    assert refused.value.code == "level_not_served_by_target"
    with pytest.raises(Rejected) as refused:
        levels.require_served({"intakes": {}}, _manifest(2), read=lambda url: facts())
    assert refused.value.code == "level_not_served_by_target"


def test_require_served_accepts_a_target_that_lists_the_variant():
    found = cl.resolve(BATTERY, 2)
    level0 = {"level": 0, "digest": cr.contract_digest(BATTERY)}
    assert (
        levels.require_served(
            CFG, _manifest(2), read=lambda url: facts(level0, entry(found))
        )
        is None
    )


def test_require_served_leaves_level_0_unchanged():
    def never(url):
        raise AssertionError("a Level 0 campaign reads no facts here")

    assert levels.require_served(CFG, _manifest(), read=never) is None


def test_require_served_refuses_a_frozen_variant_no_longer_current(monkeypatch):
    manifest = _manifest(2)
    manifest["construction_level"] = {
        **manifest["construction_level"],
        "variant": "battery-l2-spectral-v1",
        "digest": "sha256:" + "0" * 64,
    }
    with pytest.raises(Rejected) as refused:
        levels.require_served(CFG, manifest, read=lambda url: facts())
    assert refused.value.code == "level_not_registered"


def test_an_unreadable_target_is_never_served():
    def broken(url):
        raise OSError("down")

    with pytest.raises(Rejected) as refused:
        levels.require_served(CFG, _manifest(2), read=broken)
    assert refused.value.code == "intake_unreachable"


def test_the_send_path_lifts_its_refusal_only_where_the_target_lists_the_digest(
    tmp_path, monkeypatch
):
    from carbon.battery import campaign
    from carbon.battery import remote_submission as rs

    found = cl.resolve(BATTERY, 2)
    sent = []
    monkeypatch.setattr(
        rs,
        "submit_and_wait",
        lambda url, signer, **kw: sent.append(kw["contract_digest"])
        or (200, {"state": "SCORED"}, "sub-1"),
    )

    def submit(served, binding=found):
        return campaign.submit_through_intake(
            URL,
            object(),
            root=tmp_path,
            epoch=1,
            strategy=strategy(),
            contract_digest=found["digest"],
            read=lambda url: served,
            post=lambda *a: None,
            construction_level=binding,
        )

    for served in ({"challenge": {}}, facts({"level": 0, "digest": "x"})):
        with pytest.raises(rs.IntakeRefusal) as refused:
            submit(served)
        assert refused.value.code == "development_variant_not_served"
    # A variant digest without its frozen level binding is never sent, even
    # to a target that lists it.
    for binding in (None, cl.resolve(BATTERY, 3)):
        with pytest.raises(rs.IntakeRefusal) as refused:
            submit(facts(entry(found)), binding)
        assert refused.value.code == "development_variant_not_served"
    assert sent == []
    assert submit(facts(entry(found)))[0] == 200
    assert sent == [found["digest"]]


def test_the_send_path_at_level_0_reads_no_extra_facts(tmp_path, monkeypatch):
    from carbon.battery import campaign
    from carbon.battery import remote_submission as rs

    monkeypatch.setattr(
        rs, "submit_and_wait", lambda url, signer, **kw: (200, {"state": "SCORED"}, "s")
    )

    def never(url):
        raise AssertionError("no facts read before the Level 0 submit")

    status, _answer, _sid = campaign.submit_through_intake(
        URL,
        object(),
        root=tmp_path,
        epoch=1,
        strategy=strategy(),
        contract_digest=cr.contract_digest(BATTERY),
        read=never,
        post=lambda *a: None,
    )
    assert status == 200


# ---- The Contract and ladder views.


def test_the_contract_slot_shows_the_campaigns_level_as_development():
    found = cl.resolve(BATTERY, 3)
    slot = levels.campaign_slot(
        found, {"level": 0, "status": "DEFINED", "ladder": {"level": 0}}
    )
    assert slot["level"] == 3 and slot["audience"] == "DEVELOPMENT"
    assert slot["variant"] == {"name": found["variant"], "digest": found["digest"]}
    assert levels.campaign_slot(None, {"level": 0}) == {"level": 0}


def test_the_ladder_labels_every_level_above_the_targets_own_development():
    from scripts.dev.miner_launchpad.ladder_view import for_request

    value = for_request({"challenge": BATTERY}, deployment_level=0)
    assert value["deployment_level"] == 0
    for row in value["levels"]:
        if row["level"] > 0:
            assert row["audience"] == "DEVELOPMENT"


# ---- 5. One table, both doors.


def test_both_doors_take_the_level_fields_from_the_one_table():
    launch = operations.OPERATIONS["launch"]
    freeze = operations.OPERATIONS["freeze_candidate"]
    assert {"construction_level", "arm"} <= launch.optional
    assert "level4_directory" in freeze.optional
    assert operations.FIELDS["construction_level"][0] == "integer"
    described = {d["operation"]: d for d in operations.describe()}
    assert {"construction_level", "arm"} <= set(described["launch"]["optional"])
    pytest.importorskip("mcp")
    from carbon.miner_mcp.mcp_operations import make_operation_tools

    tools = {t.name: t for t in make_operation_tools(SimpleNamespace())}
    schemas = {
        name: set(tool.parameters.get("properties", {})) for name, tool in tools.items()
    }
    launch_schema = next(v for k, v in schemas.items() if k.endswith("launch"))
    freeze_schema = next(
        v for k, v in schemas.items() if k.endswith("freeze_candidate")
    )
    assert {"construction_level", "arm"} <= launch_schema
    assert "level4_directory" in freeze_schema


def test_every_level_code_has_a_next_step():
    from scripts.dev.miner_launchpad.supervisor import FALLBACK_ACTION, next_action

    codes = [
        c
        for c, f in operations.REFUSAL_FIELDS.items()
        if c.startswith(("level", "construction_level"))
    ]
    assert "level_not_registered" in codes and "level_not_served_by_target" in codes
    for code in codes + ["level_compile_unavailable"]:
        assert next_action(code) != FALLBACK_ACTION, code
