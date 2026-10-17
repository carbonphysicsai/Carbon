"""Closed private ingress provenance; synthetic requests, no host or listener."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_battery_intake import (
    DIGEST,
    MINER,
    STRATEGY,
    backend,  # noqa: F401 - fixture
    build,
    facts,
    post,
    refs,  # noqa: F401 - fixture
    signed,
)
from test_net2_transport import gateway, wire

from carbon.battery import intake as ib
from carbon.battery import intake_client as ic
from carbon.transport.models import (
    PATH,
    ReceiptRef,
    TransportCode,
    TransportFailure,
    _MalformedBranch,
    parse_message,
)
from carbon.transport.store import _NonceTransaction


@pytest.fixture
def deployed(tmp_path, request):
    return build(
        tmp_path, request.getfixturevalue("refs"), request.getfixturevalue("backend")
    )


@pytest.mark.parametrize(
    "headers,branch",
    [
        ([], "HEADERS_TYPE"),
        ({str(i): "" for i in range(17)}, "HEADER_COUNT"),
        ({1: ""}, "HEADER_VALUE_TYPE"),
        ({"x": 1}, "HEADER_VALUE_TYPE"),
        ({"x": "x" * 4096}, "HEADER_BUDGET"),
        ({"\u00e9": ""}, "HEADER_ASCII"),
        ({"x": "\u00e9"}, "HEADER_ASCII"),
        ({"x": "a\nb"}, "HEADER_LINE_BREAK"),
        ({"x": "a\rb"}, "HEADER_LINE_BREAK"),
        ({"x": "", "X": ""}, "HEADER_DUPLICATE"),
    ],
)
def test_existing_first_malformed_header_guard_keeps_code(tmp_path, headers, branch):
    gate = gateway(tmp_path)
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(gate.receive(wire(), headers))
    failure = caught.value
    assert failure.code is TransportCode.MALFORMED
    assert failure.args == ("TRANSPORT_MALFORMED",)
    assert str(failure) == "TRANSPORT_MALFORMED"
    assert failure._branch.value == branch
    assert gate.journal.highest_receipt() == 0


def test_guard_order_is_unchanged_and_does_not_parse_body_early(tmp_path):
    gate = gateway(tmp_path)
    specimens = [
        ({str(i): "\n" for i in range(17)}, b"{}", "HEADER_COUNT"),
        ({"x": "x" * 4096 + "\n"}, b"{}", "HEADER_BUDGET"),
        ({"x": "\u00e9\n"}, b"{}", "HEADER_ASCII"),
        ({"x": "", "X": "\n"}, b"{}", "HEADER_LINE_BREAK"),
        ({}, b"{}", "BODY_PARSE"),
    ]
    for headers, body, branch in specimens:
        with pytest.raises(TransportFailure) as caught:
            asyncio.run(gate.receive(body, headers))
        assert caught.value._branch.value == branch
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(gate.receive(b"{}", {}, method="GET"))
    assert caught.value.code is TransportCode.CONTEXT
    assert caught.value._branch is None


@pytest.mark.parametrize(
    "headers",
    [
        {str(i): "" for i in range(16)},
        {"x": "x" * 4095},
    ],
)
def test_exact_header_limits_reach_existing_body_parser(tmp_path, headers):
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(gateway(tmp_path).receive(b"{}", headers))
    assert caught.value._branch is _MalformedBranch.BODY_PARSE


@pytest.mark.parametrize("nonce", [-1, 2**63, True, "0"])
def test_nonce_malformed_provenance_is_private_and_before_sql(nonce):
    with pytest.raises(TransportFailure) as caught:
        _NonceTransaction(None).check_and_store("synthetic", nonce)
    assert caught.value._branch is _MalformedBranch.NONCE_RANGE
    assert str(caught.value) == "TRANSPORT_MALFORMED"


def test_malformed_reference_retains_public_failure(tmp_path):
    with pytest.raises(TransportFailure) as caught:
        gateway(tmp_path).journal.resolve(ReceiptRef(0, "0" * 64))
    assert caught.value._branch is _MalformedBranch.RECEIPT_REF
    assert str(caught.value) == "TRANSPORT_MALFORMED"


def records(capsys):
    return [json.loads(line) for line in capsys.readouterr().err.splitlines()]


def test_real_intake_body_then_header_refusal_has_only_closed_metadata(
    deployed, capsys
):
    intake, _ = deployed
    # Deliberately distinct inert markers must never leave these local fixtures.
    marker = "synthetic-private-marker"
    assert intake.handle("POST", PATH, {"x": marker}, b"{}", "198.51.100.7").body == {
        "refused": "TRANSPORT_MALFORMED"
    }
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="r1")
    headers = signed(MINER, body)
    while len(headers) < 17:
        headers["synthetic-" + str(len(headers))] = marker
    answer = intake.handle("POST", PATH, headers, body, "198.51.100.7")
    assert answer.status == 400
    assert answer.body == {"refused": "TRANSPORT_MALFORMED"}
    observed = records(capsys)
    assert [r["branch"] for r in observed] == ["BODY_PARSE", "HEADER_COUNT"]
    assert observed[-1]["header_count_capped_at_17"] == 17
    assert observed[-1]["header_count_over_limit"] is True
    assert observed[-1]["header_budget_over_limit"] is None
    assert set(observed[0]) == {
        "ts",
        "service",
        "event",
        "branch",
        "header_count_capped_at_17",
        "header_count_over_limit",
        "header_budget_over_limit",
    }
    assert all(r["event"] == "transport_malformed" for r in observed)
    encoded = json.dumps(observed)
    for secret in (marker, MINER.ss58_address, "198.51.100.7", "strategy_json"):
        assert secret not in encoded
    assert intake.inbox.received() == []
    assert intake.journal.highest_receipt() == 0
    # Negative control: removing excess headers admits the same original body.
    accepted = post(intake, MINER, body)
    assert accepted.status == 202
    assert intake.journal.highest_receipt() == 1
    assert len(intake.inbox.received()) == 1
    assert records(capsys) == []


def test_budget_type_and_unobserved_counts_are_bounded(capsys):
    recorder = ib._MalformedDiagnostics()
    recorder.note(
        TransportFailure(
            TransportCode.MALFORMED, _branch=_MalformedBranch.HEADER_BUDGET
        ),
        {"x": "x" * 4096},
    )
    recorder.note(
        TransportFailure(
            TransportCode.MALFORMED, _branch=_MalformedBranch.HEADER_VALUE_TYPE
        ),
        {"x": object()},
    )
    recorder.note(
        TransportFailure(
            TransportCode.MALFORMED, _branch=_MalformedBranch.HEADERS_TYPE
        ),
        [],
    )
    observed = records(capsys)
    assert observed[0]["header_budget_over_limit"] is True
    assert observed[1]["header_budget_over_limit"] is None
    assert observed[2]["header_count_capped_at_17"] is None
    assert observed[2]["header_count_over_limit"] is None


def test_parallel_and_arbitrary_diagnostics_emit_only_once_per_closed_branch(capsys):
    recorder = ib._MalformedDiagnostics()
    failures = [
        TransportFailure(TransportCode.MALFORMED, _branch=b) for b in _MalformedBranch
    ]
    unknown = TransportFailure(
        TransportCode.MALFORMED, _branch="synthetic-private-marker"
    )
    unknown._branch = "synthetic-private-marker"
    failures += [unknown, TransportFailure(TransportCode.CONTEXT)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda f: recorder.note(f, {}), failures * 20))
    observed = records(capsys)
    assert len(observed) == len(_MalformedBranch)
    assert {r["branch"] for r in observed} == {b.value for b in _MalformedBranch}
    assert "synthetic-private-marker" not in json.dumps(observed)


def test_failed_private_logging_keeps_actual_intake_refusal(deployed, monkeypatch):
    intake, _ = deployed

    def unavailable(*args, **kwargs):
        raise OSError("synthetic-private-marker")

    monkeypatch.setattr(ib, "log", unavailable)
    answer = intake.handle("POST", PATH, {}, b"{}", "198.51.100.7")
    assert answer.status == 400
    assert answer.body == {"refused": "TRANSPORT_MALFORMED"}
    assert intake.inbox.received() == []


def test_parser_never_includes_private_branch_in_exception_message():
    with pytest.raises(TransportFailure) as caught:
        parse_message(b"{}")
    assert caught.value._branch is _MalformedBranch.BODY_PARSE
    assert caught.value.args == ("TRANSPORT_MALFORMED",)
