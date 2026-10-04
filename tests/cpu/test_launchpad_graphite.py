"""Graphite in the Launchpad: the agent choice and its launch (S4).

OWNER-GRAPHITE-MINER-01: Graphite's miner edition replaces the `autonomous`
agent for new Launchpad campaigns. A new launch naming `autonomous` is refused
`autonomous_agent_replaced` after the replay gate, so a launch recorded under
it still replays and a queued one is still carried out. A Graphite launch
carries its mode, research share, plan, hunt and limits, validated before
anything is created, and the miner's curation digest captured at admission.

What is real here: the campaign host (`RunnerAdapter`), the operations table
and its gates, both doors, setup's agent step, the capability document, the
projection and the campaign view. DEVELOPMENT FIXTURES, by name: the journey
host (`journey_fixture`, a stub chain and the fixture Challenge), and S2's and
S3's interfaces - the miner's library, the shared card pack and the plan rule
- as in-memory fakes (`FakeLibrary`), because those slices land separately.
Nothing here reaches a chain, a provider, arXiv or a pod.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad.controller import Rejected

PRINCIPAL = "alice"
KEY = "graphite-launch-key-000001"


# --- fixtures ----------------------------------------------------------------


def card(card_id, origin="shared", **extra):
    return {
        "card_id": card_id,
        "title": "A method for " + card_id,
        "abstract": "We train a surrogate.",
        "technique": "neural operator; operator learning",
        "claimed_effect": "faster training | reported evidence: a benchmark",
        "data_regime": "small data | required inputs: simulations",
        "cost": "not stated",
        "code_available": False,
        "applicability": "battery surrogate",
        "provenance": "arXiv 2101.00001v1; method card UNCHECKED",
        "origin": origin,
        **extra,
    }


try:  # S2's own typed refusal, once the literature slice is on this branch.
    from carbon.agent_campaign.graphite.miner.library import LibraryError
except ImportError:

    class LibraryError(ValueError):
        """DEVELOPMENT FIXTURE: S2's `library.LibraryError` as S2 defines it -
        a ValueError carrying a closed `.code` - until S2 is on this base."""

        def __init__(self, code, detail=""):
            super().__init__(code + (": " + detail if detail else ""))
            self.code, self.detail = code, detail


class FakeLibrary:
    """DEVELOPMENT FIXTURE: S2's `MinerLibrary` contract, in memory, refusing
    as S2 refuses (`LibraryError` with a closed code) and answering in S2's
    shapes. It answers searches with every card it holds - banned and
    protected ones too - so the door's own filters are what is tested."""

    def __init__(self, cards=()):
        self.cards = {c["card_id"]: dict(c) for c in cards}
        self.pins, self.bans = [], []
        self.imports, self.saved = [], {}
        self.writes, self.searches = [], []
        #: A text this library refuses to queue (S2's `import_invalid`).
        self.refused_text = None

    def _digest(self):
        return digest(canonical({"pins": sorted(self.pins), "bans": sorted(self.bans)}))

    def curation(self):
        return {
            "pins": list(self.pins),
            "bans": list(self.bans),
            "digest": self._digest(),
        }

    def search(self, query, *, challenge, limit=10, bans=(), pins=()):
        self.searches.append(
            {"query": query, "challenge": challenge, "limit": limit, "bans": bans}
        )
        return [
            {
                **c,
                "score": 2.5,
                "reasons": ["matches the Challenge's task"],
                "plan_input": c.get("plan_input", True),
                "capability_request_candidate": c.get(
                    "capability_request_candidate", False
                ),
            }
            for c in self.cards.values()
        ]

    def card(self, card_id):
        if card_id not in self.cards:
            raise LibraryError("card_not_found", str(card_id)[:100])
        if card_id in self.bans:
            raise LibraryError("card_banned", card_id)
        return dict(self.cards[card_id])

    def _curate(self, name, card_id, target, add):
        if card_id not in self.cards:
            raise LibraryError("card_not_found", str(card_id)[:100])
        if name == "pin" and card_id in self.bans:
            raise LibraryError("card_banned", card_id)
        self.writes.append((name, card_id))
        if add and card_id not in target:
            target.append(card_id)
        if not add and card_id in target:
            target.remove(card_id)
        if name == "ban" and card_id in self.pins:
            self.pins.remove(card_id)  # S2: a ban unpins
        return self._digest()

    def pin(self, card_id):
        return self._curate("pin", card_id, self.pins, True)

    def unpin(self, card_id):
        return self._curate("unpin", card_id, self.pins, False)

    def ban(self, card_id):
        return self._curate("ban", card_id, self.bans, True)

    def unban(self, card_id):
        return self._curate("unban", card_id, self.bans, False)

    def import_text(self, title, text):
        if text == self.refused_text:
            raise LibraryError("import_invalid", "not a text S2 queues")
        identity = "imp-" + str(len(self.imports) + 1)
        self.writes.append(("import", identity))
        self.imports.append({"import_id": identity, "title": title, "text": text})
        return identity

    def pending_imports(self):
        # S2's rows: the size as `chars`, never the text.
        return [
            {
                "import_id": item["import_id"],
                "title": item["title"],
                "chars": len(item["text"]),
                "text_digest": digest(item["text"].encode()),
            }
            for item in self.imports
        ]

    def snapshot(self):
        return digest(canonical(sorted(self.cards)))

    def save_plan(self, plan):
        if plan.get("created_by") not in ("planner", "miner"):
            raise LibraryError("plan_invalid", "created_by is planner or miner")
        if plan.get("parent") is not None and plan["parent"] not in self.saved:
            raise LibraryError("plan_not_found", plan["parent"])
        address = digest(canonical(plan))
        self.writes.append(("plan", address))
        self.saved[address] = json.loads(canonical(plan))
        return address

    def plan(self, address):
        if address not in self.saved:
            raise LibraryError("plan_not_found", str(address)[:100])
        return json.loads(json.dumps(self.saved[address]))

    def plans(self):
        # S2's index: oldest first, saved at a UTC timestamp.
        return [
            {
                "digest": address,
                "created_by": plan.get("created_by"),
                "parent": plan.get("parent"),
                "created_at": "2026-10-03T12:00:%02dZ" % index,
            }
            for index, (address, plan) in enumerate(self.saved.items())
        ]


PACK = SimpleNamespace(digest="sha256:" + "a" * 64, cards=(card("arxiv-2101.00001v1"),))


def fixture_challenge():
    from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE

    return {"id": FIXTURE_CHALLENGE["id"], "version": FIXTURE_CHALLENGE["version"]}


def plan_document(
    cites=("arxiv-2101.00001v1",), parent=None, created_by="planner", challenge=None
):
    """A plan in S3's stored shape (`plan.check_shape`)."""
    return {
        "schema": "carbon.graphite.miner-plan.v1",
        "challenge": challenge if challenge is not None else fixture_challenge(),
        "hypotheses": [
            {
                "rank": 1,
                "hypothesis": "neighbours interpolate",
                "expected_effect": "lower error",
                "stopping_rule": "stop after two practices",
                "cites": [{"card_id": c, "origin": "shared"} for c in cites],
            }
        ],
        "pins_considered": [],
        "parent": parent,
        "created_by": created_by,
    }


def ensure_graphite_agent(monkeypatch):
    """Until S3's `product_campaign.AGENTS` names graphite on this branch's
    base, admit it here; a no-op once it does (the integration merge)."""
    from carbon.development_session import product_campaign

    if "graphite" not in product_campaign.AGENTS:
        monkeypatch.setattr(
            product_campaign, "AGENTS", (*product_campaign.AGENTS, "graphite")
        )


def ready_for_graphite(host, monkeypatch, root, library=None):
    """DEVELOPMENT FIXTURE: a campaign host a Graphite launch can be admitted
    on - S2's library and pack and S3's plan rule as in-memory fakes, and
    graphite admitted as an agent - for tests of the launch path whose
    campaigns are Carbon's agent's, which for a new launch is Graphite."""
    ensure_graphite_agent(monkeypatch)
    library = library if library is not None else FakeLibrary([card("arxiv-1")])
    host.library_root = Path(root) / "graphite-library"
    host.open_library = lambda path: library
    host.shared_pack = lambda: PACK
    host.validate_plan = lambda plan, library_, curation: (True, None)
    return library


class Chain:
    """The stub chain's registration read, counted."""

    def __init__(self, registration):
        self.registration, self.reads = registration, 0

    def __call__(self, cfg):
        self.reads += 1
        return self.registration(cfg)


@pytest.fixture
def graphite(tmp_path, monkeypatch):
    """The journey host with a Graphite library and pack: what a launch
    carries out is recorded (`launched`), not run."""
    from carbon.development_session import research_campaign
    from scripts.dev.miner_launchpad.journey_fixture import (
        FIXTURE_CHALLENGE,
        journey_host,
    )

    root = tmp_path / "home"
    root.mkdir(mode=0o700)
    ensure_graphite_agent(monkeypatch)
    host = journey_host(root, patch=monkeypatch.setattr)
    chain = Chain(host.registration)
    host.registration = chain
    library = FakeLibrary([card("arxiv-2101.00001v1"), card("own-1", "miner_hunt")])
    host.library_root = root / "graphite-library"
    host.open_library = lambda path: library
    host.shared_pack = lambda: PACK
    validated = []

    def validate(plan, library_, curation):
        validated.append(curation["digest"])
        banned = {c["card_id"] for h in plan["hypotheses"] for c in h["cites"]} & set(
            curation["bans"]
        )
        return (False, {"code": "cites_banned_card"}) if banned else (True, None)

    host.validate_plan = validate
    launched = []
    prepare = research_campaign.prepare

    async def execute(args, *, ledger=None):
        # The fixture's preparation freezes the manifest; nothing is run.
        launched.append(args)
        (await prepare(args, ledger=ledger)).close()

    monkeypatch.setattr(research_campaign, "execute", execute)
    yield SimpleNamespace(
        host=host,
        chain=chain,
        library=library,
        launched=launched,
        validated=validated,
        challenge=FIXTURE_CHALLENGE,
        root=root,
    )
    host.close()


def join(host):
    for thread in list(host.threads.values()):
        thread.join(timeout=60)
        assert not thread.is_alive()


def launch_request(g, key=KEY, **fields):
    return {
        "agent": "graphite",
        "challenge": g.challenge["id"],
        "challenge_version": g.challenge["version"],
        "idempotency_key": key,
        **fields,
    }


def perform(g, name, request):
    from scripts.dev.miner_launchpad.operations import perform as run

    return run(g.host, name, request)


# --- the agent choice: Graphite replaces autonomous for new launches ---------


def test_options_offer_graphite_and_no_longer_the_autonomous_agent(graphite):
    options = perform(graphite, "options", {})
    values = [a["value"] for a in options["agents"]]
    assert values == ["none", "graphite"]
    assert "autonomous" not in values
    block = options["graphite"]
    assert [m["id"] for m in block["modes"]] == ["RESEARCH", "BUILD", "FULL"]
    assert [m["id"] for m in block["modes"] if m["default"]] == ["FULL"]
    assert block["research_share"]["default"] == 0.10
    assert block["limits"]["keys"] == [
        "calls_per_epoch",
        "trials_per_epoch",
        "planner_calls",
    ]
    estimate = block["hunt"]["estimate"]
    # The pinned default's price: a planning figure, never a cap.
    assert estimate["nanodollars_per_abstract"] == 1000 * 250 + 250 * 2000
    assert graphite.challenge in block["offered_for"]


@pytest.mark.parametrize("agent", ["autonomous", "carbon-autonomous"])
def test_a_new_autonomous_launch_is_refused_before_the_chain_is_read(graphite, agent):
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite, agent=agent))
    assert refused.value.code == "autonomous_agent_replaced"
    assert graphite.chain.reads == 0 and graphite.host.recent() == []


def test_a_new_autonomous_launch_is_refused_at_the_mcp_door(graphite):
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.mcp_operations import make_operation_tools

    tool = {t.name: t for t in make_operation_tools(graphite.host)}["carbon_launch"]
    body = launch_request(graphite, agent="autonomous")
    with pytest.raises(ToolError) as refused:
        asyncio.run(tool.fn(**body))
    text = str(refused.value)
    answer = json.loads(text[text.index("{") :])
    assert answer["error"] == "autonomous_agent_replaced"
    assert answer["field"] == "agent"
    assert "graphite" in answer["next_step"]


def recorded_autonomous_launch(g, key="recorded-autonomous-01", queued=True, **extra):
    """A launch recorded under `autonomous` before Graphite replaced it:
    its row exactly as `launch_admitted` wrote one then."""
    host = g.host
    cfg = host.configured()
    request = {
        "agent": "autonomous",
        "challenge": g.challenge["id"],
        "challenge_version": g.challenge["version"],
        "idempotency_key": key,
        **extra,
    }
    run_id, request_digest, config_pin = host._launch_identity(cfg, request)
    root = Path(cfg["campaigns_root"]) / run_id
    with host.db() as db:
        db.execute(
            "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget,research_guidance,launch_request) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                key,
                request_digest,
                cfg["profile_id"],
                cfg["principal"],
                config_pin,
                "cmp-" + run_id,
                "QUEUED" if queued else "COMPLETED",
                1.0,
                str(root),
                canonical({}),
                canonical({}),
                None,
                canonical({k: v for k, v in request.items() if k != "idempotency_key"}),
            ),
        )
    return run_id, request


def test_a_launch_recorded_under_autonomous_still_replays(graphite):
    """The refusal comes after the replay gate's lookup: a lost response of a
    launch recorded before Graphite replays it, reading no chain."""
    run_id, request = recorded_autonomous_launch(graphite)
    replayed = perform(graphite, "launch", request)
    assert replayed["id"] == run_id
    # Under setup's name for the same agent, too.
    assert (
        perform(graphite, "launch", {**request, "agent": "carbon-autonomous"})["id"]
        == run_id
    )
    assert graphite.chain.reads == 0
    # The browser's historical body names no agent: the same request.
    browser_id, browser = recorded_autonomous_launch(
        graphite, key="recorded-browser-0001", profile="journey-profile"
    )
    body = {k: v for k, v in browser.items() if k not in ("agent", "idempotency_key")}
    assert graphite.host.launch(body, browser["idempotency_key"])["id"] == browser_id
    assert graphite.chain.reads == 0 and graphite.launched == []


def test_a_queued_autonomous_launch_is_still_carried_out_as_recorded(graphite):
    run_id, _ = recorded_autonomous_launch(graphite)
    host = graphite.host
    row, _kind, _root = host._bound(run_id)
    product, choice = host._recorded_launch(dict(row), host.configured())
    assert product.agent == "autonomous" and choice is None


def test_no_path_past_the_gate_admits_an_autonomous_launch(graphite):
    """The body refuses it too: nothing that reaches `launch_admitted`
    records one, whatever called it."""
    host = graphite.host
    admitted = SimpleNamespace(profile=host.configured(), miner=None)
    with pytest.raises(Rejected) as refused:
        host.launch_admitted(admitted, launch_request(graphite, agent="autonomous"))
    assert refused.value.code == "autonomous_agent_replaced"
    assert host.recent() == []


def test_the_browser_launch_naming_no_agent_is_not_a_new_autonomous_launch(graphite):
    with pytest.raises(Rejected) as refused:
        graphite.host.launch(
            {
                "profile": "journey-profile",
                "challenge": graphite.challenge["id"],
                "challenge_version": graphite.challenge["version"],
            },
            "browser-key-000000001",
        )
    assert refused.value.code == "autonomous_agent_replaced"


# --- a Graphite launch ---------------------------------------------------------


def test_a_graphite_launch_freezes_its_choice_and_the_curation_digest(graphite):
    library = graphite.library
    library.pins.append("arxiv-2101.00001v1")
    curation = library.curation()["digest"]
    launched = perform(
        graphite,
        "launch",
        launch_request(
            graphite,
            graphite_mode="FULL",
            research_share=0.25,
            hunt={"queries": ["battery fast charge", "neural operator"]},
            limits={"calls_per_epoch": 200},
        ),
    )
    join(graphite.host)
    (args,) = graphite.launched
    assert args.product.agent == "graphite"
    # Exactly the names S3's `edition.launch_fields` reads; the captured
    # curation digest travels beside them.
    assert args.graphite == {
        "mode": "FULL",
        "research_share": 0.25,
        "plan": None,
        "hunt": {
            "queries": ["battery fast charge", "neural operator"],
            "max_records": 200,
        },
        "limits": {"calls_per_epoch": 200},
    }
    assert args.graphite_curation_digest == curation
    assert args.graphite_library == graphite.root / "graphite-library"
    # The record keeps what admission captured beside the request, never in it.
    row, _kind, _root = graphite.host._bound(launched["id"])
    stored = json.loads(row["launch_request"])
    assert stored["graphite_admission"] == {"curation_digest": curation}
    assert graphite.chain.reads == 1
    # The view names Graphite as setup does.
    assert graphite.host.get(launched["id"])["agent"] == "carbon-graphite"


def test_a_graphite_launch_replays_and_a_changed_one_conflicts(graphite):
    first = perform(
        graphite, "launch", launch_request(graphite, graphite_mode="RESEARCH")
    )
    join(graphite.host)
    again = perform(
        graphite, "launch", launch_request(graphite, graphite_mode="RESEARCH")
    )
    assert again["id"] == first["id"] and graphite.chain.reads == 1
    assert len(graphite.launched) == 1
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite, graphite_mode="BUILD"))
    assert refused.value.code == "research_launch_replay_conflict"


def test_the_curation_digest_is_the_one_captured_at_admission(graphite):
    """A launch carried out where it was not received (a supervisor, a
    restart) keeps the curation its miner launched with: a pin made since is
    not read into it, and its plan is not judged again."""
    host = graphite.host
    plan = graphite.library.save_plan(plan_document())
    launched = perform(
        graphite, "launch", launch_request(graphite, graphite_mode="BUILD", plan=plan)
    )
    join(host)
    captured = graphite.launched[0].graphite_curation_digest
    graphite.library.pins.append("own-1")
    graphite.library.bans.append("arxiv-2101.00001v1")
    row, _kind, _root = host._bound(launched["id"])
    validated = len(graphite.validated)
    _product, choice = host._recorded_launch(dict(row), host.configured())
    assert choice.graphite["curation_digest"] == captured
    assert choice.graphite["plan"] == plan
    assert len(graphite.validated) == validated
    # What the campaign receives is the captured digest, not the library's
    # current one (S3 freezes that curation: `library.curation_state`).
    args = SimpleNamespace()
    choice.apply(args)
    assert args.graphite_curation_digest == captured
    assert captured != graphite.library.curation()["digest"]
    assert args.graphite["plan"] == plan


def test_a_recorded_graphite_launch_without_its_admission_is_refused(graphite):
    host = graphite.host
    launched = perform(graphite, "launch", launch_request(graphite))
    join(host)
    with host.db() as db:
        stored = json.loads(
            db.execute(
                "SELECT launch_request FROM launchpad_campaigns WHERE id=?",
                (launched["id"],),
            ).fetchone()[0]
        )
        stored.pop("graphite_admission")
        db.execute(
            "UPDATE launchpad_campaigns SET launch_request=? WHERE id=?",
            (canonical(stored), launched["id"]),
        )
    row, _kind, _root = host._bound(launched["id"])
    with pytest.raises(Rejected) as refused:
        host._recorded_launch(dict(row), host.configured())
    assert refused.value.code == "launch_record_differs"


@pytest.mark.parametrize(
    "fields,code",
    [
        ({"graphite_mode": "EVERYTHING"}, "graphite_mode_invalid"),
        (
            {"graphite_mode": "BUILD", "research_share": 0.2},
            "graphite_field_not_used_by_mode",
        ),
        ({"research_share": 1.5}, "research_share_invalid"),
        ({"research_share": -0.1}, "research_share_invalid"),
        ({"research_share": True}, "research_share_invalid"),
        ({"research_share": float("nan")}, "research_share_invalid"),
        ({"plan": "sha256:" + "b" * 64}, "graphite_field_not_used_by_mode"),
        ({"graphite_mode": "BUILD", "plan": "../../etc"}, "plan_not_found"),
        ({"graphite_mode": "BUILD", "plan": "sha256:" + "B" * 64}, "plan_not_found"),
        ({"graphite_mode": "BUILD", "plan": "plan-00000001"}, "plan_not_found"),
        ({"graphite_mode": "BUILD", "plan": "sha256:" + "b" * 64}, "plan_not_found"),
        (
            {"graphite_mode": "BUILD", "plan": "sha256:" + "b" * 64, "hunt": {}},
            "graphite_field_not_used_by_mode",
        ),
        # S3 runs no hunt in BUILD, with or without a plan: refused before
        # the campaign exists, never by its preparation after.
        ({"graphite_mode": "BUILD", "hunt": {}}, "graphite_field_not_used_by_mode"),
        ({"hunt": {"queries": ["ti:battery AND au:x"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["a b c d e f g"]}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["battery"] * 9}}, "hunt_query_invalid"),
        ({"hunt": {"queries": []}}, "hunt_query_invalid"),
        ({"hunt": {"queries": ["battery  charge"]}}, "hunt_query_invalid"),
        ({"hunt": {"max_records": 0}}, "hunt_query_invalid"),
        ({"hunt": {"max_records": 10001}}, "hunt_query_invalid"),
        ({"hunt": {"pages": 3}}, "hunt_query_invalid"),
        ({"limits": {"calls_per_epoch": 0}}, "graphite_limits_invalid"),
        ({"limits": {"calls_per_epoch": True}}, "graphite_limits_invalid"),
        ({"limits": {"provider_nanodollars": 5}}, "graphite_limits_invalid"),
    ],
)
def test_a_graphite_choice_that_cannot_run_is_refused_before_the_chain(
    graphite, fields, code
):
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite, **fields))
    assert refused.value.code == code
    assert graphite.chain.reads == 0 and graphite.host.recent() == []


@pytest.mark.parametrize(
    "field", ["graphite_mode", "research_share", "plan", "hunt", "limits"]
)
def test_graphite_fields_need_the_graphite_agent(graphite, field):
    value = {
        "graphite_mode": "FULL",
        "research_share": 0.1,
        "plan": "sha256:" + "b" * 64,
        "hunt": {},
        "limits": {},
    }[field]
    with pytest.raises(Rejected) as refused:
        perform(
            graphite, "launch", launch_request(graphite, agent="none", **{field: value})
        )
    assert refused.value.code == "graphite_fields_need_the_graphite_agent"


def test_defaults_resolve_as_the_design_states():
    from scripts.dev.miner_launchpad.runner import GRAPHITE_LAUNCH_KEYS, graphite_launch

    assert graphite_launch({"agent": "none"}) is None
    full = graphite_launch({"agent": "graphite"})
    assert tuple(full) == GRAPHITE_LAUNCH_KEYS
    assert (full["mode"], full["research_share"], full["hunt"], full["limits"]) == (
        "FULL",
        0.10,
        None,
        {},
    )
    research = graphite_launch(
        {"agent": "graphite", "graphite_mode": "RESEARCH", "hunt": {}}
    )
    assert research["research_share"] is None
    assert research["hunt"] == {"queries": None, "max_records": 200}
    build = graphite_launch({"agent": "graphite", "graphite_mode": "BUILD"})
    assert build["plan"] is None and build["research_share"] is None
    # A field sent as null means what leaving it out means.
    nulls = dict.fromkeys(
        ("graphite_mode", "research_share", "plan", "hunt", "limits"), None
    )
    assert graphite_launch({"agent": "graphite", **nulls}) == full
    assert graphite_launch({"agent": "none", **nulls}) is None


#: S3's `edition.LAUNCH_FIELDS` on claude/gm-driver: the only names its
#: `launch_fields` accepts (any other is `graphite_launch_invalid`).
S3_LAUNCH_FIELDS = {"mode", "research_share", "plan", "hunt", "limits"}

APPLY_CASES = (
    {},
    {"graphite_mode": "FULL", "research_share": 0.25, "hunt": {}},
    {
        "graphite_mode": "RESEARCH",
        "hunt": {"queries": ["battery fast charge"], "max_records": 50},
        "limits": {"planner_calls": 40},
    },
    {
        "graphite_mode": "BUILD",
        "plan": "sha256:" + "b" * 64,
        "limits": {"calls_per_epoch": 200, "trials_per_epoch": 12},
    },
)


@pytest.mark.parametrize("fields", APPLY_CASES)
def test_args_graphite_carries_exactly_s3s_launch_field_names(fields):
    from scripts.dev.miner_launchpad.runner import LaunchChoice, graphite_launch

    choice = graphite_launch({"agent": "graphite", **fields})
    args = SimpleNamespace()
    LaunchChoice(graphite={**choice, "curation_digest": "sha256:" + "c" * 64}).apply(
        args
    )
    assert set(args.graphite) == S3_LAUNCH_FIELDS
    assert "edition" not in args.graphite and "curation_digest" not in args.graphite
    assert args.graphite_curation_digest == "sha256:" + "c" * 64


@pytest.mark.parametrize("fields", APPLY_CASES)
def test_s3s_launch_fields_accept_what_the_launchpad_sends(fields):
    """At integration: S3's own validator runs on exactly what
    `LaunchChoice.apply` produces, and keeps every choice."""
    edition = pytest.importorskip("carbon.agent_campaign.graphite.miner.edition")
    from scripts.dev.miner_launchpad.runner import LaunchChoice, graphite_launch

    choice = graphite_launch({"agent": "graphite", **fields})
    args = SimpleNamespace()
    LaunchChoice(graphite={**choice, "curation_digest": "sha256:" + "c" * 64}).apply(
        args
    )
    assert set(edition.LAUNCH_FIELDS) == S3_LAUNCH_FIELDS
    accepted = edition.launch_fields(args.graphite)
    assert accepted["mode"] == choice["mode"]
    assert accepted["plan"] == choice["plan"]
    assert accepted["limits"] == choice["limits"]
    if choice["hunt"] is None:
        assert accepted["hunt"] is None
    else:
        assert accepted["hunt"]["max_records"] == choice["hunt"]["max_records"]
        assert accepted["hunt"]["queries"] == (choice["hunt"]["queries"] or [])
    if choice["mode"] == "FULL":
        assert accepted["research_share"] == choice["research_share"]


def test_a_launch_sent_with_null_graphite_fields_is_the_launch_without_them(
    graphite,
):
    """The browser keeps nulls and MCP strips them: one launch, one identity,
    whichever door sent it; and null fields are absent for any agent."""
    first = perform(
        graphite, "launch", launch_request(graphite, graphite_mode="RESEARCH")
    )
    join(graphite.host)
    again = perform(
        graphite,
        "launch",
        launch_request(
            graphite,
            graphite_mode="RESEARCH",
            research_share=None,
            plan=None,
            hunt=None,
            limits=None,
        ),
    )
    assert again["id"] == first["id"] and graphite.chain.reads == 1
    row, _kind, _root = graphite.host._bound(first["id"])
    assert "plan" not in json.loads(row["launch_request"])
    manual = perform(
        graphite,
        "launch",
        launch_request(graphite, key="manual-launch-key-0001", agent="none", plan=None),
    )
    join(graphite.host)
    assert graphite.host.get(manual["id"])["agent"] == "manual"


def test_a_plan_for_another_challenge_is_refused_before_the_chain(graphite):
    """S3 builds only on a plan of the launch's own Challenge: refused here,
    before anything is created, not by its preparation after."""
    plan = graphite.library.save_plan(
        plan_document(challenge={"id": "another-challenge", "version": "1"})
    )
    with pytest.raises(Rejected) as refused:
        perform(
            graphite,
            "launch",
            launch_request(graphite, graphite_mode="BUILD", plan=plan),
        )
    assert refused.value.code == "plan_invalid"
    assert refused.value.next_step.endswith("Reason: plan_for_another_challenge.")
    assert graphite.chain.reads == 0 and graphite.host.recent() == []


def test_a_plan_the_rule_refuses_is_refused_with_its_reason(graphite):
    plan = graphite.library.save_plan(plan_document())
    graphite.library.bans.append("arxiv-2101.00001v1")
    with pytest.raises(Rejected) as refused:
        perform(
            graphite,
            "launch",
            launch_request(graphite, graphite_mode="BUILD", plan=plan),
        )
    assert refused.value.code == "plan_invalid"
    assert refused.value.next_step.endswith("Reason: cites_banned_card.")
    assert graphite.chain.reads == 0


def test_a_missing_card_pack_is_refused_by_name(graphite):
    def missing():
        raise FileNotFoundError("the pack")

    graphite.host.shared_pack = missing
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite))
    assert refused.value.code == "literature_pack_missing"
    assert graphite.chain.reads == 0


def test_graphite_only_runs_on_a_challenge_with_a_registered_campaign(
    graphite, monkeypatch
):
    from carbon.challenge_registry import campaigns

    def no_campaign(challenge):
        raise campaigns.NoCampaignComposition("no research campaign composition")

    monkeypatch.setattr(campaigns, "campaign_for", no_campaign)
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite))
    assert refused.value.code == "graphite_not_offered_for_challenge"
    # The miner's own selection is unaffected: agent=none needs no campaign
    # check here (its preparation reads its campaign itself).
    assert graphite.chain.reads == 0


def test_a_launch_with_no_library_is_refused_by_name(graphite):
    graphite.host.library_root = None
    with pytest.raises(Rejected) as refused:
        perform(graphite, "launch", launch_request(graphite))
    assert refused.value.code == "library_unavailable"


def test_a_graphite_launch_may_name_a_model_as_the_autonomous_one_could(graphite):
    """A model is for an agent that calls one: graphite takes model fields;
    agent=none is still refused them, under the code's historical name."""
    from scripts.dev.miner_launchpad.runner import MODEL_AGENTS, RunnerAdapter

    assert "graphite" in MODEL_AGENTS
    cfg = graphite.host.configured()
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._launch_choice(
            cfg, {"agent": "none", "model_provider": "engy-anthropic"}, None
        )
    assert refused.value.code == "model_selection_needs_the_autonomous_agent"


def test_a_non_graphite_launch_keeps_its_historical_identity_and_args(graphite):
    """Default-off: a launch that is not Graphite's has the identity it had,
    and its args carry nothing of Graphite's."""
    host = graphite.host
    cfg = host.configured()
    request = {"agent": "none", "idempotency_key": KEY, "profile": "p"}
    _, historical, _ = host._launch_identity(cfg, request)
    assert historical == digest(canonical({"profile": "p", "agent": "none"}))
    launched = perform(graphite, "launch", launch_request(graphite, agent="none"))
    join(host)
    (args,) = graphite.launched
    assert not hasattr(args, "graphite") and not hasattr(args, "graphite_library")
    row, _kind, _root = host._bound(launched["id"])
    assert "graphite_admission" not in json.loads(row["launch_request"])


def test_only_a_graphite_campaign_is_given_the_library(graphite, tmp_path):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host = graphite.host
    for agent, expected in (("graphite", host.library_root), ("none", None)):
        args = SimpleNamespace()
        RunnerAdapter._graphite_args(host, args, tmp_path, SimpleNamespace(agent=agent))
        assert getattr(args, "graphite_library", None) == expected
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "campaign-manifest.json").write_bytes(canonical({"agent": "graphite"}))
    args = SimpleNamespace()
    host._graphite_args(args, frozen)
    assert args.graphite_library == host.library_root


def test_graphite_selects_in_its_campaign_and_pauses_for_a_handover(tmp_path):
    """A Graphite campaign is an agent campaign: freeze and submit are its
    agent's, and a detached supervisor pauses it for a Control Center."""
    from scripts.dev.miner_launchpad.runner import RunnerAdapter, product_agent

    root = tmp_path / "c"
    root.mkdir()
    (root / "campaign-manifest.json").write_bytes(canonical({"agent": "graphite"}))
    assert product_agent(root) == "graphite"
    admitted = SimpleNamespace(campaign={"root": str(root)})
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._require_frozen(admitted)
    assert refused.value.code == "the_agent_selects_in_this_campaign"


# --- setup and the capability document ---------------------------------------


def test_setup_offers_graphite_and_refuses_the_autonomous_agent(tmp_path):
    from scripts.dev.miner_launchpad import environment_setup as setup
    from scripts.dev.miner_launchpad.setup_operations import NEXT_STEPS

    offered = [choice["id"] for choice in setup.choices()["agent"]]
    assert offered == ["carbon-graphite", "own-agent", "hermes"]
    assert setup.GRAPHITE in setup.USES_SETUP_MODEL
    # A setup that recorded the autonomous agent still needs its model.
    assert setup.AUTONOMOUS in setup.USES_SETUP_MODEL
    assert setup._needs_inference({"agent": {"choice": setup.AUTONOMOUS}})
    instance = setup.EnvironmentSetup.__new__(setup.EnvironmentSetup)
    with pytest.raises(setup.SetupRefused) as refused:
        instance.agent({"choice": "carbon-autonomous"})
    assert (refused.value.field, refused.value.code) == (
        "choice",
        "autonomous_agent_replaced",
    )
    assert "carbon-graphite" in NEXT_STEPS["autonomous_agent_replaced"]
    with pytest.raises(setup.SetupRefused) as refused:
        instance.agent({"choice": "carbon-anything"})
    assert refused.value.code == "agent_not_offered"


def test_the_capability_document_offers_graphite_named_as_setup_names_it(graphite):
    from scripts.dev.miner_launchpad import capabilities, environment_setup

    document = capabilities.control_center(graphite.host)
    choices = {c["id"]: c for c in document["agents"]["choices"]}
    assert set(choices) == {"graphite", "manual", "external_mcp"}
    named = {c["id"]: c["display_name"] for c in environment_setup.choices()["agent"]}
    assert choices["graphite"]["label"] == named[environment_setup.GRAPHITE]
    assert choices["graphite"]["launch_agent"] == "graphite"
    assert [m["id"] for m in choices["graphite"]["modes"]] == [
        "RESEARCH",
        "BUILD",
        "FULL",
    ]
    assert document["model"]["used_by"] == ["graphite"]
    assert {"graphite_mode", "research_share", "plan", "hunt", "limits"} <= set(
        document["launch"]["browser_sends"]
    )
    assert document["graphite"]["library"]["writes"][0] == "library_pin"
    for challenge in document["challenges"]:
        assert type(challenge["setup_offers"]["graphite"]) is bool


def test_without_a_profile_graphite_is_shown_unavailable_with_why():
    from scripts.dev.miner_launchpad import capabilities

    document = capabilities.control_center(None)
    assert document["graphite"]["availability"] == "unavailable"
    graphite = next(c for c in document["agents"]["choices"] if c["id"] == "graphite")
    assert graphite["availability"] == "unavailable"


# --- the refusal catalog -----------------------------------------------------

#: Every new code the design names (OWNER-GRAPHITE-MINER-01).
DESIGN_CODES = (
    "autonomous_agent_replaced",
    "graphite_edition_unknown",
    "graphite_not_offered_for_challenge",
    "research_share_reached",
    "plan_not_found",
    "plan_invalid",
    "literature_pack_missing",
    "literature_fetch_failed",
    "card_not_found",
    "card_banned",
    "import_invalid",
    "hunt_query_invalid",
)


def test_every_new_code_has_its_own_next_step():
    from scripts.dev.miner_launchpad.operations import REFUSAL_FIELDS
    from scripts.dev.miner_launchpad.supervisor import (
        FALLBACK_ACTION,
        NEXT_ACTIONS,
        next_action,
    )

    # And the codes S3's preparation and the engine's ceiling may end a
    # Graphite campaign with.
    campaign_codes = (
        "graphite_launch_invalid",
        "curation_not_found",
        "miner_ceiling_reached",
    )
    for code in (*DESIGN_CODES, *REFUSAL_FIELDS, *campaign_codes):
        assert next_action(code) != FALLBACK_ACTION, code
    # None of the steps reads as if the autonomous agent were still offered.
    assert "agent=autonomous" not in json.dumps(NEXT_ACTIONS)
    assert "carbon-autonomous" not in NEXT_ACTIONS["invalid_agent"]


def test_a_last_refusal_with_a_new_code_carries_its_step():
    from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS, refusal

    for code in DESIGN_CODES:
        entry = refusal(code, operation="run")
        assert entry["code"] == code
        assert entry["next_action"] == NEXT_ACTIONS[code]


# --- the projection and the campaign view ------------------------------------


def ledger_status(*identities, charge=1000):
    return {
        "operations": [
            {
                "id": identity,
                "phase": "provider",
                "state": "SETTLED",
                "reservation": {
                    "provider_nanodollars": 5 * charge,
                    "provider_attempts": 1,
                },
                "actual": {"provider_nanodollars": charge, "provider_attempts": 1},
                "result": None,
            }
            for identity in identities
        ]
    }


GRAPHITE_MANIFEST = {
    "agent": "graphite",
    "provider": {
        "agent": "graphite",
        "graphite": {
            "edition": "carbon.graphite.miner-edition.v1",
            "mode": "FULL",
            "research_share": 0.1,
            "plan_digest": None,
            "hunt": {"queries": [], "max_records": 200},
            "limits": {},
        },
    },
}

PLANNED = "sha256:" + "e" * 64


def s3_view(**changes):
    """DEVELOPMENT FIXTURE: S3's `driver.view` answer, in its shape (the
    driver on claude/gm-driver), mid-way through a FULL campaign's plan."""
    return {
        "schema": "carbon.graphite.miner-campaign-view.v1",
        "edition": "carbon.graphite.miner-edition.v1",
        "mode": "FULL",
        "stage": "plan",
        "stages": [
            {"stage": "hunt", "state": "DONE", "code": None},
            {"stage": "plan", "state": "RUNNING", "code": None},
            {"stage": "build", "state": "PENDING", "code": None},
        ],
        "plan_digest": None,
        "research_share": 0.1,
        "research_spent": {"provider_nanodollars": 4000, "provider_attempts": 4},
        "research_cap": {"provider_nanodollars": 100000, "provider_attempts": 8},
        "hunt": {"extracted": 1, "deduped": 1, "cost_nanodollars": 2000},
        **changes,
    }


def write_hunt_stage(root, report):
    """The hunt's stage record as S3 writes it, with S2's report counts."""
    stages = root / "graphite" / "stages"
    stages.mkdir(parents=True, exist_ok=True)
    (stages / "hunt.json").write_text(
        json.dumps(
            {
                "schema": "carbon.graphite.miner-stage.v1",
                "stage": "hunt",
                "status": "DONE",
                "code": None,
                "share": None,
                "report": report,
                "private_snapshot_digest": "sha256:" + "f" * 64,
            }
        )
    )


HUNT_REPORT = {
    "fetched": 2,
    "deduped": 1,
    "triaged_out": 0,
    "extracted": 1,
    "failed_infra": False,
    "cards": ["own-1"],
}


def test_graphite_progress_is_s3s_view_of_its_own_records(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad import projection

    seen = []

    def view(root, operations):
        seen.append((root, operations))
        return s3_view()

    monkeypatch.setattr(projection, "_graphite_view", view)
    status = ledger_status(
        "graphite-reader-" + "1" * 40,
        "graphite-reader-" + "2" * 40,
        "research-epoch-1-plan",
        "epoch-1-plan-provider-000",
        "worker-practice-000",
    )
    write_hunt_stage(tmp_path, HUNT_REPORT)
    value = projection.graphite_progress(GRAPHITE_MANIFEST, status, tmp_path)
    assert seen == [(tmp_path, status["operations"])]
    assert value["mode"] == "FULL" and value["stage"] == "plan"
    assert [row["stage"] for row in value["stages"]] == ["hunt", "plan", "build"]
    assert value["research_share"] == 0.1
    # The research spend and cap are the driver's (its Reader's and its
    # Planner's calls), never recounted here under other names.
    assert value["research_spent"] == {
        "provider_nanodollars": 4000,
        "provider_attempts": 4,
    }
    assert value["research_cap"] == {
        "provider_nanodollars": 100000,
        "provider_attempts": 8,
    }
    # The hunt: its report's counts from S3's stage record, and its Reader
    # calls (`graphite-reader-*`) and their cost from the ledger.
    assert value["hunt"] == {
        "fetched": 2,
        "deduped": 1,
        "triaged_out": 0,
        "extracted": 1,
        "failed_infra": 0,
        "reader_calls": 2,
        "cost_nanodollars": 2000,
    }


def test_a_finished_research_campaign_shows_the_plan_its_planner_wrote(
    tmp_path, monkeypatch
):
    from scripts.dev.miner_launchpad import projection

    monkeypatch.setattr(
        projection,
        "_graphite_view",
        lambda root, operations: s3_view(
            mode="RESEARCH", stage="complete", plan_digest=PLANNED, research_cap=None
        ),
    )
    manifest = json.loads(json.dumps(GRAPHITE_MANIFEST))
    manifest["provider"]["graphite"]["mode"] = "RESEARCH"
    value = projection.graphite_progress(manifest, ledger_status(), tmp_path)
    assert value["plan_digest"] == PLANNED and value["stage"] == "complete"
    # RESEARCH applies no share; the block's recorded default is not shown.
    assert value["research_share"] is None and value["research_cap"] is None


def test_during_a_hunt_its_calls_show_before_its_report(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad import projection

    monkeypatch.setattr(
        projection,
        "_graphite_view",
        lambda root, operations: s3_view(stage="hunt", hunt=None),
    )
    value = projection.graphite_progress(
        GRAPHITE_MANIFEST, ledger_status("graphite-reader-" + "3" * 40), tmp_path
    )
    assert value["stage"] == "hunt"
    assert value["hunt"]["reader_calls"] == 1
    assert value["hunt"]["cost_nanodollars"] == 1000
    assert value["hunt"]["extracted"] is None  # no report until it finished


def test_without_the_drivers_view_only_the_frozen_block_is_shown(
    tmp_path, monkeypatch
):
    """S3's view absent or failing: nothing is invented. The mode and the
    frozen plan digest show; the stage and the research spend are unknown."""
    from scripts.dev.miner_launchpad import projection

    def broken(root, operations):
        raise ValueError("an unreadable stage record")

    monkeypatch.setattr(projection, "_graphite_view", broken)
    manifest = json.loads(json.dumps(GRAPHITE_MANIFEST))
    manifest["provider"]["graphite"].update(mode="BUILD", plan_digest=PLANNED)
    value = projection.graphite_progress(manifest, ledger_status(), tmp_path)
    assert value["mode"] == "BUILD" and value["plan_digest"] == PLANNED
    assert value["stage"] is None and value["stages"] == []
    assert value["research_spent"] == {
        "provider_nanodollars": None,
        "provider_attempts": None,
    }


def test_a_campaign_without_a_hunt_shows_none(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad import projection

    monkeypatch.setattr(
        projection, "_graphite_view", lambda root, operations: s3_view(stage=None)
    )
    manifest = json.loads(json.dumps(GRAPHITE_MANIFEST))
    manifest["provider"]["graphite"]["hunt"] = None
    value = projection.graphite_progress(manifest, ledger_status(), tmp_path)
    assert value["hunt"] is None and value["stage"] is None


def test_the_projection_reads_s3s_real_view(tmp_path):
    """At integration: the projection over S3's own `driver.view` of a FULL
    campaign whose hunt finished and whose Planner is running."""
    driver = pytest.importorskip("carbon.agent_campaign.graphite.miner.driver")
    budget = pytest.importorskip("carbon.agent_campaign.graphite.miner.budget")
    from scripts.dev.miner_launchpad.projection import READER_PREFIX, graphite_progress

    assert READER_PREFIX == budget.READER_PREFIX
    edition = pytest.importorskip("carbon.agent_campaign.graphite.miner.edition")
    block = edition.graphite_block(
        edition.launch_fields({"mode": "FULL", "hunt": {}}),
        curation_digest="sha256:" + "c" * 64,
        pack_digest="sha256:" + "a" * 64,
        private_snapshot_digest=None,
    )
    manifest = {
        "agent": "graphite",
        "owner": "alice",
        "ceilings": {"provider_nanodollars": 100000, "provider_attempts": 80},
        "provider": {"agent": "graphite", "graphite": block},
    }
    (tmp_path / "campaign-manifest.json").write_text(json.dumps(manifest))
    write_hunt_stage(tmp_path, HUNT_REPORT)
    stages = driver.Stages(tmp_path)
    stages.start("hunt")
    stages.start("plan")
    status = ledger_status(
        budget.READER_PREFIX + "1" * 40,
        budget.PLAN_PREFIX + "provider-000",
        "epoch-1-provider-000",
    )
    value = graphite_progress(manifest, status, tmp_path)
    assert value["stage"] == "plan"
    assert value["research_spent"] == {
        "provider_nanodollars": 2000,
        "provider_attempts": 2,
    }
    assert value["research_cap"] == {
        "provider_nanodollars": 10000,
        "provider_attempts": 8,
    }
    assert value["hunt"]["reader_calls"] == 1
    assert value["hunt"]["extracted"] == 1


def test_the_view_copies_graphite_by_name_and_only_for_graphite():
    from scripts.dev.miner_launchpad.campaign_view import graphite_section, stages

    own = {
        "state": "RUNNING",
        "graphite": {
            "edition": "carbon.graphite.miner-edition.v1",
            "mode": "RESEARCH",
            "stage": "plan",
            "stages": [
                {"stage": "hunt", "state": "STOPPED", "code": "research_share_reached"},
                {"stage": "plan", "state": "RUNNING", "code": "<b>", "x": 1},
                {"stage": "<script>", "state": "DONE"},
            ],
            "plan_digest": None,
            "research_share": None,
            "research_spent": {"provider_nanodollars": 7, "provider_attempts": 1},
            "research_cap": {"provider_nanodollars": 70, "secret": 1},
            "hunt": {
                "fetched": 2,
                "extracted": 1,
                "failed_infra": True,
                "cost_nanodollars": 3,
                "secret": 1,
            },
            "private_path": "PRIVATE-PATH-SENTINEL",
        },
    }
    section = graphite_section(own)
    assert section["stage"] == "plan" and section["mode"] == "RESEARCH"
    assert "PRIVATE-PATH-SENTINEL" not in json.dumps(section)
    assert "secret" not in section["hunt"] and "secret" not in section["research_cap"]
    assert section["hunt"]["deduped"] is None
    assert section["hunt"]["failed_infra"] == 1  # a count, as the page reads it
    assert section["stages"] == [
        {"stage": "hunt", "state": "STOPPED", "code": "research_share_reached"},
        {"stage": "plan", "state": "RUNNING", "code": None},
    ]
    assert section["research_cap"] == {
        "provider_nanodollars": 70,
        "provider_attempts": None,
    }
    research = next(s for s in stages(own) if s["id"] == "research")
    assert research["detail"].endswith("Graphite RESEARCH: plan")
    assert graphite_section({"state": "RUNNING"}) is None
    hostile = {**own, "graphite": {**own["graphite"], "stage": "<script>"}}
    assert graphite_section(hostile)["stage"] is None


def test_observe_shows_a_graphite_campaign_and_ignores_stage_folders(graphite):
    """A Graphite campaign's projection has its graphite progress; a staged
    epoch's folder (`epoch-N/<stage>/`) is never read as the epoch's own
    outcome or candidate."""
    host = graphite.host
    launched = perform(
        graphite, "launch", launch_request(graphite, graphite_mode="RESEARCH")
    )
    join(host)
    _row, _kind, root = host._bound(launched["id"])
    stage = root / "epoch-1" / "planner"
    stage.mkdir(parents=True)
    (stage / "outcome.json").write_text(
        json.dumps(
            {
                "schema": "carbon.autoresearch.epoch-outcome.v1",
                "epoch": 1,
                "status": "PLANNED",
            }
        )
    )
    (stage / "selected-recipe.json").write_text("{}")
    value = host.get(launched["id"])
    assert value["agent"] == "carbon-graphite"
    assert set(value["graphite"]) >= {
        "mode",
        "stage",
        "plan_digest",
        "research_spent",
        "hunt",
    }
    assert value["epoch_outcomes"] == [] and value["candidate_freezes"] == []
    assert value["journey"]["frozen_awaiting_submission"] is False
