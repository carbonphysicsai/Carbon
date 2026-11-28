"""Offline SCALE reconstruction (`v2` remark + runtime 497 tx-version pin + payload
confirmation code), Unix-socket signer, 24h budget cap, and `FeePoster` cross-instance
`fcntl` lock + sticky `NOT_OBSERVED` tests (`B1`, `B7(b,c)`, `H10`, `H11`, `H15`).
"""

from __future__ import annotations

import datetime
import fcntl
import os
import shutil
import tempfile
import threading
from hashlib import blake2b
from pathlib import Path

import pytest
from bittensor.keyfiles import Keypair

from carbon.chain.external_signer import (
    SignerCode,
    SignerFailure,
    connect_signer,
    request_fee_burn,
)
from carbon.chain.fee_burns import ObservedFeeBurn, fee_remark_hash
from carbon.chain.fee_poster import FeePostCode, FeePoster
from carbon_miner_signer import commitment as cm
from carbon_miner_signer import fee_burn as fb
from carbon_miner_signer import signer as signer_cli
from carbon_miner_signer.signer import SignerServer

LIVE_MEASURED_HOTKEY = "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
RECEIVER_ALICE = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
RECEIVER_BOB = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


def _unsigned_and_payload(
    policy: fb.FeeBurnPolicy,
    hotkey: str,
    *,
    receiver: str = RECEIVER_ALICE,
    challenge_id: str = "electric-motor-magnetics",
    amount_rao: int = 25_000_000,
    limit_price_rao: int | None = None,
    era_current: int = 9_600_000,
    era_period: int = 128,
    nonce: int = 7,
    spec_version: int = 497,
    transaction_version: int = 1,
) -> tuple[dict, bytes, str, str]:
    call, _, remark_hash = fb.fee_burn_call(
        policy,
        hotkey=hotkey,
        receiver=receiver,
        challenge_id=challenge_id,
        amount_rao=amount_rao,
        limit_price_rao=limit_price_rao,
    )
    unsigned_stub = {
        "era": {"period": era_period, "current": era_current},
        "nonce": nonce,
        "spec_version": spec_version,
        "transaction_version": transaction_version,
        "era_block_hash": "0x" + "cd" * 32,
    }
    extra, additional = cm._extension_parts(policy, unsigned_stub)
    preimage = call + extra + additional
    confirm_code = blake2b(preimage, digest_size=32).hexdigest()[-8:]
    payload = (
        blake2b(preimage, digest_size=32).digest() if len(preimage) > 256 else preimage
    )
    unsigned = {
        "call_data": "0x" + call.hex(),
        "era": {"period": era_period, "current": era_current},
        "nonce": nonce,
        "tip": 0,
        "genesis_hash": policy.genesis_hash,
        "era_block_hash": "0x" + "cd" * 32,
        "spec_version": spec_version,
        "transaction_version": transaction_version,
        "metadata_hash": None,
        "included_in_extrinsic": "0x" + extra.hex(),
        "included_in_signed_data": "0x" + additional.hex(),
    }
    return unsigned, payload, remark_hash, confirm_code


def test_offline_scale_reconstruction_v2_remark_runtime_pins_and_1_tao_cap(
    monkeypatch,
):
    finney = fb.load_fee_burn_policy("finney")
    assert finney.max_single_burn_rao == 1_000_000_000  # 1.0 TAO hard cap (`M4` / `A2`)
    assert fb.DEFAULT_CLI_SINGLE_BURN_RAO == 100_000_000  # 0.10 TAO CLI default (`M4`)
    assert finney.transaction_version == 1
    assert finney.min_spec_version == 497

    call_f, remark_f, _ = fb.fee_burn_call(
        finney,
        hotkey=LIVE_MEASURED_HOTKEY,
        receiver=RECEIVER_ALICE,
        challenge_id="electric-motor-magnetics",
        amount_rao=25_000_000,
        limit_price_rao=None,
    )
    assert (
        remark_f
        == f"carbon.fee.v2|116|electric-motor-magnetics|{RECEIVER_ALICE}|{LIVE_MEASURED_HOTKEY}"
    )
    # Prefix matches runtime-497 `Utility.batch_all(2)` + `SubtensorModule.add_stake_burn(0x0784)`
    assert call_f.hex().startswith(
        "0b02080784" + "00" * 32 + "740040787d0100000000000007"
    )

    # Payload confirmation code changes when `amount_rao` changes (unlike remark hash!)
    _, _, rhash_25, code_25 = _unsigned_and_payload(
        finney, LIVE_MEASURED_HOTKEY, amount_rao=25_000_000
    )
    _, _, rhash_50, code_50 = _unsigned_and_payload(
        finney, LIVE_MEASURED_HOTKEY, amount_rao=50_000_000
    )
    assert rhash_25 == rhash_50
    assert code_25 != code_50

    # Wrong transaction_version (e.g. runtime upgrade changing extrinsic layout) fails closed!
    u_bad_txv, _, _, _ = _unsigned_and_payload(
        finney, LIVE_MEASURED_HOTKEY, transaction_version=2
    )
    with pytest.raises(fb.FeeBurnRefused) as exc:
        fb.check_request(
            finney,
            LIVE_MEASURED_HOTKEY,
            {
                "protocol": "carbon.miner-signer.v1",
                "op": "fee_burn",
                "netuid": 116,
                "challenge_id": "electric-motor-magnetics",
                "receiver": RECEIVER_ALICE,
                "amount_rao": 25_000_000,
                "limit_price_rao": None,
                "unsigned": u_bad_txv,
                "fee": {"partial_fee_rao": 150_000, "deposit_rao": 0},
            },
        )
    assert exc.value.refusal == fb.FeeBurnRefusal.PAYLOAD_MISMATCH

    # `N4`: Receiver equal to miner's own hotkey OR zero AccountId32 is ALWAYS refused (`BAD_RECEIVER`),
    # even when `--receiver` allow-list is omitted!
    for bad_rcvr in (RECEIVER_ALICE, LIVE_MEASURED_HOTKEY):
        with pytest.raises(fb.FeeBurnRefused) as exc_r:
            fb.fee_burn_call(
                finney,
                hotkey=RECEIVER_ALICE,
                receiver=bad_rcvr,
                challenge_id="electric-motor-magnetics",
                amount_rao=25_000_000,
                limit_price_rao=None,
            )
        assert exc_r.value.refusal == fb.FeeBurnRefusal.BAD_RECEIVER

    # Non-vacuous `N3` + `M4` CLI tests: patch `load_hotkey` and `key_file_problem` so
    # an unvalidated flag that reached key loading would fail with `AssertionError`!
    monkeypatch.setattr(
        signer_cli,
        "load_hotkey",
        lambda **_kw: (_ for _ in ()).throw(
            AssertionError("CLI must reject invalid fee flags BEFORE load_hotkey!")
        ),
    )
    monkeypatch.setattr(
        cm,
        "key_file_problem",
        lambda _p: (_ for _ in ()).throw(
            AssertionError("CLI must reject invalid fee flags BEFORE key_file_problem!")
        ),
    )
    for bad_argv in (
        ["--wallet", "w", "--hotkey", "h", "--max-daily-fee-tao", "0.5"],
        ["--wallet", "w", "--hotkey", "h", "--max-single-fee-tao", "0.1"],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "testnet",
            "--max-daily-fee-tao",
            "nan",
        ],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "testnet",
            "--max-daily-fee-tao",
            "inf",
        ],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "testnet",
            "--max-daily-fee-tao",
            "-0.1",
        ],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "testnet",
            "--max-daily-fee-tao",
            "0",
        ],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "finney",
            "--max-single-fee-tao",
            "1.5",
        ],
        [
            "--wallet",
            "w",
            "--hotkey",
            "h",
            "--enable-fee-burns",
            "finney",
            "--max-single-fee-tao",
            "0.0001",
        ],
    ):
        with pytest.raises(SystemExit):
            signer_cli.main(bad_argv)


def test_signer_fee_burn_default_disabled_tty_confirm_receiver_pin_and_24h_budget():
    short_dir = Path(tempfile.mkdtemp(prefix="csig-"))
    kp = Keypair.create_from_uri("//Charlie")
    sock = short_dir / "s.sock"
    policy_finney = fb.load_fee_burn_policy("finney")
    unsigned, payload, rhash, ccode = _unsigned_and_payload(
        policy_finney, kp.ss58_address, receiver=RECEIVER_ALICE
    )
    base_req = {
        "netuid": 116,
        "challenge_id": "electric-motor-magnetics",
        "receiver": RECEIVER_ALICE,
        "amount_rao": 25_000_000,
        "limit_price_rao": None,
        "unsigned": unsigned,
        "fee": {"partial_fee_rao": 150_000, "deposit_rao": 0},
    }

    # 1. Default signer (`fee_burn_policy=None`) refuses `FEE_BURN_DISABLED`.
    srv_off = SignerServer(kp, sock)
    srv_off.bind()
    t_off = threading.Thread(target=srv_off.serve_forever, daemon=True)
    t_off.start()
    try:
        ext = connect_signer(kp.ss58_address, socket_path=sock)
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(ext, base_req)
        assert exc.value.refusal == "FEE_BURN_DISABLED"
    finally:
        srv_off.close()
        t_off.join(timeout=2)

    # 2. Interactive TTY confirmation + `--receiver` allow-list + tampering rejections.
    expected_code = [ccode]
    srv_tty = SignerServer(
        kp,
        sock,
        receivers=(RECEIVER_ALICE,),
        fee_burn_policy=policy_finney,
        confirm=lambda _txt, code: expected_code[0] == code,
    )
    srv_tty.bind()
    t_tty = threading.Thread(target=srv_tty.serve_forever, daemon=True)
    t_tty.start()
    try:
        ext = connect_signer(kp.ss58_address, socket_path=sock)
        signed = request_fee_burn(ext, base_req)
        assert kp.verify(payload, signed["signature"])

        # Receiver not in `--receiver` allow-list -> BAD_RECEIVER
        u_bob, _, _, _ = _unsigned_and_payload(
            policy_finney,
            kp.ss58_address,
            receiver=RECEIVER_BOB,
            era_current=9_600_001,
            nonce=8,
        )
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(
                ext, {**base_req, "receiver": RECEIVER_BOB, "unsigned": u_bob}
            )
        assert exc.value.refusal == "BAD_RECEIVER"

        # Wrong confirmation code -> NOT_CONFIRMED
        expected_code[0] = "deadbeef"
        u2, _, _, ccode2 = _unsigned_and_payload(
            policy_finney, kp.ss58_address, era_current=9_600_001, nonce=8
        )
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(ext, {**base_req, "unsigned": u2})
        assert exc.value.refusal == "NOT_CONFIRMED"

        # Tampered call_data -> NOT_A_FEE_BURN
        expected_code[0] = ccode2
        tampered = {**u2, "call_data": "0x0500" + u2["call_data"][6:]}
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(ext, {**base_req, "unsigned": tampered})
        assert exc.value.refusal == "NOT_A_FEE_BURN"

        # Amount over 1.0 TAO single-burn ceiling -> AMOUNT_OVER_MAX (`M4`)
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(ext, {**base_req, "amount_rao": 1_500_000_000})
        assert exc.value.refusal == "AMOUNT_OVER_MAX"
    finally:
        srv_tty.close()
        t_tty.join(timeout=2)

    # 3. Unattended agent rolling 24h budget cap (`0.06 TAO` = 2 x `0.025 TAO`, 3rd refused, unlocks at +25h).
    clock_now = [datetime.datetime(2026, 11, 27, 8, 0, tzinfo=datetime.UTC)]
    budget_dir = short_dir / "b"
    budget_dir.mkdir()
    sock_b = budget_dir / "s.sock"
    budget_policy = fb.load_fee_burn_policy("finney", daily_budget_rao=60_000_000)
    srv_b = SignerServer(
        kp,
        sock_b,
        fee_burn_policy=budget_policy,
        confirm=lambda *_a: (_ for _ in ()).throw(
            AssertionError("must not prompt TTY")
        ),
        wall_clock=lambda: clock_now[0],
    )
    srv_b.bind()
    t_b = threading.Thread(target=srv_b.serve_forever, daemon=True)
    t_b.start()
    try:
        ext_b = connect_signer(kp.ss58_address, socket_path=sock_b)
        for step in (1, 2):
            u_s, pay_s, _, _ = _unsigned_and_payload(
                budget_policy,
                kp.ss58_address,
                era_current=9_600_100 + step,
                nonce=step,
            )
            ans = request_fee_burn(ext_b, {**base_req, "unsigned": u_s})
            assert kp.verify(pay_s, ans["signature"])

        u3, _, _, _ = _unsigned_and_payload(
            budget_policy, kp.ss58_address, era_current=9_600_103, nonce=3
        )
        with pytest.raises(SignerFailure) as exc:
            request_fee_burn(ext_b, {**base_req, "unsigned": u3})
        assert exc.value.refusal == "DAILY_BUDGET_EXCEEDED"

        clock_now[0] += datetime.timedelta(hours=25)
        ans_after = request_fee_burn(ext_b, {**base_req, "unsigned": u3})
        assert ans_after["remark_hash"] == rhash
    finally:
        srv_b.close()
        t_b.join(timeout=2)
        shutil.rmtree(short_dir, ignore_errors=True)


def test_fee_poster_cross_instance_flock_sticky_not_observed_and_range_reconcile(
    tmp_path,
):
    """Verify `H11` (`fcntl.flock` across separate instances), `B7(c)` (sticky
    `NOT_OBSERVED` prevents budget drain), `B7(b)` (`prune_unspent`), and `H15`
    (single-call `read_burns_in_range`)."""
    kp = Keypair.create_from_uri("//Bob")
    policy = fb.load_fee_burn_policy("finney")
    unsigned, payload, _, _ = _unsigned_and_payload(
        policy,
        kp.ss58_address,
        receiver=RECEIVER_ALICE,
        era_current=500,
        era_period=128,
    )

    sign_calls = []
    broadcast_calls = []
    range_calls = []
    finalized_head = [501]
    chain_burns: dict[int, list[ObservedFeeBurn]] = {}
    broadcast_mode = ["NOT_OBSERVED_FIRST"]

    class FakeChain:
        def finalized_block(self):
            return finalized_head[0]

        def read_burns_in_range(self, start_b, end_b):
            range_calls.append((start_b, end_b))
            return {
                b: tuple(chain_burns.get(b, []))
                for b in range(start_b, min(end_b, finalized_head[0]) + 1)
            }

        def prepare_and_estimate(self, **_kw):
            return (
                {"unsigned": unsigned, "payload": payload.hex()},
                {"partial_fee_rao": 120_000, "deposit_rao": 0},
            )

        def broadcast(self, _prep, _sig):
            broadcast_calls.append(1)
            if broadcast_mode[0] == "NOT_OBSERVED_FIRST":
                # Finalized block reported, but RPC node hasn't indexed the event yet!
                return {"outcome": "FINALIZED", "block": 501, "extrinsic_id": "501-2"}
            raise ConnectionResetError("connection dropped mid-finality")

    def fake_sign(_req):
        sign_calls.append(1)
        sig = bytes(kp.sign(payload))
        return {
            "signature": sig,
            "call": bytes.fromhex(unsigned["call_data"][2:]),
            "tx_fee_ceiling_rao": 5_000_000,
            "remark_hash": fee_remark_hash(
                116, "electric-motor-magnetics", RECEIVER_ALICE, kp.ss58_address
            ),
        }

    poster = FeePoster(
        hotkey=kp.ss58_address,
        receiver=RECEIVER_ALICE,
        netuid=116,
        challenge_id="electric-motor-magnetics",
        chain=FakeChain(),
        sign=fake_sign,
        state_dir=tmp_path,
        verify=lambda pay, sig, _hk: kp.verify(pay, sig),
    )

    # 1. Cross-process / cross-instance `fcntl.flock` test (`H11`):
    lock_fd = os.open(poster._lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        in_flight = poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
        assert in_flight["code"] == FeePostCode.IN_FLIGHT.value
        assert in_flight["retry_after_s"] == 12
        assert len(sign_calls) == 0
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    # 2. Signer refusal / Ctrl-C at prompt leaves NO pending state & returns colon-free code (`Merge Blocker 1`):
    from carbon.chain import fee_poster as fp_mod

    refusing_poster = FeePoster(
        hotkey=kp.ss58_address,
        receiver=RECEIVER_ALICE,
        netuid=116,
        challenge_id="electric-motor-magnetics",
        chain=FakeChain(),
        sign=lambda _r: (_ for _ in ()).throw(
            SignerFailure(SignerCode.REFUSED, "NOT_CONFIRMED")
        ),
        state_dir=tmp_path,
        verify=lambda pay, sig, _hk: kp.verify(pay, sig),
    )
    ref_out = refusing_poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
    assert ref_out["code"] == "NOT_CONFIRMED"  # No colon!
    assert refusing_poster.record()["state"] == "REFUSED"  # NOT in PENDING!

    # 3. Sticky `NOT_OBSERVED` (`B7(c)`): first broadcast returns `NOT_OBSERVED` (`FINALIZED_UNVERIFIED`),
    # and even AFTER `finalized_head` passes `era_current + era_period` (`628 -> 700`), a retry STILL
    # returns `NOT_OBSERVED` and NEVER signs a second burn!
    first = poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
    assert first["code"] == FeePostCode.NOT_OBSERVED.value
    assert len(sign_calls) == 1 and len(broadcast_calls) == 1

    finalized_head[0] = 700
    for _ in range(3):
        fresh_poster = FeePoster(
            hotkey=kp.ss58_address,
            receiver=RECEIVER_ALICE,
            netuid=116,
            challenge_id="electric-motor-magnetics",
            chain=FakeChain(),
            sign=fake_sign,
            state_dir=tmp_path,
            verify=lambda pay, sig, _hk: kp.verify(pay, sig),
        )
        pending = fresh_poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
        assert pending["code"] == FeePostCode.NOT_OBSERVED.value
    assert len(sign_calls) == 1 and len(broadcast_calls) == 1

    # However, if the door ALREADY indexed an unspent burn in `server_unspent`, `obtain_extrinsic`
    # reuses it immediately without being blocked by `FINALIZED_UNVERIFIED`!
    reused_door = poster.obtain_extrinsic(
        amount_rao=25_000_000, min_block=400, server_unspent=["499-1"]
    )
    assert reused_door == {
        "schema": fp_mod.SCHEMA,
        "code": FeePostCode.REUSED_UNSPENT.value,
        "extrinsic_id": "499-1",
    }

    # 4. Event at `finalized_block = 501` now becomes readable -> reconciles to `BURNED`!
    chain_burns[501] = [
        ObservedFeeBurn(
            extrinsic_id="501-2",
            block=501,
            extrinsic_idx=2,
            block_hash="0x" + "11" * 32,
            netuid=116,
            hotkey=kp.ss58_address,
            payer=kp.ss58_address,
            amount_rao=25_000_000,
            alpha_burned_rao=1_850_000_000,
            remark_hash=fee_remark_hash(
                116, "electric-motor-magnetics", RECEIVER_ALICE, kp.ss58_address
            ),
        )
    ]
    range_calls.clear()
    recovered = poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
    assert recovered["code"] == FeePostCode.BURNED.value
    assert recovered["extrinsic_id"] == "501-2"
    assert len(sign_calls) == 1

    # `confirm_extrinsic_missing_on_chain`: `501-2` is present -> False; `501-99` is absent -> True (`M1`)!
    assert poster.confirm_extrinsic_missing_on_chain("501-2") is False
    assert poster.confirm_extrinsic_missing_on_chain("501-99") is True

    # 5. Stale receipt pruning (`B7(b)`) & `UNKNOWN` broadcast chunked 32-block era scan -> `EXPIRED` + CLI `clear`:
    poster.prune_unspent("501-2")
    assert poster.record()["unspent"] == []

    broadcast_mode[0] = "DROP_NETWORK"
    finalized_head[0] = 510
    dropped = poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
    assert dropped["code"] == FeePostCode.AMBIGUOUS.value
    assert len(sign_calls) == 2

    # Advance past `500 + 128 = 628` -> scans in 32-block chunks (`RANGE_CHUNK_BLOCKS = 32`) and marks `EXPIRED`!
    range_calls.clear()
    finalized_head[0] = 630
    after_era = poster.obtain_extrinsic(amount_rao=25_000_000, min_block=400)
    # After `EXPIRED`, `obtain_extrinsic` returns `None` from `_reconcile_locked`? Wait: `_reconcile_locked` returns `None` and proceeds to broadcast #3!
    assert after_era["code"] == FeePostCode.AMBIGUOUS.value
    assert len(sign_calls) == 3
    assert all(e - s + 1 <= fp_mod.RANGE_CHUNK_BLOCKS for s, e in range_calls)

    # CLI `status` and `clear --force` work cleanly on `tmp_path`!
    assert fp_mod.main(["--dir", str(tmp_path), "status"]) == 0
    assert fp_mod.main(["--dir", str(tmp_path), "clear", "--force"]) == 0
    assert poster.record()["state"] == "IDLE"
