"""The Control Center's per-entry GPU readiness (OWNER-GPU-OPEN-WITH-READY-01): read from the validator's
public intake document, display only, unknown unless the validator said so."""

import pytest

from scripts.dev.miner_launchpad import gpu_readiness as g

CID, VER = "f08-ribbed-bracket", "1.7"
HEAD = "sha256:" + "ab" * 32


def facts(**official):
    document = {
        "schema": "carbon.construction.intake-public.v1",
        "challenge": {"id": CID, "version": VER},
    }
    if official:
        document["official_gpu"] = {
            "status": "OK",
            "ready": [],
            "log_head": HEAD,
            **official,
        }
    return document


@pytest.fixture(autouse=True)
def _clean():
    g._CACHE.clear()
    g._page["at"] = None
    g.page_read()  # a page is open unless a test says otherwise
    yield
    g._CACHE.clear()
    g._page["at"] = None


def test_ok_gives_the_ready_set():
    assert g.parse(facts(ready=["v2.f08.a", "v2.f08.b"]), CID, VER) == {
        "v2.f08.a",
        "v2.f08.b",
    }
    assert g.parse(facts(ready=[]), CID, VER) == frozenset()


@pytest.mark.parametrize(
    "status", ["STORE_ABSENT", "STORE_UNREADABLE", "UNAVAILABLE", "ok", None]
)
def test_any_other_status_is_unknown_not_nothing_ready(status):
    assert g.parse(facts(status=status, ready=[], log_head=None), CID, VER) is None


def test_an_older_receiver_with_no_key_is_unknown():
    assert g.parse(facts(), CID, VER) is None


def test_another_version_malformed_or_non_dict_answers_are_unknown():
    assert g.parse(facts(ready=["x"]), CID, "1.6") is None
    assert g.parse(facts(ready=["x"]), "f02", VER) is None
    assert g.parse(facts(ready="x"), CID, VER) is None
    assert g.parse(facts(ready=["x", 3]), CID, VER) is None
    assert g.parse(None, CID, VER) is None
    assert g.parse([], CID, VER) is None


def test_mark_labels_false_only_when_the_validator_listed_and_omitted_it():
    recipes = [{"catalog_id": "v2.f08.a"}, {"catalog_id": "v2.f08.b"}]
    assert [
        r["officially_gradable"] for r in g.mark(recipes, frozenset({"v2.f08.a"}))
    ] == [True, False]
    assert [r["officially_gradable"] for r in g.mark(recipes, None)] == [None, None]
    assert recipes == [
        {"catalog_id": "v2.f08.a"},
        {"catalog_id": "v2.f08.b"},
    ], "the input is not changed"


def test_lookup_reads_once_and_serves_the_cache_inside_the_ttl():
    calls = []

    def fetch(url):
        calls.append(url)
        return facts(ready=["v2.f08.a"])

    first = g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)
    second = g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)
    assert first == second == {"v2.f08.a"}
    assert calls == ["https://v.example/"]


def test_lookup_refreshes_when_stale_and_an_unreachable_intake_is_unknown(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(g.time, "monotonic", lambda: clock[0])
    state = {"fail": False}

    def fetch(url):
        if state["fail"]:
            raise OSError("unreachable")
        return facts(ready=["v2.f08.a"])

    assert g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False) == {
        "v2.f08.a"
    }
    clock[0] += g.TTL + 1
    state["fail"] = True
    # Stale: the refresh runs, fails, and the answer is unknown (never the old "ready").
    assert (
        g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False) is None
    )


def test_a_background_lookup_answers_at_once_without_waiting():
    import threading

    release = threading.Event()

    def slow(url):
        release.wait(5)
        return facts(ready=["v2.f08.a"])

    assert (
        g.lookup("https://v.example/", CID, VER, fetch=slow) is None
    ), "unknown until the first read ends"
    release.set()


def test_no_url_is_unknown():
    assert g.lookup(None, CID, VER, fetch=lambda url: 1 / 0, background=False) is None


def test_target_url_follows_the_profile_per_version_then_the_direct_target():
    target = {"intake_url": "https://v.example", "receiver_hotkey": "5" + "A" * 47}
    per_version = {"version_intakes": {CID: {VER: [target]}}}
    assert g.target_url(per_version, CID, VER) == "https://v.example"
    assert (
        g.target_url(per_version, CID, "1.6") is None
    ), "another version's endpoint never answers this one"
    direct = {
        "direct_intake_target": {"intake_url": "https://d.example"},
        "direct_intake_serves": {"id": CID, "version": VER},
    }
    assert g.target_url(direct, CID, VER) == "https://d.example"
    assert g.target_url(direct, CID, "1.6") is None
    assert (
        g.target_url({"intakes": {CID: "https://old.example"}}, CID, VER)
        == "https://old.example"
    )
    assert g.target_url(None, CID, VER) is None
    assert g.target_url({}, CID, VER) is None


def test_the_repository_receipts_are_never_consulted():
    import pathlib

    source = pathlib.Path(g.__file__).read_text(encoding="utf-8")
    assert "gpu_receipt" not in source and "officially_gradable(" not in source


def _clock(monkeypatch, start=1000.0):
    now = [start]
    monkeypatch.setattr(g.time, "monotonic", lambda: now[0])
    g.page_read()
    return now


def test_it_reads_at_most_once_a_minute(monkeypatch):
    now = _clock(monkeypatch)
    calls = []

    def fetch(url):
        calls.append(now[0])
        return facts(ready=["v2.f08.a"])

    assert g.TTL >= 60.0
    g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)
    now[0] += g.TTL - 1
    g.page_read()
    g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)
    assert len(calls) == 1, "no second read inside a minute"
    now[0] += 2
    g.page_read()
    g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)
    assert len(calls) == 2


def test_it_reads_only_while_a_page_is_open(monkeypatch):
    now = _clock(monkeypatch)
    calls = []

    def fetch(url):
        calls.append(1)
        return facts(ready=["v2.f08.a"])

    now[0] += g.PAGE_OPEN_SECONDS + 1  # the page's last read is long ago
    assert (
        g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False) is None
    )
    assert calls == [], "no read without an open page"
    g._page["at"] = None  # the start-up warm-up: no page has read yet
    assert (
        g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False) is None
    )
    assert calls == []


def test_only_the_pages_capabilities_route_marks_a_page_open():
    import pathlib

    source = (
        pathlib.Path(g.__file__)
        .parent.joinpath("controller.py")
        .read_text(encoding="utf-8")
    )
    assert source.count("gpu_readiness.page_read()") == 1
    at = source.index("gpu_readiness.page_read()")
    assert "control_center(self.server.research_runner)" in source[at : at + 200]
    warm = source[source.index("def _warm_capabilities") :]
    assert "page_read" not in warm[: warm.index("\ndef ") if "\ndef " in warm else 2000]


def test_it_backs_off_on_an_error_and_more_on_a_429_then_recovers(monkeypatch):
    from carbon.development_session.direct_submission import DirectIntakeRateLimit

    now = _clock(monkeypatch)
    calls = []
    outcome = ["error"]

    def fetch(url):
        calls.append(now[0])
        if outcome[0] == "error":
            raise OSError("unreachable")
        if outcome[0] == "429":
            raise DirectIntakeRateLimit()
        return facts(ready=["v2.f08.a"])

    def poll(advance):
        now[0] += advance
        g.page_read()
        return g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False)

    assert poll(0) is None and len(calls) == 1  # first failure: the wait doubles
    poll(g.TTL + 1)
    assert len(calls) == 1, "still waiting after one failure"
    poll(g.TTL)
    assert len(calls) == 2
    outcome[0] = "429"  # two failures so far: the wait is four minutes
    poll(g._wait(2) - 1)
    assert len(calls) == 2, "still inside the wait"
    poll(2)
    assert len(calls) == 3  # a 429 counts as two failures: the wait is now at the cap
    assert g._wait(4) == g.MAX_WAIT
    poll(g._wait(4) - 1)
    assert len(calls) == 3, "backed off further after a 429"
    poll(2)
    assert len(calls) == 4
    assert g._wait(50) == g.MAX_WAIT
    outcome[0] = "ok"
    poll(g.MAX_WAIT + 1)
    assert len(calls) == 5
    assert g.lookup("https://v.example/", CID, VER, fetch=fetch, background=False) == {
        "v2.f08.a"
    }
    poll(g.TTL - 1)
    assert len(calls) == 5
    poll(2)  # one success reset the wait to a minute
    assert len(calls) == 6
