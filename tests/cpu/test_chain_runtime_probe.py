"""The runtime-surface probe that gates adopting a new testnet runtime spec.

Offline: the runtime metadata here is constructed. The probe's online read
runs only on the operator's host.
"""

from __future__ import annotations

import copy

import pytest

from carbon.chain import runtime_probe as probe


def _ir_from(expected):
    """A runtime metadata IR that matches `expected`, as codegen would read it."""
    pallets = {}

    def pallet(name):
        return pallets.setdefault(
            name, {"name": name, "calls": [], "storage": [], "constants": []}
        )

    for key, args in expected["calls"].items():
        name, call = key.split(".")
        pallet(name)["calls"].append(
            {
                "name": call,
                "args": [
                    {"name": a, "type_ident": "Vec<u16>" if t == "Any" else t}
                    for a, t in args
                ],
                "docs": "",
            }
        )
    for key, value in expected["storage"].items():
        name, item = key.split(".")
        pallet(name)["storage"].append({"name": item, "value_type_ident": value})
    apis = {}
    for key in expected["runtime_apis"]:
        api, method = key.split(".")
        apis.setdefault(api, []).append(method)
    return {
        "spec_version": 471,
        "pallets": list(pallets.values()),
        "runtime_apis": [{"name": a, "methods": m} for a, m in apis.items()],
    }


def _expected():
    calls = {
        f"{p}.{c}": [["netuid", "NetUid"], ["dests", "Any"], ["version_key", "u64"]]
        for p, c in probe.SURFACE["calls"]
    }
    storage = {f"{p}.{s}": "u64" for p, s in probe.SURFACE["storage"]}
    apis = [f"{a}.{m}" for a, m in probe.SURFACE["runtime_apis"]]
    return {"calls": calls, "storage": storage, "runtime_apis": apis}


def _report(expected, ir):
    return probe.compare(
        expected,
        probe.observed_surface(ir),
        spec_version=ir["spec_version"],
        context={"fixture": True},
        raw_calls=probe.raw_call_types(ir),
    )


def test_an_unchanged_surface_is_compatible_and_authorizes_nothing():
    expected = _expected()
    report = _report(expected, _ir_from(expected))
    assert report["status"] == "COMPATIBLE_USED_SURFACE"
    assert report["differences"] == []
    assert report["claims"]["runtime_behaviour_verified"] is False
    assert report["claims"]["authorizes_publication"] is False


@pytest.mark.parametrize(
    ("mutate", "issue"),
    [
        (
            lambda ir: ir["pallets"][0]["calls"][0]["args"][1].update(name="uids"),
            "changed",
        ),
        (
            lambda ir: ir["pallets"][0]["calls"][0]["args"][2].update(type_ident="u32"),
            "changed",
        ),
        (lambda ir: ir["pallets"][0]["calls"].pop(0), "missing"),
        (lambda ir: ir["pallets"][0]["storage"].pop(0), "missing"),
        (lambda ir: ir["runtime_apis"].clear(), "missing"),
    ],
)
def test_a_changed_or_missing_used_item_is_incompatible(mutate, issue):
    expected = _expected()
    ir = _ir_from(expected)
    mutate(ir)
    report = _report(expected, ir)
    assert report["status"] == "INCOMPATIBLE"
    assert {d["issue"] for d in report["differences"]} == {issue}


def test_unused_additions_do_not_block_but_raw_changes_move_the_digest():
    expected = _expected()
    base = _ir_from(expected)
    added = copy.deepcopy(base)
    added["pallets"][0]["calls"].append({"name": "new_call", "args": [], "docs": ""})
    assert _report(expected, added)["status"] == "COMPATIBLE_USED_SURFACE"
    assert (
        _report(expected, added)["surface_digest"]
        == _report(expected, base)["surface_digest"]
    )
    # A structural argument the SDK types as Any: not a name/type mismatch,
    # but the reported raw types and the digest show it.
    widened = copy.deepcopy(base)
    widened["pallets"][0]["calls"][0]["args"][1]["type_ident"] = "Vec<u32>"
    report = _report(expected, widened)
    assert report["status"] == "COMPATIBLE_USED_SURFACE"
    assert report["surface_digest"] != _report(expected, base)["surface_digest"]
    first = next(iter(report["runtime_call_types"].values()))
    assert ["dests", "Vec<u32>"] in first


def test_the_pinned_sdk_binds_every_surface_item():
    pytest.importorskip("bittensor")
    from importlib.metadata import version

    if version("bittensor") != "11.1.0":
        pytest.skip("not the pinned SDK")
    expected = probe.expected_surface()
    assert None not in expected["calls"].values()
    assert None not in expected["storage"].values()
    assert len(expected["runtime_apis"]) == len(probe.SURFACE["runtime_apis"])


def test_main_loads_the_operator_config_given_on_the_command_line(monkeypatch, capsys):
    """The command line hands `--config` over as text, relative or absolute;
    `load_config` accepts only an absolute `Path`. Offline: the chain read is
    replaced, so this exercises exactly the argument path."""
    import asyncio
    import json
    from pathlib import Path

    example = Path(__file__).parents[2] / "docs/development"
    seen = {}

    async def offline(endpoint, genesis_hash):
        seen["endpoint"] = endpoint
        return {"status": "COMPATIBLE_USED_SURFACE", "spec_version": 471}

    monkeypatch.setattr(probe, "probe", offline)
    monkeypatch.setattr(asyncio, "run", lambda coroutine: _drain(coroutine))
    monkeypatch.chdir(example)
    for given in (
        "CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json",
        str(example / "CW1_DEVELOPMENT_TESTNET_OPERATOR.example.json"),
    ):
        assert probe.main(["--config", given]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["spec_version"] == 471
        assert type(report["operator_expected_runtime_spec"]) is int
    assert seen["endpoint"].startswith("wss://")


def _drain(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as done:
        return done.value
    raise AssertionError("the offline probe must not await anything")
