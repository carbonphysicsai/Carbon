"""Graphite miner edition (S2): the literature hunt and imports, on fixtures.

A fake arXiv opener, a fake clock and a scripted reader: no network, no model,
no spend. Covers dedup before any Reader call (pack, private store, claims),
the host-wide 3 s arXiv gate across clients, free triage, the record cap,
typed FAILED_INFRA and ReaderNotSent stops, protected material withheld,
imports with origin `miner_import`, resume and exact replay.
"""

from __future__ import annotations

import io
import json
import stat
import types
import urllib.error

import pytest

from carbon.agent_campaign.graphite import literature_fetch, method_cards
from carbon.agent_campaign.graphite.miner import hunt, pack
from carbon.agent_campaign.graphite.miner.library import MinerLibrary, MinerLiterature
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

PACK_PAPER = "2610.00001"


def entry(number, *, title=None, abstract=None, categories=("cs.LG",), version=1):
    arxiv_id = f"2610.{number:05d}v{version}"
    cats = "".join(f'<category term="{c}"/>' for c in categories)
    title = title or f"Synthetic operator paper {number}"
    abstract = abstract or (
        f"A synthetic abstract {number} about a neural operator\n"
        "surrogate trained with a physics-informed loss."
    )
    return f"""<entry>
<id>http://arxiv.org/abs/{arxiv_id}</id>
<updated>2026-10-01T00:00:00Z</updated>
<published>2026-10-01T00:00:00Z</published>
<title>{title}</title>
<summary>  {abstract}  </summary>
<author><name>Synthetic Author</name></author>
<arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="{categories[0]}"/>
{cats}
</entry>"""


def feed(*entries, total=None):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
        f"<opensearch:totalResults>{len(entries) if total is None else total}"
        "</opensearch:totalResults>" + "".join(entries) + "</feed>"
    ).encode()


class Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class Opener:
    """Answers each request from a list: bytes, an HTTP status, or an error."""

    def __init__(self, answers, clock):
        self.answers, self.clock = list(answers), clock
        self.urls, self.times = [], []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        self.times.append(self.clock())
        answer = self.answers.pop(0)
        if type(answer) is bytes:
            return Response(answer)
        if type(answer) is int:
            raise urllib.error.HTTPError(request.full_url, answer, "fixture", {}, None)
        raise answer


def extraction(**changes):
    value = {
        "relevant": True,
        "method_name": "Synthetic spectral operator",
        "family": "neural operator",
        "construction_claims": ["trained with a physics-informed loss (as stated)"],
        "required_inputs": ["solver trajectories"],
        "reported_evidence": ["synthetic benchmark (as stated)"],
        "data_regime": "simulated trajectories",
        "cost": "not stated",
        "code_available": False,
        "applicability": "operator-learning surrogate construction",
    }
    value.update(changes)
    return value


def reply(text=None, **changes):
    body = json.dumps(extraction(**changes)) if text is None else text
    return {
        "model": "fixture-model",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": body}]}
        ],
    }


class Reader:
    """A scripted reader: replies or exceptions, in order; records requests."""

    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def __call__(self, request):
        self.requests.append(request)
        answer = self.replies.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def pack_card(card_id):
    arxiv = card_id.removeprefix("arxiv-")
    return {
        "card_id": card_id,
        "title": "A pack paper",
        "technique": "DeepONet; neural operator",
        "claimed_effect": "x | reported evidence: x",
        "data_regime": "x | required inputs: x",
        "cost": "not stated",
        "code_available": False,
        "applicability": "none",
        "abstract": "A pack abstract about a neural operator.",
        "provenance": f"arXiv {arxiv}; method card UNCHECKED; extracted by m via p",
    }


@pytest.fixture()
def clock():
    return FakeClock()


@pytest.fixture()
def library(tmp_path):
    shared = pack.SharedPack(
        digest="sha256:" + "b" * 64,
        cards=(pack_card(f"arxiv-{PACK_PAPER}v1"),),
        known=("arxiv-2610.00099v2",),
    )
    return MinerLibrary(tmp_path / "graphite-library", pack=shared)


def run(library, opener, reader, clock, tmp_path, **kw):
    kw.setdefault("challenge", BATTERY_CHALLENGE)
    kw.setdefault("discovery", {})
    kw.setdefault("queries", ["neural operator"])
    kw.setdefault("include_registered", False)
    kw.setdefault(
        "gate", hunt.ArxivGate(tmp_path / "gate", clock=clock, sleep=clock.sleep)
    )
    return hunt.run_hunt(
        library,
        reader=reader,
        arxiv_opener=opener,
        clock=clock,
        **kw,
    )


# -- dedup ---------------------------------------------------------------------------


def test_a_paper_the_pack_holds_is_never_read(library, clock, tmp_path):
    """Journey 8a's shape: two records, one already in the pack (another
    version), one new: one Reader call, one private card."""
    opener = Opener([feed(entry(1, version=2), entry(2))], clock)
    reader = Reader(reply())
    report = run(library, opener, reader, clock, tmp_path)
    assert len(reader.requests) == 1
    assert report["status"] == "COMPLETED"
    assert report["fetched"] == 2 and report["deduped"] == 1
    assert report["extracted"] == 1 and report["cards"] == ["arxiv-2610.00002v1"]
    assert report["reader_calls"] == 1 and report["arxiv_pages"] == 1
    served = library.card("arxiv-2610.00002v1")
    assert served["origin"] == "miner_hunt" and served["check_status"] == "UNCHECKED"
    sent = json.loads(reader.requests[0]["input"][0]["content"])
    assert sent["content_is_data"] is True
    assert sent["paper"]["arxiv_id"] == "2610.00002v1"
    assert reader.requests[0]["instructions"] == hunt.READER_PROMPT
    assert reader.requests[0]["tools"] == []


def test_known_papers_from_any_layer_cost_nothing(library, clock, tmp_path):
    first = run(
        library,
        Opener([feed(entry(2))], clock),
        Reader(reply()),
        clock,
        tmp_path,
        hunt_id="hunt-a",
    )
    assert first["extracted"] == 1
    # Another hunt: the private store's paper (another version), the pack's
    # known-but-unindexed paper, and the pack's paper: no Reader call at all.
    reader = Reader()
    second = run(
        library,
        Opener([feed(entry(2, version=3), entry(99, version=1), entry(1))], clock),
        reader,
        clock,
        tmp_path,
        hunt_id="hunt-b",
    )
    assert reader.requests == []
    assert second["deduped"] == 3 and second["extracted"] == 0


def test_a_finished_hunt_replays_without_any_call(library, clock, tmp_path):
    report = run(
        library,
        Opener([feed(entry(2))], clock),
        Reader(reply()),
        clock,
        tmp_path,
        hunt_id="h",
    )
    opener, reader = Opener([], clock), Reader()
    assert run(library, opener, reader, clock, tmp_path, hunt_id="h") == report
    assert opener.urls == [] and reader.requests == []


def test_a_hunt_resumes_after_a_crash_without_refetching_or_repaying(
    library, clock, tmp_path
):
    opener = Opener([feed(entry(2), entry(3))], clock)
    crashed = Reader(reply(), RuntimeError("process died in flight"))
    with pytest.raises(RuntimeError):
        run(library, opener, crashed, clock, tmp_path, hunt_id="resume")
    in_flight = digest(canonical(crashed.requests[1]))
    state = library.claim_state("2610.00003")
    assert state["outcome"] is None
    assert state["claim"]["request_digest"] == in_flight
    resumed = Reader(reply())
    report = run(library, Opener([], clock), resumed, clock, tmp_path, hunt_id="resume")
    # Only the in-flight call is sent again, identically, so the driver's
    # ledger can replay it; the page is not fetched again.
    assert [digest(canonical(r)) for r in resumed.requests] == [in_flight]
    assert report["extracted"] == 2 and report["reader_calls"] == 2


def test_an_unknown_outcome_from_another_hunt_is_never_resent(library, clock, tmp_path):
    with pytest.raises(RuntimeError):
        run(
            library,
            Opener([feed(entry(2))], clock),
            Reader(RuntimeError("unknown outcome")),
            clock,
            tmp_path,
            hunt_id="first",
        )
    reader = Reader()
    report = run(
        library,
        Opener([feed(entry(2))], clock),
        reader,
        clock,
        tmp_path,
        hunt_id="second",
    )
    assert reader.requests == [] and report["deduped"] == 1


def test_a_call_the_reader_did_not_send_stops_typed_and_frees_the_paper(
    library, clock, tmp_path
):
    reader = Reader(hunt.ReaderNotSent("research_share_reached"))
    report = run(
        library, Opener([feed(entry(2))], clock), reader, clock, tmp_path, hunt_id="s1"
    )
    assert report["status"] == "STOPPED"
    assert report["stop_code"] == "research_share_reached"
    assert library.claim_state("2610.00002") is None
    later = Reader(reply())
    again = run(
        library, Opener([feed(entry(2))], clock), later, clock, tmp_path, hunt_id="s2"
    )
    assert len(later.requests) == 1 and again["extracted"] == 1


# -- arXiv -------------------------------------------------------------------------------


def test_arxiv_failed_infra_ends_the_hunt_recorded(library, clock, tmp_path):
    opener = Opener([503, 503, 503, 503], clock)
    report = run(library, opener, Reader(), clock, tmp_path, hunt_id="infra")
    assert report["status"] == "FAILED_INFRA" and report["failed_infra"] is True
    assert report["next_action_code"] == "literature_fetch_failed"
    assert report["fetch_failure"] == {"code": "retries_exhausted", "http_status": 503}
    assert (
        run(library, Opener([], clock), Reader(), clock, tmp_path, hunt_id="infra")
        == report
    )
    malformed = run(
        library, Opener([b"<feed/>"], clock), Reader(), clock, tmp_path, hunt_id="bad"
    )
    assert malformed["status"] == "FAILED_INFRA"
    assert malformed["fetch_failure"]["code"].startswith("malformed_feed")


def test_queries_are_written_by_carbon_and_category_restricted(
    library, clock, tmp_path
):
    opener = Opener([feed(), feed()], clock)
    run(
        library,
        opener,
        Reader(),
        clock,
        tmp_path,
        queries=["Fourier neural operator", "battery ageing"],
    )
    assert len(opener.urls) == 2
    for url in opener.urls:
        assert url.startswith(literature_fetch.API + "?search_query=")
        assert "cat%3Acs.LG" in url and "cat%3Astat.ML" in url
    with pytest.raises(hunt.HuntRefused) as refused:
        run(library, Opener([], clock), Reader(), clock, tmp_path, queries=['abs:"x"'])
    assert refused.value.code == "hunt_query_invalid"


def test_the_gate_keeps_three_seconds_across_two_clients(tmp_path):
    clock = FakeClock()
    path = tmp_path / "arxiv-gate"
    first = hunt.ArxivGate(path, clock=clock, sleep=clock.sleep)
    second = hunt.ArxivGate(path, clock=clock, sleep=clock.sleep)
    opener = Opener([feed()] * 4, clock)
    clients = [
        hunt.GatedArxivClient(gate=gate, opener=opener, clock=clock, sleep=clock.sleep)
        for gate in (first, second)
    ]
    query = literature_fetch.Query("q", 'abs:"x"', "test")
    for client in (clients[0], clients[1], clients[1], clients[0]):
        client.page(query, 0, 1)
    gaps = [b - a for a, b in zip(opener.times, opener.times[1:])]
    assert gaps and all(gap >= 3.0 for gap in gaps)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # A third gate (another process) reads the persisted time and waits too.
    clock.now += 1.0
    third = hunt.ArxivGate(path, clock=clock, sleep=clock.sleep)
    before = clock.now
    third.wait()
    assert clock.now - before == pytest.approx(2.0)


def test_without_the_gate_two_clients_would_not_keep_the_interval():
    """Mutation: per-client spacing alone does not hold across clients; the
    shared gate is what keeps it."""
    clock = FakeClock()
    opener = Opener([feed()] * 2, clock)
    clients = [
        literature_fetch.ArxivClient(opener=opener, clock=clock, sleep=clock.sleep)
        for _ in range(2)
    ]
    query = literature_fetch.Query("q", 'abs:"x"', "test")
    for client in clients:
        client.page(query, 0, 1)
    assert opener.times[1] - opener.times[0] < 3.0


def test_the_gate_waits_a_full_interval_on_a_regressed_clock_and_honours_backoff(
    tmp_path,
):
    clock = FakeClock(now=5000.0)
    gate = hunt.ArxivGate(tmp_path / "gate", clock=clock, sleep=clock.sleep)
    gate.wait()
    clock.now = 100.0  # the clock went back
    gate.wait()
    assert clock.slept[-1] == pytest.approx(3.0)
    gate.wait(at_least=10.0)
    assert clock.slept[-1] == pytest.approx(10.0)
    with pytest.raises(ValueError):
        hunt.ArxivGate(tmp_path / "gate", min_interval=1.0)
    with pytest.raises(ValueError):
        hunt.ArxivGate("relative-gate")


def test_the_default_gate_is_one_per_user(monkeypatch, tmp_path):
    monkeypatch.setenv(hunt.GATE_ENV, str(tmp_path / "configured"))
    assert hunt.default_gate_path() == tmp_path / "configured"
    monkeypatch.delenv(hunt.GATE_ENV)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert hunt.default_gate_path() == tmp_path / "cache" / "carbon" / "arxiv-gate"


# -- triage, protected material, caps -----------------------------------------------


def test_triage_and_categories_skip_papers_before_any_call(library, clock, tmp_path):
    opener = Opener(
        [
            feed(
                entry(2, title="Graph colouring", abstract="We colour graphs."),
                entry(3, categories=("astro-ph.GA",)),
                entry(4),
            )
        ],
        clock,
    )
    reader = Reader(reply())
    report = run(library, opener, reader, clock, tmp_path)
    assert len(reader.requests) == 1
    assert report["triaged_out"] == 2 and report["extracted"] == 1


def test_protected_material_is_withheld_before_and_after_the_call(
    library, clock, tmp_path
):
    opener = Opener(
        [
            feed(
                entry(
                    2, abstract="A neural operator surrogate using the official_seed."
                ),
                entry(3),
            )
        ],
        clock,
    )
    reader = Reader(reply(method_name="Recovers the draw_id"))
    report = run(library, opener, reader, clock, tmp_path)
    assert len(reader.requests) == 1  # the first paper is never sent
    assert report["withheld_protected"] == 2 and report["cards"] == []
    with pytest.raises(ValueError):
        library.card("arxiv-2610.00003v1")
    assert library.claim_state("2610.00003")["outcome"]["state"] == "WITHHELD"


def test_the_record_cap_bounds_new_papers(library, clock, tmp_path):
    opener = Opener([feed(entry(1), entry(2), entry(3))], clock)
    reader = Reader(reply())
    report = run(library, opener, reader, clock, tmp_path, max_records=1)
    assert report["status"] == "CAPPED" and len(reader.requests) == 1
    assert report["deduped"] == 1 and report["extracted"] == 1


def test_a_rejected_extraction_is_recorded_and_never_paid_again(
    library, clock, tmp_path
):
    reader = Reader(reply(text="not json"))
    report = run(
        library, Opener([feed(entry(2))], clock), reader, clock, tmp_path, hunt_id="r1"
    )
    assert report["rejected"] == 1 and report["reader_calls"] == 1
    again = Reader()
    run(library, Opener([feed(entry(2))], clock), again, clock, tmp_path, hunt_id="r2")
    assert again.requests == []


def test_a_checkpoint_runs_before_every_page_and_call(library, clock, tmp_path):
    calls = []

    class Paused(Exception):
        pass

    def checkpoint():
        calls.append(len(calls))
        if len(calls) == 2:
            raise Paused()

    reader = Reader(reply())
    with pytest.raises(Paused):
        run(
            library,
            Opener([feed(entry(2))], clock),
            reader,
            clock,
            tmp_path,
            hunt_id="pause",
            checkpoint=checkpoint,
        )
    assert reader.requests == []  # paused before the call, after the page
    report = run(
        library, Opener([], clock), Reader(reply()), clock, tmp_path, hunt_id="pause"
    )
    assert report["extracted"] == 1


# -- imports -------------------------------------------------------------------------


def test_imports_are_read_first_into_miner_import_cards(library, clock, tmp_path):
    queued = library.import_text(
        "My notes", "A DeepONet surrogate for battery charging."
    )
    reader = Reader(reply(), reply())
    report = run(library, Opener([feed(entry(2))], clock), reader, clock, tmp_path)
    sent = json.loads(reader.requests[0]["input"][0]["content"])
    assert sent["paper"] == {
        "source": "miner_import",
        "import_id": queued,
        "title": "My notes",
        "text": "A DeepONet surrogate for battery charging.",
    }
    assert report["imports"]["cards"] == [queued]
    assert library.pending_imports() == []
    card = library.card(queued)
    assert card["origin"] == "miner_import" and card["check_status"] == "UNCHECKED"
    assert card["abstract"] == "A DeepONet surrogate for battery charging."
    assert "miner import" in card["provenance"]
    view = MinerLiterature(
        library.pack,
        library,
        challenge=BATTERY_CHALLENGE,
        private_snapshot_digest=library.snapshot(),
        curation=None,
    )
    origins = view.record()["served_by_origin"]
    assert origins == {"shared": 1, "miner_hunt": 1, "miner_import": 1}


def test_an_import_whose_card_names_protected_material_is_withheld(library):
    queued = library.import_text("Notes", "Operator learning notes.")
    summary = hunt.extract_imports(library, reader=Reader(reply(cost="a draw_id")))
    assert summary["withheld_protected"] == 1 and summary["cards"] == []
    with pytest.raises(ValueError):
        library.card(queued)
    assert library.pending_imports() == []


# -- requests and the plan --------------------------------------------------------------


class Selection:
    """The shape of `model_provider.ModelSelection` the hunt reads."""

    model_id = "miner-model"
    provider_id = "miner-provider"
    settings = types.SimpleNamespace(reasoning_effort="low", max_output_tokens=2048)

    def record(self):
        return {"model": self.model_id, "provider_id": self.provider_id}


def test_a_complete_request_has_the_extraction_requests_shape():
    record = {
        "arxiv_id": "2610.00002v1",
        "title": "t",
        "abstract": "a",
        "categories": ["cs.LG"],
        "link": "https://arxiv.org/abs/2610.00002v1",
    }
    internal = method_cards.extraction_request(Selection(), record)
    miner = hunt.reader_request(method_cards.paper(record), Selection())
    assert list(miner) == list(internal)
    assert {k: v for k, v in miner.items() if k != "instructions"} == {
        k: v for k, v in internal.items() if k != "instructions"
    }
    assert miner["instructions"] == hunt.READER_PROMPT != internal["instructions"]
    body = hunt.reader_request(method_cards.paper(record))
    assert "model" not in body
    assert hunt.complete_request(body, Selection()) == miner
    assert hunt.reader_identity(miner) == hunt.reader_identity(dict(miner))
    assert hunt.reader_identity(miner).startswith("graphite-read-")


def test_the_reader_prompt_is_the_miner_variant_pinned_by_digest():
    assert "Graphite miner edition" in hunt.READER_PROMPT
    assert "internal research and testing agent" not in hunt.READER_PROMPT
    assert hunt.READER_PROMPT_DIGEST == digest(hunt.READER_PROMPT.encode("utf-8"))
    assert hunt.READER_PROMPT_DIGEST == READER_PROMPT_DIGEST
    # The miner variant is its own text; the internal prompt is not reused.
    assert hunt.READER_PROMPT != method_cards.READER_EXTRACTION_PROMPT
    assert set(method_cards.EXTRACTED_FIELDS) == {
        name
        for name in method_cards.EXTRACTED_FIELDS
        if f'"{name}"' in hunt.READER_PROMPT
    }


def test_a_hunt_with_a_selection_records_it_on_each_card(library, clock, tmp_path):
    reader = Reader(reply())
    run(
        library,
        Opener([feed(entry(2))], clock),
        reader,
        clock,
        tmp_path,
        selection=Selection(),
    )
    assert reader.requests[0]["model"] == "miner-model"
    stored = library.hunted.card("arxiv-2610.00002v1")
    assert stored["extraction"]["model"] == "miner-model"
    assert stored["extraction"]["origin"] == "miner_hunt"
    assert stored["extraction"]["prompt_digest"] == hunt.READER_PROMPT_DIGEST


def test_the_hunt_plan_orders_miner_learned_discovery_registered(library):
    library.record_outcome([f"arxiv-{PACK_PAPER}v1"], True, {"practice": "p-1"})
    discovery = {
        "title": "Battery fast charge",
        "models": {"rebuildable": [{"selector": "deeponet"}]},
    }
    plan = hunt.plan_queries(library, discovery=discovery, queries=["my query"])
    sources = [q["source"] for q in plan]
    assert sources[0] == "miner" and sources[1] == "learned"
    assert sources.index("discovery") < sources.index("registered")
    assert sources.count("registered") == len(literature_fetch.QUERY_SET.queries)
    assert len({q["search_query"] for q in plan}) == len(plan)
    for query in plan:
        literature_fetch.Query(
            query["query_id"], query["search_query"], query["purpose"]
        )


def test_a_launch_hunt_block_is_validated():
    assert hunt.validate_hunt(None) is None
    assert hunt.validate_hunt({}) == {"queries": [], "max_records": 200}
    assert hunt.validate_hunt({"queries": ["a  b"], "max_records": 5}) == {
        "queries": ["a b"],
        "max_records": 5,
    }
    for bad in (
        {"queries": ["a:b"]},
        {"max_records": 0},
        {"max_records": 5001},
        {"max_records": "10"},
        {"other": 1},
        [],
    ):
        with pytest.raises(hunt.HuntRefused) as refused:
            hunt.validate_hunt(bad)
        assert refused.value.code == "hunt_query_invalid"


def test_a_hunt_id_reused_with_another_plan_is_refused(library, clock, tmp_path):
    with pytest.raises(RuntimeError):
        run(
            library,
            Opener([feed(entry(2))], clock),
            Reader(RuntimeError("crash")),
            clock,
            tmp_path,
            hunt_id="same",
        )
    with pytest.raises(ValueError, match="reused"):
        run(
            library,
            Opener([], clock),
            Reader(),
            clock,
            tmp_path,
            hunt_id="same",
            max_records=7,
        )


#: The pinned digest of the miner Reader prompt (frozen by the edition plan).
READER_PROMPT_DIGEST = (
    "sha256:4c8d88e09da11f7ba18bc862be332adc6e913a6b44f71b81c463c46b714568a7"
)
