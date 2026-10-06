"""Literature for a named Challenge (VALIDATOR-08).

Pins:
- each Challenge's literature profile is registered and pinned; battery's
  phase-2 query set and pipeline are untouched;
- the free pre-filter keeps a Challenge's domain papers and drops the rest
  before any paid call;
- extraction for a Challenge uses the Challenge-neutral Reader prompt and
  card schema v2, only on records its own query set retrieved;
- a Challenge's snapshot (v3) grades and ranks its cards; a session offered
  it lists them best first and records its Challenge, ranking rule and
  unchecked fraction; an unranked offer's record keeps its old keys;
- phase 3 refuses another Challenge's snapshot;
- a live per-Challenge extraction runs only under the literature grant.

Synthetic feeds and a scripted Reader: no network, key or spend.
"""

import json
from pathlib import Path

import graphite_phase2_fixtures as f
import pytest

from carbon.agent_campaign.graphite import challenge_literature as cl
from carbon.agent_campaign.graphite import literature_fetch as lf
from carbon.agent_campaign.graphite import method_cards as mc
from carbon.agent_campaign.graphite import phase2, phase3
from carbon.agent_campaign.graphite.miner.hunt import (
    READER_PROMPT,
    READER_PROMPT_DIGEST,
)

REPOSITORY = Path(__file__).resolve().parents[2]
COOLING, MOTOR = "chip-cold-plate", "electric-motor-magnetics"
BATTERY = "battery-fastcharge-ageing-development-v1"


def test_profiles_are_registered_and_battery_keeps_its_queries():
    profiles = cl.load_profiles()
    assert set(profiles) == {COOLING, MOTOR}
    for profile in profiles.values():
        assert profile.query_set.version != lf.QUERY_SET.version
        assert len(profile.query_set.queries) == 6
        rule = profile.ranking_rule()
        assert rule["rule"] == cl.RANK_RULE and rule["profile_digest"] == profile.digest
        assert "applicability" not in rule["ranked_fields"]
    assert lf.QUERY_SET.version == "graphite-phase2-queries.v1"
    with pytest.raises(cl.LiteratureProfileRefused, match="not_registered"):
        cl.profile_for(BATTERY)


def test_an_altered_profile_is_refused(tmp_path):
    import shutil

    directory = tmp_path / "profiles"
    shutil.copytree(cl.PROFILE_DIR, directory)
    path = directory / f"{COOLING}.json"
    document = json.loads(path.read_text())
    path.write_text(json.dumps({**document, "categories": ["cs.LG"]}))
    with pytest.raises(cl.LiteratureProfileRefused, match="altered"):
        cl.load_profiles(directory)


def _record(title, abstract, categories=("physics.flu-dyn",)):
    return {"title": title, "abstract": abstract, "categories": list(categories)}


def test_the_free_prefilter_keeps_only_the_challenges_domain():
    cooling, motor = cl.profile_for(COOLING), cl.profile_for(MOTOR)
    plate = _record(
        "Learning a cold plate", "A surrogate for microchannel heat transfer."
    )
    machine = _record(
        "Torque ripple of a PMSM",
        "A neural network predicts torque ripple of a permanent magnet motor.",
        ("eess.SY",),
    )
    battery = _record(
        "Battery ageing", "Electrochemical ageing of lithium cells.", ("cs.LG",)
    )
    assert cooling.triage(plate)[0] and not cooling.triage(machine)[0]
    assert motor.triage(machine)[0] and not motor.triage(plate)[0]
    assert not cooling.triage(battery)[0] and not motor.triage(battery)[0]
    off_category = _record("A cold plate", "Heat transfer.", ("q-bio.GN",))
    assert cooling.triage(off_category) == (False, ["category outside the profile"])
    # Whole phrases only: "heat sinking" does not name a heat sink.
    assert not cooling.triage(_record("Heat sinking ideas", "Prose about sinks."))[0]


def test_grades_follow_the_cues_and_ignore_applicability():
    cooling = cl.profile_for(COOLING)
    card = {
        "title": "A cold plate surrogate",
        "technique": "neural operator; neural operator",
        "claimed_effect": "fast",
        "data_regime": "cfd",
        "abstract": "Heat transfer in a cold plate.",
        "code_available": True,
        "applicability": "battery battery battery",
    }
    assert cooling.grade(card)[0] == 3
    assert cooling.grade({**card, "code_available": False})[0] == 2
    assert (
        cooling.grade({**card, "title": "x", "abstract": "y", "technique": "z"})[0] == 1
    )
    nothing = {k: "unrelated" for k in card if k != "code_available"}
    nothing["applicability"] = "cold plate heat transfer surrogate"
    assert cooling.grade({**nothing, "code_available": False})[0] == 0


def _seed(root, profile, entries):
    """A raw store with `entries` retrieved by `profile`'s first query, and a
    battery-query record beside them."""
    store = lf.RawStore(Path(root) / "raw")
    answers = [f.feed(*entries)] + [f.feed()] * (len(profile.query_set.queries) - 1)
    fetcher, _ = f.client(answers)
    lf.backfill(
        fetcher,
        store,
        query_set=profile.query_set,
        page_size=len(entries) + 1,
        now=lambda: "2026-10-05T00:00:00Z",
    )
    other, _ = f.client([f.feed(f.entry(90))])
    lf.backfill(
        other,
        store,
        query_set=f.one_query(),
        page_size=2,
        now=lambda: "2026-10-05T00:00:00Z",
    )
    return store


COOLING_ENTRIES = (
    f.entry(
        1,
        title="Neural operator for a cold plate",
        abstract="A surrogate of conjugate heat transfer in a microchannel cold plate.",
        categories=("physics.flu-dyn",),
    ),
    f.entry(
        2,
        title="Thermal CFD emulator",
        abstract="A neural operator surrogate for convective heat transfer.",
        categories=("cs.LG",),
    ),
    f.entry(
        3,
        title="Genome assembly",
        abstract="Unrelated biology.",
        categories=("q-bio.GN",),
    ),
)


def test_extraction_uses_the_neutral_prompt_on_the_challenges_records_only(tmp_path):
    profile = cl.profile_for(COOLING)
    raw = _seed(tmp_path, profile, COOLING_ENTRIES)
    model = f.scripted(f.replies(2))
    backfill = f.backfill(tmp_path, raw, model, profile=profile)
    assert (
        len(backfill.pending()) == 2
    )  # the off-category paper and battery's record are not paid for
    summary = backfill.run("cooling-1")
    assert summary["status"] == "COMPLETED" and summary["cards_made"] == 2
    for request in model.requests:
        assert request["instructions"] == READER_PROMPT
    cards = backfill.cards.cards()
    assert {card["schema"] for card in cards} == {mc.CARD_SCHEMA_V2}
    assert {card["extraction"]["prompt_digest"] for card in cards} == {
        READER_PROMPT_DIGEST
    }
    run = json.loads((backfill.root / "runs" / "cooling-1" / "run.json").read_bytes())
    assert run["challenge_id"] == COOLING and run["profile_digest"] == profile.digest
    assert run["query_set_digest"] == profile.query_set.digest


def _cooling_snapshot(tmp_path, *, code=(True, False)):
    profile = cl.profile_for(COOLING)
    raw = _seed(tmp_path, profile, COOLING_ENTRIES)
    model = f.scripted(
        [
            f.reply(code_available=code[0], method_name="Cold plate operator"),
            f.reply(code_available=code[1]),
        ]
    )
    backfill = f.backfill(tmp_path, raw, model, profile=profile)
    backfill.run("cooling-1")
    index, document = mc.challenge_snapshot(
        backfill.cards, raw, profile, label="graphite-literature-test"
    )
    address = mc.write_snapshot(backfill.cards, document)
    path = backfill.cards.root / "snapshots" / (address[7:] + ".json")
    return profile, index, document, path


def test_a_challenge_snapshot_is_graded_ranked_and_recorded(tmp_path):
    profile, index, document, path = _cooling_snapshot(tmp_path)
    assert document["schema"] == mc.SNAPSHOT_SCHEMA_V3
    assert document["challenge_id"] == COOLING
    assert document["ranking"]["digest"] == profile.ranking_rule()["digest"]
    grades = [grade for _, grade in document["ranked"]]
    assert grades == sorted(grades, reverse=True) and min(grades) >= 1
    assert [c["card_id"] for c in index.cards] == [cid for cid, _ in document["ranked"]]
    offered = mc.offered_literature(path, allow_unchecked=True)
    assert offered.challenge_id == COOLING
    assert [row["card_id"] for row in offered.catalogue()] == [
        cid for cid, _ in document["ranked"]
    ]
    record = offered.record()
    assert record["challenge_id"] == COOLING
    assert record["ranking_rule_digest"] == document["ranking"]["digest"]
    assert record["unchecked_fraction"] == f"{len(index.cards)}/{len(index.cards)}"
    brief = phase3.literature_brief(offered)
    assert [row["card_id"] for row in brief["cards"]] == [
        cid for cid, _ in document["ranked"]
    ]
    # Checked-only: nothing checked yet, so an empty, still-ranked offer.
    assert mc.offered_literature(path).empty


def test_an_unranked_offer_keeps_its_record_keys(tmp_path):
    raw = f.seed(tmp_path, f.entry(1), f.entry(2))
    backfill = f.backfill(tmp_path, raw, f.scripted(f.replies(2)))
    backfill.run("battery-1")
    _index, document = mc.snapshot(
        backfill.cards, raw, label="phase2-test", query_set_digest=lf.QUERY_SET.digest
    )
    address = mc.write_snapshot(backfill.cards, document)
    offered = mc.offered_literature(
        backfill.cards.root / "snapshots" / (address[7:] + ".json"),
        allow_unchecked=True,
    )
    assert offered.challenge_id is None and "ranking" not in offered.document()
    assert not {"challenge_id", "ranking_rule_digest", "unchecked_fraction"} & set(
        offered.record()
    )


def test_phase3_refuses_another_challenges_literature(tmp_path):
    _profile, _index, _document, path = _cooling_snapshot(tmp_path)
    cooling = mc.offered_literature(path, allow_unchecked=True)
    phase3.check_literature_challenge(cooling, COOLING, phase3.RunnerRefused)
    with pytest.raises(phase3.RunnerRefused):
        phase3.check_literature_challenge(cooling, BATTERY, phase3.RunnerRefused)
    raw = f.seed(tmp_path / "b", f.entry(1))
    backfill = f.backfill(tmp_path / "b", raw, f.scripted(f.replies(1)))
    backfill.run("battery-1")
    _index, document = mc.snapshot(
        backfill.cards, raw, label="phase2-test", query_set_digest=lf.QUERY_SET.digest
    )
    address = mc.write_snapshot(backfill.cards, document)
    battery = mc.offered_literature(
        backfill.cards.root / "snapshots" / (address[7:] + ".json"),
        allow_unchecked=True,
    )
    phase3.check_literature_challenge(battery, BATTERY, phase3.RunnerRefused)
    with pytest.raises(phase3.RunnerRefused):
        phase3.check_literature_challenge(battery, COOLING, phase3.RunnerRefused)


def test_a_live_challenge_extraction_needs_the_literature_grant(tmp_path, capsys):
    tmp_path.chmod(0o700)
    argv = [
        "triage",
        "--root",
        str(tmp_path / "root"),
        "--challenge",
        COOLING,
        "--grant",
        str(f.GRANT_FILE),
        "--credential-env",
        "ENGY_API_KEY",
    ]
    with pytest.raises(SystemExit):
        phase2.main(argv)
    out = capsys.readouterr().out
    assert "grant_is_not_the_literature_grant" in out
    with pytest.raises(SystemExit):
        phase2.main(["snapshot", "--root", str(tmp_path / "root"), "--challenge", "x"])
    assert "literature_profile_not_registered" in capsys.readouterr().out


def test_the_literature_grant_is_the_owners():
    from carbon.agent_campaign.grant import SpendingGrant

    path = (
        REPOSITORY
        / "docs/development/graphite/grants/GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR.json"
    )
    grant = SpendingGrant.from_document(json.loads(path.read_text()))
    assert grant.grant_id == phase2.LITERATURE_GRANT
    assert (str(grant.monetary_ceiling), str(grant.worst_case_run_cost)) == (
        "4.00",
        "2.49",
    )
    assert (str(grant.cleanup_allowance), grant.permitted_runs) == ("0.10", 3)
    assert grant.max_runtime_s == 360000
