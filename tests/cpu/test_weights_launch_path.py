"""The launch weights path, end to end with fixtures (Validator WEIGHTS_PATH_CHECK_20261026,
blockers B1, B2, B4). No chain, wallet, network or spend:

- B1: the bundle wrapper's `weights` command takes `--lean-pool` and hands it to the
  publication issuer; the unit renderer emits it (it was an AttributeError before);
- B2: `testnet-winner-v4-launch` names exactly the four launch Challenges by the ids the
  validator emits, and a pool store registered under `f08-ribbed-bracket` is accepted;
- B4: a sealed incumbent plus a registered noise gives the exact UID/weight vector and its
  daily halving; no registered noise gives no crown and a 100 % burn to UID 0.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_bank_koth_comparator import KEY, _Pairs, pair
from test_battery_od4a_dispatch import SPEC, Backend, chain, snapshot
from test_e8_weight_source_fixtures import NOISE, _registry, _set_body, _set_comparator

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.interface import digest
from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12
from carbon.validator_setup import __main__ as wrapper

LAUNCH = ("electric-motor-magnetics", "chip-cold-plate", "f08-ribbed-bracket", "f02")
CROWNED = "electric-motor-magnetics"
POLICY = wd.load_policy("testnet-winner-v4-launch")


# --- B2: the launch policy ------------------------------------------------------------


def test_the_launch_policy_names_the_four_launch_challenges_by_their_validator_ids():
    assert POLICY.challenges == LAUNCH
    # The ids are the validator's own: every one is a registered Challenge id.
    assert set(LAUNCH) <= set(exam_cap.registered_challenges())
    assert (POLICY.network, POLICY.netuid, POLICY.burn_uid) == ("testnet", 567, 0)
    assert POLICY.share == Q12 // 4
    assert POLICY.baselines == tuple(sorted((c, None) for c in LAUNCH))
    assert wd.network_authorized(POLICY.network, POLICY.netuid, POLICY.authority)


def test_the_launch_policy_is_registered_but_not_made_current():
    registry = json.loads((wd.POLICY_DIR / "registry.json").read_text())
    assert registry["current"] == "testnet-winner-v1"
    assert registry["versions"]["testnet-winner-v4-launch"] == POLICY.digest
    # Its only difference from the dev policy is the Ribbed Bracket id.
    dev = wd.load_policy("testnet-winner-v2-four-challenge-dev")
    assert [c if c != "f08" else "f08-ribbed-bracket" for c in dev.challenges] == list(
        POLICY.challenges
    )
    assert (dev.share, dev.cadence_blocks, dev.burn_uid) == (
        POLICY.share,
        POLICY.cadence_blocks,
        POLICY.burn_uid,
    )


def test_a_source_under_the_old_f08_id_is_outside_the_launch_policy(tmp_path):
    auth, _ = _standing(tmp_path)
    receipts = _journal(tmp_path)
    ledger = we.WinnerLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(twp.WinnerPublicationRefused, match="SOURCE_OUTSIDE_POLICY"):
        twp.TestnetWinnerIntentIssuer(receipts, auth, POLICY, ledger, {"f08": None})
    twp.TestnetWinnerIntentIssuer(
        receipts, auth, POLICY, ledger, {"f08-ribbed-bracket": lambda: None}
    )


# --- fixtures -------------------------------------------------------------------------


def _journal(tmp_path):
    from carbon.transport.store import ReceiptJournal

    return ReceiptJournal(tmp_path / "journal.sqlite3", chain())


def _standing(tmp_path):
    record = tmp_path / "owner-record.md"
    record.write_text("OWNER-TESTNET-WEIGHTS-01 fixture record")
    standing = tmp_path / "standing.json"
    standing.write_text(
        json.dumps(
            {
                "authority_record": record.name,
                "policy_digest": POLICY.digest,
                "publisher_hotkey": "owner-hotkey",
                "expected_runtime_spec": SPEC,
                "valid_from_block": 900,
                "valid_through_block": 2000,
            }
        )
    )
    standing.chmod(0o600)
    return twp.load_standing(standing, chain()), standing


def _pool(tmp_path, monkeypatch, name, *, registry=None):
    """A pool store; with a registry, it holds a sealed set-level crown for model `a`."""
    directory = tmp_path / name
    directory.mkdir()
    store = PoolStore(directory / "pool.sqlite", clock=lambda: 0.0)
    if registry is None:
        return store
    store.admit(
        "a",
        request_digest=digest(["request", "a"]),
        hotkey="miner-hotkey",
        challenge=CROWNED,
        strategy={},
        binding={"challenge": {"id": CROWNED}},
    )
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    comparator = _set_comparator(registry)
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(store, {"a": pair(_set_body("a", comparator, 0.9), None)}),
    )
    return store, flow.consider_private("a", KEY, comparator, sealed=True)


def _wrapper_args(monkeypatch, tmp_path, standing, pools):
    """The args the bundle wrapper's `weights preview` hands to the publication."""
    seen = {}
    monkeypatch.setattr(
        wrapper, "bound", lambda args: SimpleNamespace(root=tmp_path, digest="d")
    )
    monkeypatch.setattr(
        wrapper, "runtime_identity", lambda bundle: contextlib.nullcontext()
    )
    monkeypatch.setattr(wrapper, "runtime_lease", lambda path: contextlib.nullcontext())

    def capture(args, bundle):
        seen["args"] = args
        return 0, {"captured": True}

    monkeypatch.setattr(wrapper, "delegate", capture)
    argv = [
        "weights",
        "preview",
        "--bundle",
        str(tmp_path),
        "--digest",
        "d",
        "--config",
        "c",
        "--service-config",
        "s",
        "--standing",
        str(standing),
        "--journal",
        str(tmp_path / "journal.sqlite3"),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
        "--policy-version",
        "testnet-winner-v4-launch",
    ]
    for challenge, path in pools.items():
        argv += ["--lean-pool", f"{challenge}={path}"]
    assert wrapper.main(argv) == 0
    return seen["args"]


def _launch(tmp_path, monkeypatch, registry):
    """Four pool stores (Motor's holds the crown when a registry gives a noise)."""
    stores, crown = {}, None
    for challenge in LAUNCH:
        if challenge == CROWNED and registry is not None:
            store, crown = _pool(tmp_path, monkeypatch, challenge, registry=registry)
        else:
            store = _pool(tmp_path, monkeypatch, challenge)
        stores[challenge] = store
    _, standing = _standing(tmp_path)
    args = _wrapper_args(
        monkeypatch,
        tmp_path,
        standing,
        {c: tmp_path / c / "pool.sqlite" for c in LAUNCH},
    )
    config = SimpleNamespace(context=chain(), netuid=chain().netuid)
    issuer = twp._issuer(args, config, args.journal)
    return args, issuer, crown


def _publish(issuer, state):
    backend = Backend(state)
    publisher = twp.TestnetWinnerPublisher(issuer, backend)
    observed, _ = asyncio.run(backend.observe())
    return asyncio.run(publisher.publish(issuer.issue(observed))), backend


# --- B1: the wrapper reaches the issuer with --lean-pool ----------------------------------


def test_the_wrapper_parses_lean_pool_and_the_issuer_opens_each_store(
    tmp_path, monkeypatch
):
    args, issuer, _ = _launch(tmp_path, monkeypatch, None)
    assert args.lean_pool == [f"{c}={tmp_path / c / 'pool.sqlite'}" for c in LAUNCH]
    assert sorted(issuer.sources) == sorted(LAUNCH)
    assert issuer.policy.version == "testnet-winner-v4-launch"


def test_a_missing_pool_store_is_refused_never_created(tmp_path, monkeypatch):
    _, standing = _standing(tmp_path)
    args = _wrapper_args(
        monkeypatch, tmp_path, standing, {CROWNED: tmp_path / "absent" / "pool.sqlite"}
    )
    config = SimpleNamespace(context=chain(), netuid=chain().netuid)
    with pytest.raises(twp.WinnerPublicationRefused, match="LEAN_POOL_UNAVAILABLE"):
        twp._issuer(args, config, args.journal)
    assert not (tmp_path / "absent").exists()


# --- B4: sealed incumbent + registered noise -> the exact vector and its halving ----------


def test_a_sealed_crown_gets_its_share_the_rest_burns_and_the_share_halves_daily(
    tmp_path, monkeypatch
):
    registry = _registry(tmp_path, NOISE)
    _, issuer, crown = _launch(tmp_path, monkeypatch, registry)
    assert crown["outcome"] == bp.FIRST_INCUMBENT
    state = snapshot(chain(), block=925)
    miner = state.participants[1]
    assert (miner.uid, miner.hotkey) == (1, "miner-hotkey")
    share = Q12 // 4

    preview = twp.preview(issuer, state)
    assert preview["policy"] == "testnet-winner-v4-launch" and not preview["signed"]
    assert preview["records"][CROWNED]["hotkey"] == "miner-hotkey"
    assert preview["records"][CROWNED]["eligible"] is True
    assert [c for c, r in preview["records"].items() if r is None] == sorted(
        set(LAUNCH) - {CROWNED}
    )
    assert preview["targets"]["burn"] == Q12 - share
    assert [amount for _, amount in preview["targets"]["winners"]] == [share]

    result, backend = _publish(issuer, state)
    assert result["state"] == "ROW_VERIFIED"
    assert result["document"]["plan"]["q12"] == [[0, Q12 - share], [1, share]]
    assert backend.executions == 1

    # A day later the winner's share is halved and the difference burns.
    later = dataclasses.replace(state, timestamp_ms=state.timestamp_ms + DAY_MS)
    assert twp.preview(issuer, later)["targets"]["burn"] == Q12 - share // 2
    two_days = dataclasses.replace(later, timestamp_ms=later.timestamp_ms + DAY_MS)
    assert twp.preview(issuer, two_days)["targets"]["burn"] == Q12 - share // 4


def test_no_registered_noise_means_no_crown_and_everything_burns_to_uid_zero(
    tmp_path, monkeypatch
):
    registry = _registry(tmp_path, None)  # the live registry is empty until the recal
    _, issuer, crown = _launch(tmp_path, monkeypatch, registry)
    # No sealed incumbent is possible without a registered noise.
    assert (crown["outcome"], crown["reason"]) == (
        bp.UNAVAILABLE,
        "rebuild_noise_unregistered",
    )
    state = snapshot(chain(), block=925)
    preview = twp.preview(issuer, state)
    assert all(record is None for record in preview["records"].values())
    assert preview["targets"] == {
        "challenges": preview["targets"]["challenges"],
        "winners": [],
        "burn": Q12,
    }
    result, backend = _publish(issuer, state)
    assert result["document"]["plan"]["q12"] == [[0, Q12]]
    assert backend.executions == 1


def test_a_comparison_without_a_registered_noise_is_unavailable_not_a_crown(
    tmp_path, monkeypatch
):
    """The comparator itself, on the same fixture: UNAVAILABLE, and no incumbent set."""
    registry = _registry(tmp_path, None)
    store = _pool(tmp_path, monkeypatch, "noiseless")
    store.admit(
        "a",
        request_digest=digest(["request", "a"]),
        hotkey="miner-hotkey",
        challenge=CROWNED,
        strategy={},
        binding={"challenge": {"id": CROWNED}},
    )
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    comparator = _set_comparator(registry)
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(store, {"a": pair(_set_body("a", comparator, 0.9), None)}),
    )
    outcome = flow.consider_private("a", KEY, comparator, sealed=True)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert store.incumbent() is None


# --- B1: the weights unit carries --lean-pool -----------------------------------------


def _unit_profile(tmp_path, monkeypatch, **weights_changes):
    from test_validator_setup_units import arrangement

    profile, raw, _fetch, state = arrangement(tmp_path, monkeypatch)
    pools = []
    for challenge in ("electric-motor-magnetics", "f02"):
        store = state / challenge / "pool.sqlite"
        store.parent.mkdir()
        store.write_bytes(b"")
        pools.append(f"{challenge}={store}")
    raw["weights"].update({"lean_pools": pools, "battery_source": False})
    raw["weights"].update(weights_changes)
    profile.write_text(json.dumps(raw), encoding="utf-8")
    return profile, raw, pools


def _weights_argv(rendered, name="fixture-validator-weights.service"):
    import shlex

    line = next(
        row for row in rendered[name].splitlines() if row.startswith("ExecStart=")
    )
    return shlex.split(line.removeprefix("ExecStart="))


def test_the_weights_unit_passes_each_lean_pool_and_no_battery_source_when_none(
    tmp_path, monkeypatch
):
    from carbon.validator_setup import units

    profile, _, pools = _unit_profile(tmp_path, monkeypatch)
    argv = _weights_argv(units.render(profile))
    flagged = [argv[i + 1] for i, part in enumerate(argv) if part == "--lean-pool"]
    assert flagged == pools
    assert "--battery-deployment" not in argv
    assert argv[argv.index("weights") + 1] == "run"


def test_the_weights_unit_keeps_the_battery_source_unless_told_otherwise(
    tmp_path, monkeypatch
):
    from carbon.validator_setup import units

    profile, raw, _ = _unit_profile(tmp_path, monkeypatch, battery_source=True)
    argv = _weights_argv(units.render(profile))
    assert argv[argv.index("--battery-deployment") + 1] == raw["weights"]["deployment"]
    assert argv.count("--lean-pool") == 2


def test_a_profile_without_the_new_keys_renders_as_before(tmp_path, monkeypatch):
    from test_validator_setup_units import arrangement

    from carbon.validator_setup import units

    profile, raw, _fetch, _state = arrangement(tmp_path, monkeypatch)
    argv = _weights_argv(units.render(profile))
    assert "--lean-pool" not in argv
    assert argv[argv.index("--battery-deployment") + 1] == raw["weights"]["deployment"]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"lean_pools": []}, "EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED"),
        ({"lean_pools": ["no-equals-sign"]}, "EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED"),
        (
            {"lean_pools": ["f02=relative/pool.sqlite"]},
            "EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED",
        ),
        ({"battery_source": "no"}, "EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED"),
        ({"lean_pools": "f02=/x"}, "EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED"),
    ],
)
def test_malformed_weight_sources_refuse_before_any_unit_is_written(
    tmp_path, monkeypatch, change, code
):
    from carbon.validator_setup import units
    from carbon.validator_setup.bundle import SetupRefused

    profile, _, _ = _unit_profile(tmp_path, monkeypatch, **change)
    with pytest.raises(SetupRefused) as refused:
        units.render(profile)
    assert str(refused.value) == code


def test_duplicate_pool_ids_and_a_pool_outside_the_mounts_refuse(tmp_path, monkeypatch):
    from carbon.validator_setup import units
    from carbon.validator_setup.bundle import SetupRefused

    profile, raw, pools = _unit_profile(tmp_path, monkeypatch)
    duplicate = {**raw["weights"], "lean_pools": [pools[0], pools[0]]}
    profile.write_text(json.dumps({**raw, "weights": duplicate}), encoding="utf-8")
    with pytest.raises(SetupRefused, match="EXACT_OPERATOR_WEIGHT_SOURCES_REQUIRED"):
        units.render(profile)
    outside = tmp_path / "outside" / "pool.sqlite"
    outside.parent.mkdir()
    outside.write_bytes(b"")
    moved = {**raw["weights"], "lean_pools": [f"f02={outside}"]}
    profile.write_text(json.dumps({**raw, "weights": moved}), encoding="utf-8")
    with pytest.raises(SetupRefused, match="OPERATOR_PATH_NOT_MOUNTED_IDENTICALLY"):
        units.render(profile)


def test_one_of_the_two_new_keys_alone_is_not_a_profile(tmp_path, monkeypatch):
    from carbon.validator_setup import units
    from carbon.validator_setup.bundle import SetupRefused

    profile, raw, _ = _unit_profile(tmp_path, monkeypatch)
    del raw["weights"]["battery_source"]
    profile.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SetupRefused, match="EXACT_OPERATOR_UNIT_PROFILE_REQUIRED"):
        units.render(profile)
