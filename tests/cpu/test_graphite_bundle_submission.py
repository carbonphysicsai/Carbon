"""A Graphite phase-3 bundle becomes the Launchpad's own submission (BUNDLE-TO-SUBMISSION-01).

Pinned:

- a run-5-style battery bundle (DeepONet with physics heads, a v3 manifest)
  converts, against the published miner-facing contract digest;
- parity: the converter's bytes are the bytes the Launchpad's freeze writes
  for the same recipe (`research_campaign.freeze_candidate`), and the
  Launchpad's submit then sends exactly the converter's strategy and
  contract digest (`battery.campaign._evaluate_through_intake`, its intake
  replaced by a capture: nothing is signed or sent);
- refusals, typed, each producing nothing: a tampered bundle, a
  score-variant-labelled bundle, a Level-1 bundle, a development variant's
  digest, an unpublished contract digest, a recipe the contract does not
  admit, a bundle Carbon does not rebuild, a record whose digests are not the
  bundle's, and an output file holding other bytes;
- one mutation per guard: with the guard disabled, its bundle is no longer
  refused by its code;
- no network: every socket connect fails during a conversion.

Fixture bundles only: no pod, model, chain, key, wallet or spend.
"""

from __future__ import annotations

import asyncio
import copy
import json
import socket
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import bundle_submission as bs
from carbon.agent_campaign.graphite import delivery
from carbon.agent_campaign.graphite import experiment as ex
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.artifact_identity import build_identity

BATTERY = "battery-fastcharge-ageing-development-v1"
#: Run 5's bundled shape (GRAPHITE phase 3, R2 run 5): DeepONet, depth 3,
#: width 128, 20 basis functions, 15k steps, Arrhenius + OCV + capacity-fade.
RUN5 = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "deeponet",
    "parameters": {
        "deeponet_depth": 3,
        "width": 128,
        "basis_functions": 20,
        "steps": 15000,
        "arrhenius_features": True,
        "ocv_initial_voltage": True,
        "capacity_fade_head": True,
    },
}
SEED = 20261005
#: Battery's registered Level-1 variant (loss expressions).
L1_VARIANT = "sha256:34153f41641e3f45077e2752b1cae6d2e1c0ae4327d2cb780526e084a241c854"
SCORE_VARIANT = "battery-g-feas-ce-v1"
FORGED = "sha256:" + "c" * 64


@pytest.fixture(scope="module")
def level0():
    return ex.admit(RUN5, SEED)


@pytest.fixture(scope="module")
def level1():
    from carbon.reconstruction import development_variants

    return ex.admit(RUN5, SEED, variant=development_variants.registered(L1_VARIANT))


def score_record(recipe, **extra):
    """A phase-3 winner's result: synthetic fixture numbers, no claim."""
    return {
        "kind": "proposal",
        "proposal_id": "p-fixture00005",
        "status": "SCORED",
        "recipe_digest": recipe["recipe_digest"],
        "frozen_rule": {"eligible": True, "score": 0.5},
        "against_baseline": {
            "outcome": "IMPROVEMENT",
            "reason": "fixture",
            "promotable": True,
        },
        **extra,
    }


def write_bundle(folder, strategy, recipe, *, score=None, **manifest_extra):
    """A bundle in `delivery.deliver`'s exact layout and manifest."""
    folder.mkdir(parents=True, mode=0o700)
    bodies = {
        "strategy.json": canonical(strategy),
        "recipe.json": canonical(recipe),
        "score.json": canonical(score or score_record(recipe)),
        "rows.json": canonical([]),
        "baseline.json": canonical({"strategy": {}, "result": {"status": "SCORED"}}),
        "ablations.json": canonical({"undefined": None, "ablations": []}),
        "run-log.jsonl": canonical({"event": "fixture"}) + b"\n",
        "WRITEUP.md": b"# fixture\n",
        "REBUILD.md": delivery.rebuild_text("p-fixture00005").encode(),
        "next-level-proposals.json": canonical({"proposals": [], "note": "none"}),
    }
    for name, body in bodies.items():
        (folder / name).write_bytes(body)
    manifest = {
        "schema": delivery.BUNDLE_SCHEMA,
        "proposal_id": "p-fixture00005",
        "run_id": "graphite-fixture",
        "files": {name: digest(bodies[name]) for name in delivery.FILES},
        "contract_digest": recipe["contract_digest"],
        "record_sequence": recipe["record_sequence"],
        "recipe_digest": recipe["recipe_digest"],
        "artifact": build_identity(recipe),
        "authority_granted": False,
        "official_eligible": False,
        **manifest_extra,
    }
    (folder / "manifest.json").write_bytes(canonical(manifest))
    return folder


# -- fixtures for each refusal: (code, builder) ---------------------------------------------
def tampered(tmp_path, level0, level1):
    folder = write_bundle(tmp_path / "bundle", RUN5, level0)
    wider = copy.deepcopy(RUN5)
    wider["parameters"]["width"] = 256
    (folder / "strategy.json").write_bytes(canonical(wider))
    return folder


def score_variant(tmp_path, level0, level1):
    label = "development_score_result:" + SCORE_VARIANT
    score = score_record(
        level0, score_variant={"score_variant": SCORE_VARIANT, "label": label}
    )
    score["label"] = label
    return write_bundle(tmp_path / "bundle", RUN5, level0, score=score)


def level_one(tmp_path, level0, level1):
    return write_bundle(tmp_path / "bundle", RUN5, level1)


def variant_digest(tmp_path, level0, level1):
    recipe = {**level0, "contract_digest": L1_VARIANT}
    return write_bundle(tmp_path / "bundle", RUN5, recipe)


def unpublished(tmp_path, level0, level1):
    recipe = {**level0, "contract_digest": FORGED}
    return write_bundle(tmp_path / "bundle", RUN5, recipe)


def not_admitted(tmp_path, level0, level1):
    strategy = copy.deepcopy(RUN5)
    strategy["parameters"]["loss_expressions"] = [{"op": "sq_error"}]
    return write_bundle(tmp_path / "bundle", strategy, level0)


def not_rebuilt(tmp_path, level0, level1):
    recipe = {**level0, "program": FORGED}
    return write_bundle(tmp_path / "bundle", RUN5, recipe)


def digest_mismatch(tmp_path, level0, level1):
    recipe = {**level0, "strategy_hash": FORGED}
    return write_bundle(tmp_path / "bundle", RUN5, recipe)


#: (code, bundle builder, the guard, its mutant, other guards bypassed).
GUARDS = [
    (bs.BUNDLE_TAMPERED, tampered, "integrity", None, ()),
    (bs.SCORE_VARIANT_LABELLED, score_variant, "check_score_variant", None, ()),
    (bs.DEVELOPMENT_LEVEL, level_one, "check_level", None, ()),
    (bs.DEVELOPMENT_VARIANT, variant_digest, "check_variant", None, ()),
    (bs.CONTRACT_NOT_PUBLISHED, unpublished, "published_contract", "trust", ()),
    (bs.RECIPE_NOT_ADMITTED, not_admitted, "check_admitted", None, ()),
    (bs.BUNDLE_NOT_REBUILT, not_rebuilt, "check_rebuilt", None, ()),
    # Defence in depth behind the clean rebuild, which catches it first.
    (
        bs.SUBMISSION_DIGEST_MISMATCH,
        digest_mismatch,
        "check_digests",
        None,
        ("check_rebuilt",),
    ),
]


def outcome(bundle, out):
    try:
        return bs.convert(bundle, out)["status"]
    except bs.Refused as refused:
        return refused.code


def mutate(monkeypatch, guard, kind):
    """Disable one guard."""
    if guard == "integrity":
        real = delivery.verified_files
        monkeypatch.setattr(
            delivery, "verified_files", lambda folder: (real(folder)[0], [])
        )
    elif kind == "trust":
        # Mutant: the bundle's own contract digest is trusted, not the
        # published one.
        def trusted(documents):
            challenge = documents["recipe.json"]["challenge"]
            recorded = documents["manifest.json"]["contract_digest"]
            return challenge["id"], challenge["version"], recorded

        monkeypatch.setattr(bs, "published_contract", trusted)
    else:
        monkeypatch.setattr(bs, guard, lambda *_, **__: None)


# -- conversion and parity ---------------------------------------------------------------------
def test_a_run5_style_bundle_converts_against_the_published_contract(tmp_path, level0):
    from carbon.challenge_registry import registry
    from carbon.development_session.research_loop import candidate_record

    folder = write_bundle(tmp_path / "bundle", RUN5, level0)
    assert delivery.clean_rebuild(folder)["status"] == "REBUILT"
    out = tmp_path / "out" / "submission.json"
    report = bs.convert(folder, out)
    published = registry.describe(BATTERY, "1.0")["contract_digest"]
    record = json.loads(out.read_bytes())
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert report["status"] == "CONVERTED"
    assert report["submitted"] is False and report["signed"] is False
    assert report["contract_digest"] == published == record["contract_digest"]
    assert out.read_bytes() == canonical(
        candidate_record(RUN5, bs.reason_for(manifest), False)
    )
    assert report["submission_digest"] == digest(out.read_bytes())
    assert record["reconstruction_profile_digest"] == level0["recipe_digest"]
    assert record["strategy_hash"] == level0["strategy_hash"]
    assert record["final_evidence"] is False and record["used_feedback"] is False
    assert "freeze_candidate" in report["next_step"]
    # Idempotent: the same bytes again are not a conflict.
    assert bs.convert(folder, out)["submission_digest"] == report["submission_digest"]


def prepared_campaign(tmp_path, strategy):
    """A miner's (agent none) battery campaign with a practice result for
    `strategy`, as `test_miner_freeze_submit` builds one; its evaluation is
    the real battery path through an intake."""
    from carbon.battery import campaign as battery
    from carbon.development_session import research_campaign as campaign
    from carbon.development_session.research_ledger import CampaignLedger

    root = tmp_path / "launchpad"
    root.mkdir(mode=0o700)
    ledger = CampaignLedger(root / "campaign", clock=lambda: 1000)
    with ledger.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
        )
        body = canonical({"provenance": "REAL_JAX_PUBLIC_PRACTICE", "recipe": strategy})
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("miner", "task-0", body, digest(body)),
        )
    manifest = {"owner": "miner", "agent": "none", "challenge": BATTERY}
    (ledger.root / "campaign-manifest.json").write_bytes(canonical(manifest))
    return campaign.PreparedCampaign(
        args=SimpleNamespace(intakes={BATTERY: "https://intake.invalid"}),
        ledger=ledger,
        owner="miner",
        manifest=manifest,
        seeds={},
        role_root=None,
        data=None,
        image=None,
        key=None,
        config=None,
        composition=SimpleNamespace(tasks=SimpleNamespace(close=lambda: None)),
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key="fixture-signer")),
        task=None,
        grant=None,
        agent_policy=None,
        campaign=SimpleNamespace(
            evaluate=battery.evaluate_frozen, refusal_retains_candidate=True
        ),
    )


def test_parity_the_launchpad_freezes_and_submits_the_same_bytes(
    tmp_path, level0, monkeypatch
):
    from carbon.battery import campaign as battery
    from carbon.battery import intake_client
    from carbon.battery.remote_submission import IntakeRefusal
    from carbon.development_session import research_campaign as campaign

    folder = write_bundle(tmp_path / "bundle", RUN5, level0)
    out = tmp_path / "submission.json"
    bs.convert(folder, out)
    converted = json.loads(out.read_bytes())

    monkeypatch.setattr(campaign, "report", lambda *_, **__: None)
    value = prepared_campaign(tmp_path, converted["strategy"])
    # The Launchpad's freeze, given the record's own fields.
    asyncio.run(
        campaign.freeze_candidate(
            value,
            strategy=converted["strategy"],
            reason=converted["reason"],
            used_feedback=converted["used_feedback"],
        )
    )
    frozen = value.ledger.root / "epoch-1" / "selected-recipe.json"
    assert frozen.read_bytes() == out.read_bytes()

    # The Launchpad's submit, to the point where the miner's signer would
    # sign: captured, nothing signed or sent.
    sent = []

    def capture(url, signer, *, root, epoch, strategy, contract_digest, **_):
        sent.append({"strategy": strategy, "contract_digest": contract_digest})
        raise IntakeRefusal("fixture_captured")

    monkeypatch.setattr(battery, "submit_through_intake", capture)
    with pytest.raises(campaign.OperationRefused):
        asyncio.run(campaign.submit_frozen(value))
    assert sent == [
        {
            "strategy": converted["strategy"],
            "contract_digest": converted["contract_digest"],
        }
    ]
    hotkey = "5Fixture" + "x" * 40
    assert intake_client.submission_id(
        hotkey, sent[0]["strategy"], sent[0]["contract_digest"]
    ) == intake_client.submission_id(
        hotkey, converted["strategy"], converted["contract_digest"]
    )


# -- refusals and one mutation per guard ---------------------------------------------------
@pytest.mark.parametrize(
    "code, build, guard, kind, bypass", GUARDS, ids=[g[0] for g in GUARDS]
)
def test_each_refusal_produces_nothing_and_its_mutant_turns_it_red(
    tmp_path, level0, level1, monkeypatch, code, build, guard, kind, bypass
):
    folder = build(tmp_path, level0, level1)
    for name in bypass:
        monkeypatch.setattr(bs, name, lambda *_, **__: None)
    out = tmp_path / "out" / "submission.json"
    assert outcome(folder, out) == code
    assert not out.exists() and not out.parent.exists()
    mutate(monkeypatch, guard, kind)
    assert outcome(folder, tmp_path / "mutant.json") != code


def test_a_level1_bundle_is_refused_as_a_development_level(tmp_path, level0, level1):
    folder = level_one(tmp_path, level0, level1)
    assert level1["development"]["level"] == 1
    # Carbon rebuilds it through its variant: refused for what it is.
    assert delivery.clean_rebuild(folder)["status"] == "REBUILT"
    with pytest.raises(bs.Refused) as refused:
        bs.convert(folder, tmp_path / "out.json")
    assert refused.value.code == bs.DEVELOPMENT_LEVEL
    assert not (tmp_path / "out.json").exists()


def test_a_variant_digest_bundle_is_refused(tmp_path, level0, level1):
    from carbon.reconstruction.capability_registry import is_development_variant

    assert is_development_variant(L1_VARIANT)
    folder = variant_digest(tmp_path, level0, level1)
    with pytest.raises(bs.Refused) as refused:
        bs.convert(folder, tmp_path / "out.json")
    assert refused.value.code == bs.DEVELOPMENT_VARIANT
    assert refused.value.detail == ["manifest.json", "recipe.json"]


def test_a_tampered_bundle_digest_is_refused(tmp_path, level0, level1):
    folder = tampered(tmp_path, level0, level1)
    with pytest.raises(bs.Refused) as refused:
        bs.convert(folder, tmp_path / "out.json")
    assert refused.value.code == bs.BUNDLE_TAMPERED
    assert refused.value.detail == ["digest:strategy.json"]
    # A forged manifest digest is a mismatch too.
    other = write_bundle(tmp_path / "other", RUN5, level0)
    manifest = json.loads((other / "manifest.json").read_bytes())
    manifest["files"]["recipe.json"] = FORGED
    (other / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(bs.Refused) as refused:
        bs.convert(other, tmp_path / "out.json")
    assert refused.value.detail == ["digest:recipe.json"]


def test_an_existing_output_is_never_overwritten(tmp_path, level0, monkeypatch):
    folder = write_bundle(tmp_path / "bundle", RUN5, level0)
    out = tmp_path / "submission.json"
    out.write_bytes(b"someone else's file")
    assert outcome(folder, out) == bs.OUTPUT_EXISTS
    assert out.read_bytes() == b"someone else's file"
    # Mutant: the guard removed; the write is no longer a typed refusal.
    monkeypatch.setattr(bs, "check_output", lambda *_: None)
    with pytest.raises(ValueError) as raised:
        bs.convert(folder, out)
    assert not isinstance(raised.value, bs.Refused)


def test_every_refusal_code_is_tested():
    tested = {g[0] for g in GUARDS} | {bs.OUTPUT_EXISTS}
    assert tested | {bs.CHALLENGE_NOT_PUBLISHED} == set(bs.REFUSALS)


def test_a_bundle_naming_an_unregistered_challenge_is_refused(tmp_path, level0):
    recipe = {**level0, "challenge": {"id": "no-such-challenge", "version": "1.0"}}
    strategy = {**RUN5, "challenge_id": "no-such-challenge"}
    folder = write_bundle(tmp_path / "bundle", strategy, recipe)
    with pytest.raises(bs.Refused) as refused:
        bs.convert(folder, tmp_path / "out.json")
    assert refused.value.code == bs.CHALLENGE_NOT_PUBLISHED
    assert refused.value.detail == ["challenge_unknown"]


# -- the command ---------------------------------------------------------------------------
def test_the_command_never_reaches_the_network(
    tmp_path, level0, level1, monkeypatch, capsys
):
    def refused(*_, **__):
        raise AssertionError("the converter opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    folder = write_bundle(tmp_path / "bundle", RUN5, level0)
    out = tmp_path / "submission.json"
    assert bs.main(["--bundle", str(folder), "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "CONVERTED" and printed["submitted"] is False
    assert "submit" in printed["next_step"]
    bad = level_one(tmp_path / "l1", level0, level1)
    assert bs.main(["--bundle", str(bad), "--out", str(tmp_path / "x.json")]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["code"] == bs.DEVELOPMENT_LEVEL and printed["written"] is False
    assert not (tmp_path / "x.json").exists()
