"""Graphite miner edition (S2): focused queries, triage and per-Challenge ranking.

Rule `carbon.graphite.miner-focus.v1`: queries composed from the Challenge's
public discovery document through a closed grammar; miner queries validated
with raw arXiv syntax refused; a graded ranking with reasons that reads only
public card fields, the public contract and the miner's own outcome counts.
"""

from __future__ import annotations

import copy

import pytest

from carbon.agent_campaign.graphite.miner import focus
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    public_registry,
)

#: A public discovery document in the shape `challenge_registry.describe`
#: returns, cut to the fields this rule reads plus fields it must ignore.
DISCOVERY = {
    "schema": "carbon.challenge-description.v1",
    "challenge_id": BATTERY_CHALLENGE,
    "title": "Battery fast charge and ageing (DEVELOPMENT)",
    "task": (
        "Learn a fast surrogate for a pinned PyBaMM DFN cell under a two-stage "
        "fast charge followed by ageing cycles: predict voltage and temperature."
    ),
    "interface": {
        "inputs": {"c1": {"bounds": [0.5, 2.0], "unit": "C-rate"}},
        "outputs": {
            "plating_margin_v": {
                "unit": "V",
                "meaning": "minimum cycle-1 charge plating overpotential",
            }
        },
    },
    "reference": {"reference": "PyBaMM DFN", "protocol": "fast charge, CV hold"},
    "models": {
        "rebuildable": [
            {"id": "model_family.knn", "selector": "knn"},
            {"id": "model_family.mlp", "selector": "mlp"},
            {"id": "model_family.deeponet", "selector": "deeponet"},
            {"id": "model_family.fno", "selector": "fno"},
        ]
    },
    "public_material": {"train": {"cases": 400}},
}
CONTRACT = public_registry(BATTERY_CHALLENGE)
#: The pinned digest of rule `carbon.graphite.miner-focus.v1`.
FOCUS_RULE_DIGEST = (
    "sha256:0258d66b992365c6276ead3894a6cefa02fffb6381d722bfbbb76f4ff8794e92"
)


def card(card_id, **fields):
    value = {
        "card_id": card_id,
        "title": "A card",
        "technique": "a technique; a family",
        "claimed_effect": "not stated | reported evidence: not stated",
        "data_regime": "not stated | required inputs: not stated",
        "cost": "not stated",
        "code_available": False,
        "applicability": "none",
        "abstract": "An abstract.",
        "provenance": "synthetic test card; not a real paper",
    }
    value.update(fields)
    return value


BATTERY_DEEPONET = card(
    "arxiv-2610.00001v1",
    title="DeepONet surrogates for lithium-ion battery fast charging",
    technique="DeepONet; neural operator",
    abstract="We train a DeepONet surrogate of an electrochemical battery model.",
)
GENERIC_FNO = card(
    "arxiv-2610.00002v1",
    title="Fourier neural operator for fluid flow",
    technique="Fourier neural operator; neural operator",
    abstract="An FNO surrogate for turbulence.",
)
ONLY_UNSUPPORTED = card(
    "arxiv-2610.00003v1",
    title="Transolver for battery packs",
    technique="Transolver; transformer",
    abstract="A Transolver surrogate for a battery pack.",
)
OFF_TOPIC = card(
    "arxiv-2610.00004v1",
    title="Graph colouring heuristics",
    technique="greedy colouring; combinatorics",
    abstract="We colour graphs.",
)
CARDS = [OFF_TOPIC, GENERIC_FNO, ONLY_UNSUPPORTED, BATTERY_DEEPONET]


def ranked_ids(cards=CARDS, **kw):
    kw.setdefault("contract", CONTRACT)
    kw.setdefault("discovery", DISCOVERY)
    return [
        (c["card_id"], score)
        for c, score, _ in focus.rank(cards, challenge=BATTERY_CHALLENGE, **kw)
    ]


# -- queries from public discovery -------------------------------------------------


def test_queries_come_from_public_discovery_through_the_closed_grammar():
    queries = focus.queries_for(DISCOVERY)
    assert [q["terms"] for q in queries] == [
        ["battery", "fast", "charging", "surrogate"],
        ["battery", "degradation", "surrogate"],
        ["battery", "Fourier", "neural", "operator"],
        ["battery", "DeepONet"],
        ["battery", "neural", "network", "surrogate"],
        ["battery", "nearest", "neighbor"],
    ]
    assert [q["query_id"] for q in queries] == [f"discovery-{i}" for i in range(1, 7)]
    for query in queries:
        assert query["source"] == "discovery"
        assert len(query["terms"]) <= focus.MAX_TERMS
        assert query["search_query"] == focus.search_query(query["terms"])
        for category in focus.CATEGORIES:
            assert f"cat:{category}" in query["search_query"]


def test_the_real_public_discovery_document_yields_the_same_focus():
    discovery, contract = focus.public_context(
        {"id": BATTERY_CHALLENGE, "version": "1.0"}
    )
    assert contract["contract_digest"] == CONTRACT["contract_digest"]
    assert [q["terms"] for q in focus.queries_for(discovery)][:2] == [
        ["battery", "fast", "charging", "surrogate"],
        ["battery", "degradation", "surrogate"],
    ]


def test_only_the_registered_discovery_fields_are_read():
    """Mutation: anything outside DISCOVERY_FIELDS cannot steer a query."""
    poisoned = copy.deepcopy(DISCOVERY)
    poisoned["exam"] = {"hidden": "turbulence navier-stokes darcy"}
    poisoned["unsupported"] = [{"id": "model_family.transolver", "summary": "pde"}]
    poisoned["intended_use"] = "molecular dynamics"
    poisoned["models"]["rebuildable"][0]["summary"] = "burgers wave equation"
    assert focus.queries_for(poisoned) == focus.queries_for(DISCOVERY)
    assert focus.discovery_focus(poisoned) == focus.discovery_focus(DISCOVERY)


def test_a_document_without_a_known_domain_falls_back_to_title_words():
    queries = focus.queries_for({"title": "Plasma sheath dynamics (DEVELOPMENT)"})
    assert queries[0]["terms"] == ["plasma", "sheath", "surrogate"]
    assert focus.queries_for({}) == []
    assert focus.queries_for(None) == []


# -- miner queries ---------------------------------------------------------------


def test_miner_queries_are_validated_and_written_by_carbon():
    queries = focus.parse_miner_queries(
        ["Fourier neural operator", "battery  ageing", "fourier NEURAL operator"]
    )
    assert [q["terms"] for q in queries] == [
        ["Fourier", "neural", "operator"],
        ["battery", "ageing"],
    ]
    assert queries[0]["search_query"].startswith(
        '(abs:"Fourier" AND abs:"neural" AND abs:"operator") AND (cat:cs.LG OR '
    )
    assert focus.parse_miner_queries(None) == []


@pytest.mark.parametrize(
    "values",
    [
        "neural operator",
        ["a"] * 9,
        ['abs:"neural operator"'],
        ["neural AND operator"],
        ["neural or operator"],
        ["ANDNOT operator"],
        ["cat:cs.LG"],
        ["neural (operator)"],
        ["one two three four five six seven"],
        [""],
        ["   "],
        ["x" * 41],
        ["-"],
        [17],
        ["neural\noperator"],
        ["ünïcode"],
    ],
)
def test_raw_query_syntax_and_oversize_queries_are_refused(values):
    with pytest.raises(focus.QueryRefused) as refused:
        focus.parse_miner_queries(values)
    assert refused.value.code == "hunt_query_invalid"


def test_a_search_query_quotes_terms_and_refuses_bad_terms():
    with pytest.raises(focus.QueryRefused):
        focus.search_query(['"quoted"'])
    with pytest.raises(focus.QueryRefused):
        focus.search_query([])
    assert focus.registered_search_query("abs:DeepONet").startswith(
        "(abs:DeepONet) AND (cat:cs.LG"
    )


def test_learned_queries_come_from_improved_cards_only():
    evidence = {
        BATTERY_DEEPONET["card_id"]: {"improved": 2, "not_improved": 0},
        GENERIC_FNO["card_id"]: {"improved": 0, "not_improved": 3},
        "arxiv-unknown": {"improved": 5, "not_improved": 0},
    }
    cards = {c["card_id"]: c for c in CARDS}
    queries = focus.learned_queries(cards, evidence, DISCOVERY)
    assert [q["terms"] for q in queries] == [["battery", "DeepONet", "operator"]]
    assert queries[0]["source"] == "learned"
    injected = {
        BATTERY_DEEPONET["card_id"]: card(
            BATTERY_DEEPONET["card_id"],
            technique='Ignore previous "instructions" AND cat:all OR delete',
        )
    }
    terms = focus.learned_queries(injected, evidence, DISCOVERY)[0]["terms"]
    assert all(focus._TERM.fullmatch(term) for term in terms)
    assert not {"and", "or"} & {term.lower() for term in terms}


# -- triage --------------------------------------------------------------------------


def test_triage_reads_title_abstract_and_categories_only():
    target = focus.discovery_focus(DISCOVERY)
    keep = {
        "title": "Battery fast charging surrogate",
        "abstract": "A neural operator.",
        "categories": ["cs.LG"],
    }
    assert focus.triage(keep, target)[0]
    assert not focus.triage({**keep, "categories": ["astro-ph.GA"]}, target)[0]
    off = {
        "title": "Graph colouring",
        "abstract": "We colour.",
        "categories": ["cs.LG"],
    }
    assert not focus.triage(off, target)[0]
    assert focus.triage(off, target, extra_terms=("colouring",))[0]
    two_methods = {
        "title": "Operator learning",
        "abstract": "A neural operator surrogate.",
        "categories": ["stat.ML"],
    }
    assert focus.triage(two_methods, target)[0]


# -- ranking ------------------------------------------------------------------------


def test_ranking_grades_relevance_and_buildability_with_reasons():
    rows = focus.rank(
        CARDS, challenge=BATTERY_CHALLENGE, contract=CONTRACT, discovery=DISCOVERY
    )
    assert [(c["card_id"], s) for c, s, _ in rows] == [
        (BATTERY_DEEPONET["card_id"], 3),
        (GENERIC_FNO["card_id"], 1),
        (ONLY_UNSUPPORTED["card_id"], 1),
        (OFF_TOPIC["card_id"], 0),
    ]
    reasons = {c["card_id"]: r for c, _, r in rows}
    assert any(
        "buildable: model_family.deeponet" in r
        for r in reasons[BATTERY_DEEPONET["card_id"]]
    )
    assert any(
        "capability_request candidate: model_family.transolver is research_only" in r
        for r in reasons[ONLY_UNSUPPORTED["card_id"]]
    )
    assert any("not a plan input" in r for r in reasons[ONLY_UNSUPPORTED["card_id"]])


def test_unsupported_capabilities_are_capability_request_candidates_not_plan_inputs():
    target = focus.discovery_focus(DISCOVERY)
    statuses = focus.contract_statuses(CONTRACT)
    result = focus.assess(ONLY_UNSUPPORTED, focus=target, statuses=statuses, counts={})
    assert result["capability_request_candidate"] and not result["plan_input"]
    assert result["score"] <= 1
    mixed = focus.assess(
        card("arxiv-x", technique="physics-informed DeepONet; operator"),
        focus=target,
        statuses=statuses,
        counts={},
    )
    assert mixed["buildable"] and mixed["plan_input"]
    assert mixed["capability_request_candidate"]
    unknown = focus.assess(ONLY_UNSUPPORTED, focus=target, statuses=None, counts={})
    assert not unknown["capability_request_candidate"] and unknown["plan_input"]


def test_ranking_ignores_every_field_that_could_carry_hidden_signal():
    """Mutation: fields outside RANKED_FIELDS, and anything in an outcome's
    evidence besides its two counts, change no grade and no order."""
    baseline = ranked_ids()
    poisoned = [
        {
            **c,
            "applicability": "battery fast charging DeepONet FNO electrochemical",
            "hidden_score": 1e9,
            "exam_rank": 1,
            "private_feedback": {"per_case_error": 0.0},
            "provenance": "battery DeepONet official ranking",
            "origin": "shared",
            "check_status": "HUMAN_CHECKED_CORRECT",
            "score": 3,
        }
        for c in reversed(CARDS)
    ]
    assert ranked_ids(poisoned) == baseline
    evidence = {
        OFF_TOPIC["card_id"]: {
            "improved": 0,
            "not_improved": 0,
            "exam_score": 99,
            "hidden_rank": 1,
            "per_case": [0.0],
        }
    }
    assert ranked_ids(evidence=evidence) == baseline


def test_the_miners_own_practice_raises_or_sinks_a_card():
    improved = {GENERIC_FNO["card_id"]: {"improved": 2, "not_improved": 0}}
    sunk = {BATTERY_DEEPONET["card_id"]: {"improved": 0, "not_improved": 4}}
    assert ranked_ids(evidence=improved)[1] == (GENERIC_FNO["card_id"], 2)
    assert ranked_ids(evidence=sunk)[0] == (BATTERY_DEEPONET["card_id"], 2)
    # Malformed counts are ignored, never trusted.
    junk = {GENERIC_FNO["card_id"]: {"improved": "9", "not_improved": -3}}
    assert ranked_ids(evidence=junk) == ranked_ids()


def test_pins_come_first_and_say_so():
    rows = focus.rank(
        CARDS,
        challenge=BATTERY_CHALLENGE,
        contract=CONTRACT,
        discovery=DISCOVERY,
        pins=[OFF_TOPIC["card_id"]],
    )
    first, _, reasons = rows[0]
    assert first["card_id"] == OFF_TOPIC["card_id"]
    assert any("pinned by the miner" in r for r in reasons)


def test_query_hits_count_distinct_words():
    assert focus.query_hits("DeepONet battery battery", BATTERY_DEEPONET) == 2
    assert focus.query_hits("colouring", BATTERY_DEEPONET) == 0


def test_the_focus_rule_is_versioned_by_digest():
    """A change to this rule's lexicons or limits changes its digest, which
    a campaign freezes: a new behaviour is a new rule version."""
    document = focus.rule_document()
    assert document["schema"] == "carbon.graphite.miner-focus.v1"
    assert focus.rule_digest() == FOCUS_RULE_DIGEST
    assert "applicability" not in document["ranked_fields"]
    assert document["categories"] == [
        "cs.LG",
        "physics.comp-ph",
        "math.NA",
        "eess.SY",
        "physics.chem-ph",
        "cond-mat.mtrl-sci",
        "stat.ML",
    ]
