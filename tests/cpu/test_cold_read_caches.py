# ---- the per-build memo and the owner commands ---------------------------------------------------------


def test_build_memo_keeps_work_for_one_build_only_and_hands_out_copies():
    from carbon.challenge_registry import build_memo

    calls = []

    def compute():
        calls.append(1)
        return {"kit": [1, 2]}

    assert build_memo.once("k", compute) == {"kit": [1, 2]} and len(calls) == 1
    assert (
        build_memo.once("k", compute) and len(calls) == 2
    ), "nothing is kept outside a build"
    with build_memo.scope():
        first = build_memo.once("k", compute)
        first["kit"].append(3)  # a caller changing its copy
        second = build_memo.once("k", compute)
        assert (
            second == {"kit": [1, 2]} and len(calls) == 3
        ), "one compute, an untouched copy each time"
        with build_memo.scope():  # nested: the outer build's memo stands
            assert build_memo.once("k", compute) == {"kit": [1, 2]} and len(calls) == 3
    build_memo.once("k", compute)
    assert len(calls) == 4, "forgotten when the build ends"


def test_a_catalog_recipe_builds_its_kit_once_per_version_inside_a_build(monkeypatch):
    from carbon.challenge_kit import physical_public

    from carbon.challenge_registry import build_memo, motor

    real = physical_public.construction_kit
    calls = []
    monkeypatch.setattr(
        physical_public,
        "construction_kit",
        lambda *a, **k: calls.append(a) or real(*a, **k),
    )
    entries = listing.entries(motor_challenge := "electric-motor-magnetics", "1.5")[:5]
    assert len(entries) == 5
    with build_memo.scope():
        recipes = [motor.catalog_recipe(e["catalog_id"], "1.5") for e in entries]
    assert len(calls) == 1, "five recipes, one kit"
    assert all(r["challenge"] == recipes[0]["challenge"] for r in recipes)
    assert (
        recipes[0]["challenge"] is not recipes[1]["challenge"]
    ), "each recipe has its own copy"
    calls.clear()
    for e in entries:
        motor.catalog_recipe(e["catalog_id"], "1.5")
    assert len(calls) == 5, "outside a build the kit is built every time, as before"
    assert motor_challenge


def test_the_capability_build_runs_inside_one_memo_scope(monkeypatch):
    from carbon.challenge_registry import build_memo

    inside = []
    monkeypatch.setattr(
        capabilities,
        "_control_center",
        lambda r: inside.append(build_memo._MEMO.get() is not None) or {},
    )
    capabilities.control_center(_Runner())
    assert inside == [True]
    assert build_memo._MEMO.get() is None, "and it ends with the build"


def test_the_owner_commands_edit_a_private_copy_never_the_shared_manifest():
    import pathlib

    from carbon.backbone_catalog import pipeline

    shared = listing.load()
    private = listing.load_fresh()
    assert private is not shared and private == shared
    private["entries"].append({"catalog_id": "scratch"})
    assert listing.load() is shared and "scratch" not in [
        e["catalog_id"] for e in shared["entries"]
    ]
    source = pathlib.Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "manifest = load()" not in source, "add and add_twin read their own copy"
    assert source.count("manifest = load_fresh()") == 2
