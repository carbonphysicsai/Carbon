"""Comprehensive adversarial red-team & audit regression suite (`B1-B9`, `H1-H16`):
- 32-thread single-winner burn & credit atomic race.
- Real `Validator` + `LeanRecipeAdapter` preflight parity (`B3`, `H13`).
- Adversarial retry-credit farming matrix (`B4`, `H7`, `H8`, `H14`).
- Shared host-state ledger across version flips + real `version_close.close_queued` (`B5`, `B6`, `H5`).
- Client live preflight fee, `wait_s=0` payment deadline exclusion, `409 fee_not_finalized` retry,
  stale local burn auto-pruning, and `burst == 1` R89 rate-limit separation (`B7`, `B9`, `H1`, `H13`).
- Repo-cleanliness, Terms `v1` gate, per-version Mainnet scope, chained grace tiers, and kill-switch (`B2`, `B8`, `H2`, `H3`, `H12`).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import threading
from types import SimpleNamespace

import pytest

from carbon.chain.fee_burns import FeeBurnUnavailable, ObservedFeeBurn, fee_remark_hash
from carbon.chain.models import ChainContext
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import submission_fee as sf
from carbon.challenge_validator import submission_terms as st
from carbon.challenge_validator import version_close as vc
from carbon.challenge_validator.interface import Submission
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import direct_submission as client
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.reconstruction.served_recipe_contract import registered

HOTKEY_1 = "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
HOTKEY_2 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY_1 = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
RECEIVER_1 = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
RECEIVER_2 = "5HGjWAeFDfFCWPsjFQdVV2Msvz2XtMktvgocEZcCj68kUMaw"
BHASH = "0x" + "aa" * 32
FINNEY_GENESIS = "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03"


def _make_burn(
    extrinsic_id: str = "9600100-2",
    *,
    block: int = 9600100,
    idx: int = 2,
    netuid: int = 116,
    hotkey: str = HOTKEY_1,
    receiver: str = RECEIVER_1,
    payer: str = COLDKEY_1,
    amount_rao: int = 25_000_000,
    alpha_rao: int = 1_865_000_000,
    challenge_id: str = "electric-motor-magnetics",
) -> ObservedFeeBurn:
    return ObservedFeeBurn(
        extrinsic_id=extrinsic_id,
        block=block,
        extrinsic_idx=idx,
        block_hash=BHASH,
        netuid=netuid,
        hotkey=hotkey,
        payer=payer,
        amount_rao=amount_rao,
        alpha_burned_rao=alpha_rao,
        remark_hash=fee_remark_hash(netuid, challenge_id, receiver, hotkey),
    )


def _policy(
    amount_rao: int = 25_000_000, min_block: int = 9600000, netuid: int = 116
) -> sf.FeePolicy:
    return sf.FeePolicy(
        policy_version="tao-burn-v1",
        amount_rao=amount_rao,
        netuid=netuid,
        min_block=min_block,
    )


def _terms_v1() -> st.Terms:
    raw = (sf.REPO_ROOT / "docs/terms/carbon-submission-terms-v1.md").read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return st.Terms("carbon-submission-terms-v1", sha, raw)


def test_32_thread_double_spend_race_on_burn_and_credit_allows_at_most_one_winner(
    tmp_path,
):
    ledger = sf.FeeLedger(
        tmp_path / "fees.sqlite3",
        expected_netuid=116,
        expected_genesis_hash=FINNEY_GENESIS,
    )
    policy = _policy()
    ledger.record_indexed_block(9600100, [_make_burn()])

    barrier = threading.Barrier(32)

    def try_spend_burn(worker_idx: int):
        barrier.wait()
        try:
            with ledger.claim_for_admission(
                policy=policy,
                payment={"kind": "burn", "extrinsic_id": "9600100-2"},
                hotkey=HOTKEY_1,
                receiver=RECEIVER_1,
                challenge_id="electric-motor-magnetics",
                challenge_version="1.9",
                known_finalized_head=9600105,
            ) as commit:
                commit(f"rtsk_{worker_idx:064x}")
            return "ADMITTED"
        except sf.FeeRefused as refused:
            return refused.code

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        outcomes = list(pool.map(try_spend_burn, range(32)))

    assert outcomes.count("ADMITTED") == 1
    assert outcomes.count(sf.FEE_ALREADY_SPENT) == 31
    assert ledger.public_stats() == {
        "admitted_burns": 1,
        "burned_tao_rao": 25_000_000,
        "burned_alpha_rao": 1_865_000_000,
        "credits_issued": 0,
        "credits_redeemed": 0,
    }

    settlement = ledger.open_settlements(HOTKEY_1)[0]
    credit_id = ledger.issue_infra_credit_for_settlement(
        int(settlement["settlement_id"]),
        leaf_submission_id=str(settlement["submission_id"]),
        reason="build_failed_infra",
    )
    assert credit_id is not None

    barrier_c = threading.Barrier(32)

    def try_spend_credit(worker_idx: int):
        barrier_c.wait()
        try:
            with ledger.claim_for_admission(
                policy=policy,
                payment={"kind": "credit", "credit_id": credit_id},
                hotkey=HOTKEY_1,
                receiver=RECEIVER_1,
                challenge_id="electric-motor-magnetics",
                challenge_version="1.9",
                known_finalized_head=9600110,
            ) as commit:
                commit(f"rtsk_{100 + worker_idx:064x}")
            return "ADMITTED"
        except sf.FeeRefused as refused:
            return refused.code

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        c_outcomes = list(pool.map(try_spend_credit, range(32)))

    assert c_outcomes.count("ADMITTED") == 1
    assert c_outcomes.count(sf.FEE_CREDIT_ALREADY_SPENT) == 31


def test_real_validator_and_lean_recipe_adapter_dry_preflight_parity(
    tmp_path, monkeypatch
):
    """Regression for `B3`, `H5`, and `H13`: run `dry_preflight_submission` and
    `predict_submission_id` against a REAL `Validator` + `LeanRecipeAdapter`
    (`test_coldkey_waiting._door`), verifying `parse_strategy(..., max_bytes=...)`,
    schema/version checks, staged-workspace checks, and `coldkey_submission_waiting`
    with zero AttemptLedger side effects."""
    from test_coldkey_waiting import _door as coldkey_door

    request, adapter, attempt_ledger, door, _provider = coldkey_door(
        tmp_path, monkeypatch
    )
    intake = SimpleNamespace(
        door=door,
        adapter=adapter,
        challenge=SimpleNamespace(
            challenge_id=adapter.challenge_id, version=adapter.challenge_version
        ),
    )
    valid_dict = json.loads(json.dumps(request.recipe))

    def _sub(raw_json: str, seq: int = 1) -> Submission:
        return Submission(
            hotkey="miner",
            receipt={"sequence": seq, "digest": f"{seq:064x}", "block": 9600100},
            challenge_id=adapter.challenge_id,
            challenge_version=adapter.challenge_version,
            strategy_json=raw_json,
            contract_digest=adapter.contract_digest,
        )

    # 1. Invalid JSON -> `strategy_not_json`
    r_bad_json = sf.dry_preflight_submission(intake, _sub("{not-json"))
    assert r_bad_json["kind"] == "REFUSED" and r_bad_json["code"] == "strategy_not_json"

    # 2. Oversized JSON > `adapter.max_strategy_bytes` -> `oversized_submission` (`B3`)
    huge = json.dumps({**valid_dict, "pad": "x" * (adapter.max_strategy_bytes + 1024)})
    r_big = sf.dry_preflight_submission(intake, _sub(huge))
    assert r_big["kind"] == "REFUSED" and r_big["code"] == "oversized_submission"

    # 3. Wrong named version inside strategy JSON -> `challenge_mismatch` (`H13`)
    wrong_ver = {
        **valid_dict,
        "challenge": {**valid_dict["challenge"], "version": "9.9"},
    }
    r_ver = sf.dry_preflight_submission(intake, _sub(json.dumps(wrong_ver)))
    assert r_ver["kind"] == "REFUSED" and r_ver["code"] == "challenge_mismatch"

    # 4. Unstaged graph digest (`entrypoint=None`) -> `UNAVAILABLE` `construction_recipe_graph_workspace_missing` (`H13`)
    unstaged = {
        **valid_dict,
        "source": {"kind": "graph", "submission_digest": "sha256:" + "f" * 64},
        "procedure": {**valid_dict["procedure"], "entrypoint": None},
    }
    r_unstaged = sf.dry_preflight_submission(intake, _sub(json.dumps(unstaged)))
    assert (
        r_unstaged is not None
        and r_unstaged["kind"] == "UNAVAILABLE"
        and r_unstaged["code"] == "construction_recipe_graph_workspace_missing"
    )

    # 5. Real staged recipe passes dry preflight (`None`) with ZERO AttemptLedger rows!
    valid_sub = _sub(json.dumps(valid_dict, sort_keys=True), seq=1)
    assert sf.dry_preflight_submission(intake, valid_sub) is None
    assert attempt_ledger.submitted_outcomes(adapter.contract_digest) == ()

    # 6. `predict_submission_id` (`H5`) matches the exact deterministic `submission_id` admitted by `door.evaluate`!
    predicted = sf.predict_submission_id(intake, valid_sub)
    admitted = door.evaluate(valid_sub)
    assert admitted["kind"] == "OUTCOME"
    assert predicted == admitted["outcome"]["submission_id"]

    # 7. Second distinct recipe while first is `QUEUED` is caught by preflight (`coldkey_submission_waiting`)!
    second_dict = json.loads(json.dumps(valid_dict))
    second_dict["procedure"]["configuration"] = {"variant": 2}
    r_waiting = sf.dry_preflight_submission(
        intake, _sub(json.dumps(second_dict, sort_keys=True), seq=2)
    )
    assert (
        r_waiting is not None
        and r_waiting["kind"] == "UNAVAILABLE"
        and r_waiting["code"] == "coldkey_submission_waiting"
    )


def test_adversarial_credit_farming_matrix_and_operator_posthoc_release(tmp_path):
    """Regression for `B4`, `H6`, `H7`, `H8`, `H14`:
    - Miner-caused or ambiguous failures (`output_contract_differs`, `speed_outputs_disagree`,
      `WorkerFailure`, `nonfinite_output:unrecorded`, `worker_wall_limit_reached`, `DUPLICATE`,
      `WITHDRAWN_BY_MINER`, `withdrawn_by_miner` build cancel) mint ZERO credits!
    - `retry_scheduled` in-flight markers mint ZERO credits while auto_retry runs!
    - Unsettled `LeanRecipeAdapter._requeue_failed_build` waits (`H7`) and never double-credits!
    - Proven Carbon infra codes (`PoolStoreUnavailable`, `graded_program_changed`) mint 1 credit,
      and post-hoc operator `exam_graded` `RELEASED` upgrades `CONSUMED_TERMINAL -> CREDITED_INFRA` (`H14`).
    """
    ledger = sf.FeeLedger(tmp_path / "fees.sqlite3")
    policy = _policy()

    cases = [
        (
            "t_out_diff",
            {
                "state": "FAILED",
                "code": "output_contract_differs",
                "next_step": "slot_returned",
            },
            None,
            False,
        ),
        (
            "t_speed_diff",
            {
                "state": "FAILED",
                "code": "speed_outputs_disagree",
                "next_step": "slot_returned",
            },
            None,
            False,
        ),
        (
            "t_worker_fail",
            {
                "state": "FAILED",
                "code": "WorkerFailure:exit_1",
                "next_step": "slot_returned",
            },
            None,
            False,
        ),
        (
            "t_nonfin_unrec",
            {
                "state": "FAILED",
                "code": "nonfinite_output:unrecorded",
                "next_step": "slot_returned",
            },
            None,
            False,
        ),
        (
            "t_wall",
            {
                "state": "FAILED",
                "code": "WORKER_WALL_LIMIT_REACHED",
                "next_step": "slot_returned",
            },
            None,
            False,
        ),
        ("t_dup", {"state": "DUPLICATE", "code": "duplicate"}, None, False),
        (
            "t_withdrawn_m",
            {"state": "WITHDRAWN_BY_MINER", "code": "withdrawn_by_miner"},
            None,
            False,
        ),
        (
            "t_withdrawn_b",
            None,
            {"state": "FAILED_INFRA", "failure": {"code": "withdrawn_by_miner"}},
            False,
        ),
        (
            "t_retry_sched",
            {
                "state": "FAILED",
                "code": "grade_hung_carbon",
                "next_step": "retry_scheduled",
            },
            None,
            False,
        ),
        (
            "t_carbon_hung",
            {
                "state": "FAILED",
                "code": "grade_hung_carbon",
                "next_step": "slot_returned",
            },
            None,
            True,
        ),
        (
            "t_carbon_prog",
            {
                "state": "FAILED",
                "code": "graded_program_changed",
                "next_step": "resubmit_program_changed",
            },
            None,
            True,
        ),
    ]

    burns = [
        _make_burn(f"9600100-{i}", block=9600100, idx=i)
        for i in range(1, len(cases) + 3)
    ]
    ledger.record_indexed_block(9600100, burns)

    markers = {}
    outcomes = {}
    for idx, (tid, marker, proj, _expect_credit) in enumerate(cases, start=1):
        sub_id = f"rtsk_{idx:064x}"
        with ledger.claim_for_admission(
            policy=policy,
            payment={"kind": "burn", "extrinsic_id": f"9600100-{idx}"},
            hotkey=HOTKEY_1,
            receiver=RECEIVER_1,
            challenge_id="electric-motor-magnetics",
            challenge_version="1.9",
            known_finalized_head=9600105,
        ) as commit:
            commit(sub_id)
        if marker is not None:
            markers[sub_id] = marker
        outcomes[sub_id] = proj or {"state": "RECONSTRUCTED"}

    # Also test `H7`: real-adapter `_requeue_failed_build` race guard!
    h7_id = f"rtsk_{99:064x}"
    with ledger.claim_for_admission(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": f"9600100-{len(cases) + 1}"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
    ) as commit:
        commit(h7_id)
    outcomes[h7_id] = {"state": "FAILED_INFRA"}

    settled_set: set[str] = set()
    requeue_dir = tmp_path / "door_root" / "auto-grade" / "requeued"
    requeue_dir.mkdir(parents=True, mode=0o700)

    intake = SimpleNamespace(
        fee_ledger=ledger,
        challenge=SimpleNamespace(
            challenge_id="electric-motor-magnetics", version="1.9"
        ),
        version_closed={},
        grade_marker=lambda sid: markers.get(sid),
        adapter=SimpleNamespace(
            contract_digest="sha256:" + "c" * 64,
            _requeue_failed_build=lambda *_a: None,
            _requeue_settled=settled_set,
            failure_class=lambda _sid: "carbon_worker_killed",
            ledger=SimpleNamespace(
                path=tmp_path / "door_root" / "attempts.sqlite3",
                requeued_as=lambda *_a: None,
                miner_withdrawal=lambda *_a: None,
            ),
            outcome=lambda sid: outcomes[sid],
        ),
    )

    minted = sf.reconcile_hotkey_credits(intake, HOTKEY_1)
    # ONLY `t_carbon_hung` and `t_carbon_prog` mint credits! `h7_id` waits because not yet in `_requeue_settled`!
    assert len(minted) == 2

    # Once `_requeue_failed_build` settles `h7_id` (`carbon_worker_lost` in `CARBON_CLASSES`), mints 1 credit!
    settled_set.add(h7_id)
    minted_h7 = sf.reconcile_hotkey_credits(intake, HOTKEY_1)
    assert len(minted_h7) == 1

    # `t_retry_sched` (`idx=9`) finishes auto-retry as `GRADED` -> consumed, 0 credits!
    markers[f"rtsk_{9:064x}"] = {"state": "GRADED", "code": None}
    assert sf.reconcile_hotkey_credits(intake, HOTKEY_1) == []

    # `C2` (`H14`): Operator reclasses `t_wall` (`idx=5`, previously `CONSUMED_TERMINAL`) via
    # `infra_requeue reclass` (`reclass-kept/<task>.json` + `reclassed_not_the_candidates` marker)
    # -> upgrades `CONSUMED_TERMINAL -> CREDITED_INFRA` with ZERO AttemptLedger DB locks!
    wall_fail_id = f"rtsk_{5:064x}"
    assert (
        ledger.submission_fee_view(wall_fail_id, HOTKEY_1)["status"] == "CHARGED_BURN"
    )
    (requeue_dir / "reclass-kept").mkdir(mode=0o700, exist_ok=True)
    (requeue_dir / "reclass-kept" / f"{wall_fail_id}.json").write_text(
        "{}", encoding="utf-8"
    )
    markers[wall_fail_id] = {
        "state": "FAILED",
        "code": "reclassed_not_the_candidates",
        "next_step": "slot_returned",
    }
    minted_reclass = sf.reconcile_hotkey_credits(intake, HOTKEY_1)
    assert len(minted_reclass) == 1
    assert ledger.submission_fee_view(wall_fail_id, HOTKEY_1) == {
        "status": "CREDITED_INFRA",
        "credit_id": minted_reclass[0],
    }

    # `H6`: Idempotent resend of a requeued leaf `current_leaf_submission_id` does NOT spend a second burn!
    leaf_id = f"rtsk_{777:064x}"
    fresh_id = f"rtsk_{500:064x}"
    with ledger.claim_for_admission(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": f"9600100-{len(cases) + 2}"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
    ) as commit:
        commit(fresh_id)
    open_s = next(
        r for r in ledger.open_settlements(HOTKEY_1) if r["submission_id"] == fresh_id
    )
    ledger.advance_settlement_leaf(int(open_s["settlement_id"]), leaf_id)

    extra_burn = _make_burn("9600101-1", block=9600101, idx=1)
    ledger.record_indexed_block(9600101, [extra_burn])
    with ledger.claim_for_admission(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": "9600101-1"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
    ) as commit_dup:
        commit_dup(leaf_id)
    # `9600101-1` was released in-tx rather than double-charging `leaf_id`!
    assert "9600101-1" in ledger.unspent_burns_for_hotkey(
        netuid=116,
        challenge_id="electric-motor-magnetics",
        receiver=RECEIVER_1,
        hotkey=HOTKEY_1,
        min_block=9600000,
        known_finalized_head=9600105,
        policy=policy,
    )


def test_shared_host_ledger_across_version_flip_crash_recovery_and_version_close(
    tmp_path,
):
    """Regression for `B5`, `B6`, `A3`, `H5`:
    - Shared host ledger prevents spending one burn across `1.8` and `1.9` OR across receivers!
    - Door-scoped startup recovery (`recover_door_reservations`) leaves other doors' `RESERVED`
      rows untouched, commits crash-interrupted admitted tasks, and releases unadmitted ones!
    - Real `version_close.close_queued` mints `VERSION_CLOSED` credits into the shared host
      ledger and successor door redeems them!
    """
    host_dir = tmp_path / "submission-fee-netuid-116"
    shared_ledger = sf.FeeLedger(
        host_dir / sf.ledger_file_name(116),
        expected_netuid=116,
        expected_genesis_hash=FINNEY_GENESIS,
    )
    policy = _policy()
    shared_ledger.record_indexed_block(
        9600100,
        [
            _make_burn("9600100-1", idx=1, challenge_id="synthetic-linear-field-2d"),
            _make_burn("9600100-2", idx=2, challenge_id="synthetic-linear-field-2d"),
            _make_burn("9600100-3", idx=3, challenge_id="synthetic-linear-field-2d"),
        ],
    )

    # 1. Cross-validator replay (`RECEIVER_2` vs `RECEIVER_1`) -> refused (`A3`)!
    with (
        pytest.raises(sf.FeeRefused) as exc,
        shared_ledger.claim_for_admission(
            policy=policy,
            payment={"kind": "burn", "extrinsic_id": "9600100-1"},
            hotkey=HOTKEY_1,
            receiver=RECEIVER_2,
            challenge_id="synthetic-linear-field-2d",
            challenge_version="1.3",
            known_finalized_head=9600105,
        ),
    ):
        pass
    assert exc.value.code == sf.FEE_CHALLENGE_MISMATCH

    # 2. Spend `9600100-1` on old door root -> replay on new door root sharing `shared_ledger` is refused (`B5`)!
    old_root = tmp_path / "door-1.3"
    old_root.mkdir(mode=0o700)
    old_root.chmod(0o700)
    (old_root / "auto-grade" / "markers").mkdir(parents=True, mode=0o700)
    old_attempts = AttemptLedger(old_root / "attempts.sqlite3")
    contract = registered("synthetic-linear-field-2d", "1.3")
    queued_sub_id = "rtsk_" + "a" * 64
    old_attempts.record(
        Submission(
            hotkey=HOTKEY_1,
            receipt={"sequence": 1, "digest": "sha256:" + "1" * 64, "block": 9600100},
            challenge_id="synthetic-linear-field-2d",
            challenge_version="1.3",
            strategy_json="{}",
            contract_digest=contract.digest,
        ),
        kind="OUTCOME",
        submission_id=queued_sub_id,
        state="QUEUED",
    )
    with shared_ledger.claim_for_admission(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": "9600100-1"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="synthetic-linear-field-2d",
        challenge_version="1.3",
        known_finalized_head=9600105,
        door_id="door-1.3",
        expected_submission_id=queued_sub_id,
    ) as commit:
        commit(queued_sub_id)

    with (
        pytest.raises(sf.FeeRefused) as exc2,
        shared_ledger.claim_for_admission(
            policy=policy,
            payment={"kind": "burn", "extrinsic_id": "9600100-1"},
            hotkey=HOTKEY_1,
            receiver=RECEIVER_1,
            challenge_id="synthetic-linear-field-2d",
            challenge_version="1.4",
            known_finalized_head=9600110,
            door_id="door-1.4",
        ),
    ):
        pass
    assert exc2.value.code == sf.FEE_ALREADY_SPENT

    # 3. `H5` + `B5`: Simulate two leftover `RESERVED` rows (one on `door-other` still live, one on `door-1.3` admitted before crash)
    crashed_admitted_id = "rtsk_" + "b" * 64
    old_attempts.record(
        Submission(
            hotkey=HOTKEY_1,
            receipt={"sequence": 2, "digest": "sha256:" + "2" * 64, "block": 9600100},
            challenge_id="synthetic-linear-field-2d",
            challenge_version="1.3",
            strategy_json="{}",
            contract_digest=contract.digest,
        ),
        kind="OUTCOME",
        submission_id=crashed_admitted_id,
        state="QUEUED",
    )
    res_other = shared_ledger._reserve(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": "9600100-2"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="synthetic-linear-field-2d",
        challenge_version="1.4",
        known_finalized_head=9600105,
        door_id="door-other",
        expected_submission_id="rtsk_" + "c" * 64,
    )
    shared_ledger._reserve(
        policy=policy,
        payment={"kind": "burn", "extrinsic_id": "9600100-3"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="synthetic-linear-field-2d",
        challenge_version="1.3",
        known_finalized_head=9600105,
        door_id="door-1.3",
        expected_submission_id=crashed_admitted_id,
    )
    rec = shared_ledger.recover_door_reservations(
        "door-1.3",
        lambda sid: sf.is_outcome_admitted_in_attempt_ledger(
            old_attempts, contract.digest, sid
        ),
    )
    assert rec == {"committed": 1, "released": 0, "unknown": 0}
    # `door-other`'s RESERVED row (`9600100-2`) was NOT purged!
    assert "9600100-2" not in shared_ledger.unspent_burns_for_hotkey(
        netuid=116,
        challenge_id="synthetic-linear-field-2d",
        receiver=RECEIVER_1,
        hotkey=HOTKEY_1,
        min_block=9600000,
    )
    shared_ledger._release_reservation(res_other)

    # 4. `B6` + `L1`: Non-sibling root `other_tree/door-1.3` resolves to `host_dir` via
    # `fee_state_dir=host_dir`, refuses `fee_ledger_missing` if pointed at an empty dir,
    # and mints `VERSION_CLOSED` credits for BOTH ungraded tasks!
    with pytest.raises(vc.VersionCloseRefused, match="fee_ledger_missing"):
        vc.close_queued(
            old_root,
            challenge_id="synthetic-linear-field-2d",
            version="1.3",
            fee_state_dir=tmp_path / "empty-state-dir",
            netuid=116,
        )
    doc = vc.close_queued(
        old_root,
        challenge_id="synthetic-linear-field-2d",
        version="1.3",
        fee_state_dir=host_dir,
        netuid=116,
    )
    assert len(doc["closed"]) == 2
    cred_1 = shared_ledger.available_credit(HOTKEY_1, "synthetic-linear-field-2d")
    assert cred_1 is not None
    # Redeem that credit on successor version `1.4`!
    with shared_ledger.claim_for_admission(
        policy=policy,
        payment={"kind": "credit", "credit_id": cred_1},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="synthetic-linear-field-2d",
        challenge_version="1.4",
        known_finalized_head=9600120,
        door_id="door-1.4",
    ) as commit_new:
        commit_new("rtsk_" + "d" * 64)


def test_client_live_preflight_amount_deadline_exclusion_409_retry_stale_prune_and_r89(
    tmp_path, monkeypatch
):
    """Regression for `B7(a,b)`, `B9`, `H1`, `H13`."""
    contract = registered("synthetic-linear-field-2d", "1.3")
    ctx = ChainContext("finney", "wss://chain.example", "finney", FINNEY_GENESIS, 116)
    kit = bundle_material_v5()["construction_kit"]
    recipe = ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
    )

    class DummySigner:
        def __init__(self, _s):
            pass

        def sign(self, _body, *, receiver, nonce_ns):
            assert receiver == RECEIVER_1 and nonce_ns > 0
            return {"x-bittensor-signature": "0x00"}

    monkeypatch.setattr(client, "BittensorMessageSigner", DummySigner)

    # Cached `/info` has stale `amount_rao = 25_000_000`, while live preflight returns `50_000_000` (`H1`)!
    stale_info_facts = {
        "schema": client.PUBLIC_SCHEMA,
        "network": ctx.network,
        "genesis": ctx.genesis_hash,
        "netuid": ctx.netuid,
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
        "receiver": RECEIVER_1,
        "snapshot": {"id": "snap-1"},
        "discovery_path": client.INFO_PATH,
        "path": client.SUBMIT_PATH,
        "tools": [client.SUBMIT_TOOL, client.STATUS_TOOL],
        "served_contracts": [{"level": 0, "digest": contract.digest}],
        "fee": {
            "policy_version": "tao-burn-v1",
            "amount_rao": 25_000_000,
            "netuid": 116,
            "challenge_id": "synthetic-linear-field-2d",
            "receiver": RECEIVER_1,
            "min_block": 9600000,
            "remark_version": "carbon.fee.v2",
            "preflight_tool": "construction_preflight",
        },
        "score_pack": None,
        "qualification": False,
        "reward": False,
    }
    pinned = {
        "contract_digest": contract.digest,
        "rule_digest": "sha256:" + "b" * 64,
        "implementation_digest": "sha256:" + "c" * 64,
        "identities_digest": "sha256:" + "d" * 64,
    }

    fake_clock = [1000.0]
    pruned = []
    spent = []
    obtained_amounts = []

    class TrackingPoster:
        def __init__(self):
            self.calls = 0

        def obtain_extrinsic(self, *, amount_rao, **_kw):
            self.calls += 1
            obtained_amounts.append(amount_rao)
            if self.calls == 1:
                return {"code": "fee_burn_reused_unspent", "extrinsic_id": "9600050-1"}
            # Second call simulates 180s TTY confirm + chain finalization (`B9` `wait_s=0` deadline test!)
            fake_clock[0] += 180.0
            return {"code": "fee_burn_finalized", "extrinsic_id": "9600200-4"}

        def prune_unspent(self, ext_id):
            pruned.append(ext_id)

        def note_spent(self, ext_id):
            spent.append(ext_id)

    submit_calls = []

    def send_flow(_url, body, _hdrs):
        msg = json.loads(body)
        if msg["tool"] == "construction_preflight":
            return 200, {
                "schema": "carbon.construction.preflight-reply.v1",
                "admissible": True,
                "fee_status": "BURN_REQUIRED",
                "credit_id": None,
                "unspent_extrinsics": [],
                "fee": {**stale_info_facts["fee"], "amount_rao": 50_000_000},
            }
        assert msg["tool"] == client.SUBMIT_TOOL
        ext = msg["fields"]["fee_extrinsic"]
        submit_calls.append(ext)
        if ext == "9600050-1":
            # Stale local burn (`B7(b)`) -> client prunes and re-preflights!
            return 409, {"refused": "fee_already_spent"}
        if len(submit_calls) == 2:
            # First try with `9600200-4` hits R89 `429 rate` (`H13`) -> retries submit WITHOUT re-preflighting!
            return 429, {"refused": "rate"}
        if len(submit_calls) == 3:
            # Next try hits `409 fee_not_finalized` (`B9`) -> waits 6s and retries submit!
            return 409, {"refused": "fee_not_finalized"}
        return 202, {
            "schema": client.RESULT_SCHEMA,
            "kind": "OUTCOME",
            "code": None,
            "pinned": pinned,
            "outcome": {
                "schema": client.OUTCOME_SCHEMA,
                "submission_id": "rtsk_ok",
                "task_id": "rtsk_ok",
                "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
                "state": "ADMITTED",
                "evidence": contract.evidence_label,
                "qualification": False,
                "reward": False,
            },
            "evidence": "DEVELOPMENT",
            "qualification": False,
            "reward": False,
        }

    poster = TrackingPoster()
    with pytest.raises(client.DirectConstructionPending) as pending:
        client.submit_and_wait(
            "http://127.0.0.1:9080",
            "signer",
            root=tmp_path / "camp_launchpad",
            epoch=1,
            recipe=recipe,
            contract_digest=contract.digest,
            receiver=RECEIVER_1,
            context=ctx,
            read=lambda _u: stale_info_facts,
            send=send_flow,
            clock=lambda: fake_clock[0],
            sleep=lambda dt: fake_clock.__setitem__(0, fake_clock[0] + dt),
            fee_poster=poster,
            wait_s=0,  # Launchpad 30s admission budget (`B9`)!
        )
    assert pending.value.task_id == "rtsk_ok"
    assert obtained_amounts == [50_000_000, 50_000_000]  # Live preflight fee (`H1`)!
    assert pruned == ["9600050-1"]  # Stale local burn pruned (`B7(b)`)!
    assert spent == ["9600200-4"]  # Admitted burn marked spent!
    assert submit_calls == ["9600050-1", "9600200-4", "9600200-4", "9600200-4"]


def test_policy_repo_rejection_terms_v1_gate_chained_grace_and_kill_switch(tmp_path):
    """Regression for `B2`, `B7(a)`, `B8`, `A2`, `H2`, `H3`, `H12`."""
    policy_path = tmp_path / "submission_fee_policy.json"
    ledger_path = tmp_path / "submission_fees_116.sqlite3"

    # 1. `B2`: Writing policy or opening ledger inside `REPO_ROOT` is refused!
    with pytest.raises(ValueError):
        sf.update_policy_row(
            path=sf.REPO_ROOT
            / "scripts/validator_host_classes/submission_fee_policy.json",
            scope="567:*",
            enabled=True,
            amount_rao=25_000_000,
        )
    with pytest.raises(FeeBurnUnavailable):
        sf.FeeLedger(sf.REPO_ROOT / "bad_fees.sqlite3")

    # 2. `A2` & `H12`: Unprefixed scopes and Mainnet `116:*` wildcard enablement are refused!
    with pytest.raises(ValueError):
        sf.update_policy_row(
            path=policy_path,
            scope="electric-motor-magnetics 1.9",
            enabled=True,
            amount_rao=25_000_000,
            netuid=116,
        )
    with pytest.raises(ValueError):
        sf.update_policy_row(
            path=policy_path,
            scope="116:*",
            enabled=True,
            amount_rao=25_000_000,
        )

    # 3. `B8`: Mainnet per-version row (`116:electric-motor-magnetics 1.9`) requires Terms `v1`!
    assert (
        sf.main(
            [
                "--path",
                str(policy_path),
                "dial",
                "--scope",
                "116:electric-motor-magnetics 1.9",
                "--tao",
                "0.025",
                "--min-block",
                "9600000",
                "--policy-version",
                "motor19-v1",
            ]
        )
        == 0
    )
    pol_raw = sf.for_door(
        "electric-motor-magnetics", "1.9", expected_netuid=116, path=policy_path
    )
    assert pol_raw is not None and pol_raw.ready
    # Without Terms v1 (None or v0), `check_door_terms_for_fee` returns unready (`503`)!
    assert not sf.check_door_terms_for_fee(pol_raw, None).ready
    v0_terms = st.Terms("carbon-submission-terms-v0", "0" * 64, b"v0")
    assert not sf.check_door_terms_for_fee(pol_raw, v0_terms).ready
    assert sf.check_door_terms_for_fee(pol_raw, _terms_v1()).ready

    # 4. `H2`: Up-dial requires bounded `--current-head` + `--effective-from-block`, preserves
    # `policy_version`, and carries chained grace tiers (`0.025 -> 0.050 -> 0.075`)!
    with pytest.raises(ValueError):
        sf.update_policy_row(
            path=policy_path,
            scope="116:electric-motor-magnetics 1.9",
            enabled=True,
            amount_rao=50_000_000,
        )
    with pytest.raises(ValueError):
        # Far-future typo beyond `current_head + lookback` refused!
        sf.update_policy_row(
            path=policy_path,
            scope="116:electric-motor-magnetics 1.9",
            enabled=True,
            amount_rao=50_000_000,
            current_head=9_600_100,
            effective_from_block=9_900_000,
        )

    sf.update_policy_row(
        path=policy_path,
        scope="116:electric-motor-magnetics 1.9",
        enabled=True,
        amount_rao=50_000_000,
        current_head=9_600_100,
        effective_from_block=9_600_200,
    )
    sf.update_policy_row(
        path=policy_path,
        scope="116:electric-motor-magnetics 1.9",
        enabled=True,
        amount_rao=75_000_000,
        current_head=9_600_120,
        effective_from_block=9_600_300,
    )
    pol_chained = sf.for_door(
        "electric-motor-magnetics", "1.9", expected_netuid=116, path=policy_path
    )
    assert pol_chained.policy_version == "motor19-v1"  # Preserved!
    assert pol_chained.required_amount_at_block(9_600_150) == 25_000_000
    assert pol_chained.required_amount_at_block(9_600_250) == 50_000_000
    assert pol_chained.required_amount_at_block(9_600_350) == 75_000_000

    # 5. `B7(a)`: `unspent_burns_for_hotkey` filters out expired burns and sorts newest-first!
    ldg = sf.FeeLedger(
        ledger_path, expected_netuid=116, expected_genesis_hash=FINNEY_GENESIS
    )
    ldg.record_indexed_block(
        9_550_000,
        [_make_burn("9550000-1", block=9_550_000, idx=1, amount_rao=75_000_000)],
    )
    ldg.record_indexed_block(
        9_600_100,
        [_make_burn("9600100-1", block=9_600_100, idx=1, amount_rao=75_000_000)],
    )
    ldg.record_indexed_block(
        9_600_200,
        [_make_burn("9600200-1", block=9_600_200, idx=1, amount_rao=75_000_000)],
    )
    unspent = ldg.unspent_burns_for_hotkey(
        netuid=116,
        challenge_id="electric-motor-magnetics",
        receiver=RECEIVER_1,
        hotkey=HOTKEY_1,
        min_block=9_500_000,
        known_finalized_head=9_600_250,
        policy=pol_chained,
    )
    assert unspent == ["9600200-1", "9600100-1"]  # `9550000-1` expired; newest-first!

    # 6. `H3`: `LiveFeePolicySource` fails closed (`503`) if active file disappears,
    # `disable --scope 116:*` overrides version rows, and `disable --kill-switch --force` repairs corrupt JSON!
    transitions = []
    fake_intake = SimpleNamespace(
        submission_fee=None, fee_ledger=None, fee_indexer=None
    )
    watcher = sf.LiveFeePolicySource(
        fake_intake,
        challenge_id="electric-motor-magnetics",
        version="1.9",
        expected_netuid=116,
        expected_genesis_hash=FINNEY_GENESIS,
        ledger_path=ledger_path,
        path=policy_path,
        log_fn=lambda ev, **kw: transitions.append((ev, kw)),
        refresh_interval_s=0.0,
    )
    assert watcher.current() is not None and watcher.current().ready

    # Accidental deletion after active -> fail closed (`UNREADABLE_POLICY`, not dark!)
    saved_bytes = policy_path.read_bytes()
    policy_path.unlink()
    missing_pol = watcher.current(force=True)
    assert missing_pol is not None and not missing_pol.ready

    # Restore file, then disable `116:*` -> overrides `116:electric-motor-magnetics 1.9` cleanly!
    policy_path.write_bytes(saved_bytes)
    assert watcher.current(force=True).ready
    assert sf.main(["--path", str(policy_path), "disable", "--scope", "116:*"]) == 0
    assert watcher.current(force=True) is None

    # Corrupt file repaired by `disable --kill-switch --force`!
    policy_path.write_text("<<<CORRUPT>>>", encoding="utf-8")
    assert not watcher.current(force=True).ready
    assert (
        sf.main(["--path", str(policy_path), "disable", "--kill-switch", "--force"])
        == 0
    )
    assert watcher.current(force=True) is None
    assert len(transitions) >= 4
    watcher.close()


def test_reaudit_l1_c1_c7_m1_m3_b8_b9_h3_h13_multiprocess_and_real_feeposter(
    tmp_path, monkeypatch, capsys
):
    """Comprehensive regression suite covering every remaining re-audit item:
    - `B8`: Hardcoded SHA-256 literal pin (`321100f9...`) + tampered body rejection.
    - `C3`: Repo-wide source grep conformance test for every `PROVEN_CARBON_GRADE_CODES`
      and `PROVEN_CARBON_GRADE_PREFIXES` entry + contended wall-stop `MinerProgramFailure`.
    - `C1`, `C6`, `C7`: Hyphenated `rebuild-requests.jsonl` / `stop-cancelled.jsonl`,
      `carbon_unclassified` vs `CARBON_CLASSES`, `owed_list` & `next_step=None` mutual
      exclusion, `releases.jsonl`, and `credit-settlement` CLI.
    - `L1`, `C4`, `C5`: Non-sibling roots sharing fixed state dir, three-state crash
      recovery (`recipe_task_intents` = False, `None` prediction / DB error = None kept
      `RESERVED`, post-admit commit failure -> typed `503`), per-door process lease.
    - `H3`: `kill_switch` clears bad-row `503`, `dial` refuses without `--clear-kill-switch`,
      `disable --force` forensic backup, cross-restart armed flag, `EACCES` fail-closed,
      `stats` non-creating check.
    - `H13`: Real `RequestBuckets` `burst=1` preflight exemption.
    - Cross-process (`subprocess`) `FeeLedger` double-spend race + `-wal`/`0600` check.
    - `B9`, `M1`, `M2`, `M3`, `N5`, and end-to-end real `FeePoster` + `submit_and_wait`!
    """
    import os
    import stat
    import subprocess
    import sys

    from bittensor.keyfiles import Keypair

    from carbon.chain.fee_poster import FeePoster
    from carbon.challenge_validator.request_buckets import RequestBuckets
    from carbon_miner_signer import commitment as cm
    from carbon_miner_signer import fee_burn as fb

    # 1. `B8`: Literal SHA-256 pin for `carbon-submission-terms-v1` (never self-hashed!)
    expected_v1_sha = "321100f9b4342f36a13bd9cf5c0bfbefbca99a44543e4e8da99c4760315ff1a5"
    assert sf.TERMS_V1_SHA256 == expected_v1_sha
    assert st.PINNED_SHA256["carbon-submission-terms-v1"] == expected_v1_sha
    pol = _policy()
    real_v1 = _terms_v1()
    assert real_v1.sha256 == expected_v1_sha
    assert sf.check_door_terms_for_fee(pol, real_v1).ready
    # Wrong sha or tampered bytes under the right name MUST fail closed (`503`)!
    for spoof_terms in (
        st.Terms("carbon-submission-terms-v1", "f" * 64, b"fake terms"),
        st.Terms("carbon-submission-terms-v1", expected_v1_sha, b"tampered body"),
        SimpleNamespace(
            version="carbon-submission-terms-v1", sha256="f" * 64, ready=True
        ),
    ):
        assert not sf.check_door_terms_for_fee(pol, spoof_terms).ready

    # 2. `C3`: Repo-wide conformance check — EVERY entry in `PROVEN_CARBON_GRADE_CODES`
    # and `PROVEN_CARBON_GRADE_PREFIXES` MUST appear verbatim in `carbon/` outside `submission_fee.py`!
    corpus_parts = []
    for py_file in sorted((sf.REPO_ROOT / "carbon").rglob("*.py")):
        if py_file.name == "submission_fee.py":
            continue
        corpus_parts.append(py_file.read_text(encoding="utf-8", errors="ignore"))
    corpus = "\n".join(corpus_parts)
    missing_codes = [c for c in sf.PROVEN_CARBON_GRADE_CODES if c not in corpus]
    missing_prefixes = [p for p in sf.PROVEN_CARBON_GRADE_PREFIXES if p not in corpus]
    assert missing_codes == [], f"Phantom codes in allow-list: {missing_codes}"
    assert missing_prefixes == [], f"Phantom prefixes in allow-list: {missing_prefixes}"

    # Contended wall-stop `MinerProgramFailure` (`infra_requeue._carbons_failure`) vs candidate crash
    fail_dir = tmp_path / "failures"
    fail_dir.mkdir()
    contended_txt = fail_dir / "contended.txt"
    contended_txt.write_text(
        "Traceback (most recent call last):\n"
        "carbon.development_session.research_carrier.MinerProgramFailure: WORKER_WALL_LIMIT_REACHED\n\n"
        "code: reconstruction.worker.deadline.exceeded\n"
        "private diagnostic (worker output, truncated):\nharmless\n",
        encoding="utf-8",
    )
    spoof_txt = fail_dir / "spoof.txt"
    spoof_txt.write_text(
        "Traceback (most recent call last):\n"
        "carbon.development_session.research_carrier.MinerProgramFailure: NONZERO_EXIT\n\n"
        "code: reconstruction.worker.process.nonzero_exit\n"
        "private diagnostic (worker output, truncated):\n"
        "carbon.development_session.research_carrier.MinerProgramFailure: WORKER_WALL_LIMIT_REACHED\n\n"
        "code: reconstruction.worker.deadline.exceeded\n",
        encoding="utf-8",
    )
    assert (
        sf._classify_failed_grade_marker(
            {
                "state": "FAILED",
                "code": "MinerProgramFailure",
                "next_step": "slot_returned",
            },
            failure_path=contended_txt,
        )
        == "CREDIT"
    )
    assert (
        sf._classify_failed_grade_marker(
            {
                "state": "FAILED",
                "code": "MinerProgramFailure",
                "next_step": "slot_returned",
            },
            failure_path=spoof_txt,
        )
        == "CONSUMED"
    )

    # 3. `C1`, `C6`, `C7`: Hyphenated rebuild files, `carbon_unclassified`, `owed_list` & `releases.jsonl`
    droot = tmp_path / "c_items_door"
    (droot / "auto-grade" / "requeued").mkdir(parents=True, mode=0o700)
    (droot / "auto-grade" / "failures").mkdir(parents=True, mode=0o700)
    requeue_d = droot / "auto-grade" / "requeued"
    c_ledger = sf.FeeLedger(tmp_path / "c_items_fees.sqlite3")
    c_ledger.record_indexed_block(
        9600100,
        [_make_burn(f"9600100-{i}", idx=i) for i in range(1, 7)],
    )
    sub_stop = "rtsk_" + "1" * 64
    sub_unclass = "rtsk_" + "2" * 64
    sub_carbon = "rtsk_" + "3" * 64
    sub_owed = "rtsk_" + "4" * 64
    sub_counted_undeliv = "rtsk_" + "5" * 64
    for idx, sid in enumerate(
        (sub_stop, sub_unclass, sub_carbon, sub_owed, sub_counted_undeliv), start=1
    ):
        with c_ledger.claim_for_admission(
            policy=pol,
            payment={"kind": "burn", "extrinsic_id": f"9600100-{idx}"},
            hotkey=HOTKEY_1,
            receiver=RECEIVER_1,
            challenge_id="electric-motor-magnetics",
            challenge_version="1.9",
            known_finalized_head=9600105,
        ) as cm_fn:
            cm_fn(sid)

    # Write real hyphenated `stop-cancelled.jsonl` (`C1`) and `auto-retry-alerts.jsonl` (`C7`)
    (requeue_d / "stop-cancelled.jsonl").write_text(
        json.dumps({"task": sub_stop}) + "\n", encoding="utf-8"
    )
    (requeue_d / "auto-retry-alerts.jsonl").write_text(
        json.dumps(
            {"task": sub_owed, "event": "auto_retry_cap_spent", "reason": "owed_list"}
        )
        + "\n",
        encoding="utf-8",
    )
    fclasses = {
        sub_stop: "carbon_worker_killed",
        sub_unclass: "carbon_unclassified",
        sub_carbon: "carbon_worker_killed",
    }
    c_markers = {
        sub_owed: {
            "state": "FAILED",
            "code": "graded_query_unavailable",
            "next_step": "slot_returned",
        },
        sub_counted_undeliv: {
            "state": "FAILED",
            "code": "graded_query_unavailable",
            "next_step": None,
        },
    }
    c_intake = SimpleNamespace(
        fee_ledger=c_ledger,
        challenge=SimpleNamespace(
            challenge_id="electric-motor-magnetics", version="1.9"
        ),
        version_closed={},
        grade_marker=lambda sid: c_markers.get(sid),
        adapter=SimpleNamespace(
            contract_digest="sha256:" + "d" * 64,
            _requeue_failed_build=lambda *_a: None,
            _requeue_settled={sub_stop, sub_unclass, sub_carbon},
            failure_class=lambda sid: fclasses.get(sid),
            ledger=SimpleNamespace(
                path=droot / "attempts.sqlite3",
                requeued_as=lambda *_a: None,
                miner_withdrawal=lambda *_a: None,
            ),
            outcome=lambda _sid: {"state": "FAILED_INFRA"},
        ),
    )
    minted_c = sf.reconcile_hotkey_credits(c_intake, HOTKEY_1)
    # ONLY `sub_carbon` mints! `sub_stop` held by `stop-cancelled.jsonl` (`C1`),
    # `sub_unclass` consumed (`C6`), `sub_owed` & `sub_counted_undeliv` held `ADMITTED` (`C7`)!
    assert len(minted_c) == 1
    assert (
        c_ledger.submission_fee_view(sub_carbon, HOTKEY_1)["status"] == "CREDITED_INFRA"
    )
    assert (
        c_ledger.submission_fee_view(sub_unclass, HOTKEY_1)["status"] == "CHARGED_BURN"
    )
    open_ids = {r["submission_id"] for r in c_ledger.open_settlements(HOTKEY_1)}
    assert open_ids == {sub_stop, sub_owed, sub_counted_undeliv}

    # Operator runs `infra_requeue release` on `sub_counted_undeliv` (`releases.jsonl`) -> credits!
    (requeue_d / "releases.jsonl").write_text(
        json.dumps(
            {
                "task": sub_counted_undeliv,
                "state": "RELEASED",
                "status": "FAILED_INFRA",
                "reason": "result_not_delivered",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    minted_rel = sf.reconcile_hotkey_credits(c_intake, HOTKEY_1)
    assert len(minted_rel) == 1
    assert (
        c_ledger.submission_fee_view(sub_counted_undeliv, HOTKEY_1)["status"]
        == "CREDITED_INFRA"
    )

    # 4. `L1`, `C4`, `C5`: Non-sibling roots, three-state crash recovery, & process lease
    state_fixed = tmp_path / "fixed-host-state"
    monkeypatch.setenv("CARBON_SUBMISSION_FEE_STATE_DIR", str(state_fixed))
    assert sf.resolve_host_state_dir(
        netuid=116, receiver_root=tmp_path / "tree_a" / "motor18"
    ) == sf.resolve_host_state_dir(
        netuid=116, receiver_root=tmp_path / "tree_b" / "deep" / "motor19"
    )
    monkeypatch.delenv("CARBON_SUBMISSION_FEE_STATE_DIR")

    rec_root = tmp_path / "rec_door"
    rec_root.mkdir(mode=0o700)
    rec_root.chmod(0o700)
    rec_attempts = AttemptLedger(rec_root / "attempts.sqlite3")
    contract_s = registered("synthetic-linear-field-2d", "1.3")
    # Record ONLY a `recipe_task_intents` row (NOT an `OUTCOME` row!) -> must evaluate as `False` (`C4`)!
    intent_only_id = "rtsk_" + "9" * 64
    rec_attempts.record_recipe_task_intent(
        contract_s.digest, intent_only_id, HOTKEY_1, "sha256:" + "0" * 64
    )
    assert (
        sf.is_outcome_admitted_in_attempt_ledger(
            rec_attempts, contract_s.digest, intent_only_id
        )
        is False
    )

    rec_fee_db = sf.FeeLedger(tmp_path / "rec_fees.sqlite3")
    rec_fee_db.record_indexed_block(
        9600100,
        [_make_burn(f"9600100-{i}", idx=i) for i in (1, 2, 3, 4)],
    )
    # Row 1: `intent_only_id` (`False` -> released!)
    rec_fee_db._reserve(
        policy=pol,
        payment={"kind": "burn", "extrinsic_id": "9600100-1"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
        door_id="d-rec",
        expected_submission_id=intent_only_id,
    )
    # Row 2: `expected_submission_id=None` (`None` -> kept `RESERVED`, NOT deleted!)
    rec_fee_db._reserve(
        policy=pol,
        payment={"kind": "burn", "extrinsic_id": "9600100-2"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
        door_id="d-rec",
        expected_submission_id=None,
    )
    # Row 3: `is_admitted_fn` raises DB error (`None` -> kept `RESERVED`, NOT deleted!)
    rec_fee_db._reserve(
        policy=pol,
        payment={"kind": "burn", "extrinsic_id": "9600100-3"},
        hotkey=HOTKEY_1,
        receiver=RECEIVER_1,
        challenge_id="electric-motor-magnetics",
        challenge_version="1.9",
        known_finalized_head=9600105,
        door_id="d-rec",
        expected_submission_id="rtsk_" + "8" * 64,
    )
    rec_logs = []
    rec_res = rec_fee_db.recover_door_reservations(
        "d-rec",
        lambda sid: (
            False
            if sid == intent_only_id
            else (_ for _ in ()).throw(OSError("sqlite busy"))
        ),
        log_fn=lambda ev, **kw: rec_logs.append((ev, kw)),
    )
    assert rec_res == {"committed": 0, "released": 1, "unknown": 2}
    assert len(rec_logs) == 2

    # Post-admit `commit` failure maps to typed `503 fee_verifier_unavailable` & pins id (`C4`)!
    monkeypatch.setattr(
        rec_fee_db,
        "_commit_reservation",
        lambda *_a: (_ for _ in ()).throw(RuntimeError("wal disk error")),
    )
    with (
        pytest.raises(sf.FeeRefused) as commit_err,
        rec_fee_db.claim_for_admission(
            policy=pol,
            payment={"kind": "burn", "extrinsic_id": "9600100-4"},
            hotkey=HOTKEY_1,
            receiver=RECEIVER_1,
            challenge_id="electric-motor-magnetics",
            challenge_version="1.9",
            known_finalized_head=9600105,
            door_id="d-rec",
        ) as failing_commit,
    ):
        failing_commit("rtsk_" + "7" * 64)
    assert commit_err.value.status == 503
    assert commit_err.value.code == sf.FEE_VERIFIER_UNAVAILABLE
    assert rec_fee_db.settled_payment_for_submission(HOTKEY_1, "rtsk_" + "7" * 64) == (
        "BURN",
        "9600100-4",
    )

    # `C5`: Overlapping `LiveFeePolicySource` process lease refuses concurrent recovery!
    lease_dir = tmp_path / "lease_state"
    lease_pol_path = lease_dir / sf.POLICY_FILE_NAME
    sf.update_policy_row(
        path=lease_pol_path,
        scope="567:*",
        enabled=True,
        amount_rao=25_000_000,
        allow_testnet_without_terms=True,
    )
    fake_in_1 = SimpleNamespace(
        challenge=SimpleNamespace(challenge_id="c", version="1.0"),
        adapter=SimpleNamespace(ledger=SimpleNamespace(path=tmp_path / "same.db")),
        submission_fee=None,
        fee_ledger=None,
        fee_indexer=None,
    )
    src_1 = sf.LiveFeePolicySource(
        fake_in_1,
        challenge_id="c",
        version="1.0",
        expected_netuid=567,
        ledger_path=lease_dir / sf.ledger_file_name(567),
        path=lease_pol_path,
    )
    assert src_1.current().ready
    try:
        # Hold the OS flock in a child process to simulate a live sibling process!
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import sys, time; from pathlib import Path; "
                    f"sys.path.insert(0, {str(sf.REPO_ROOT)!r}); "
                    "from carbon.chain.fee_burns import exclusive_file_lock; "
                    f"p = next(Path({str(lease_dir)!r}).glob('.door-lease-*.lock')); "
                    "cm = exclusive_file_lock(p, blocking=False); cm.__enter__(); "
                    "print('HELD', flush=True); time.sleep(10)"
                ),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        # First release `src_1` so `holder` takes the OS flock, then start `src_2`!
        src_1.close()
        assert holder.stdout.readline().strip() == "HELD"
        fake_in_2 = SimpleNamespace(
            challenge=SimpleNamespace(challenge_id="c", version="1.0"),
            adapter=SimpleNamespace(ledger=SimpleNamespace(path=tmp_path / "same.db")),
            submission_fee=None,
            fee_ledger=None,
            fee_indexer=None,
        )
        src_2 = sf.LiveFeePolicySource(
            fake_in_2,
            challenge_id="c",
            version="1.0",
            expected_netuid=567,
            ledger_path=lease_dir / sf.ledger_file_name(567),
            path=lease_pol_path,
        )
        assert (
            not src_2.current().ready
        )  # Fails closed (`503`) while `holder` owns lease!
        src_2.close()
    finally:
        holder.terminate()
        holder.wait(timeout=3)

    # 5. `H3`: `kill_switch` clears bad-row `503`, `--clear-kill-switch` guard, `disable --force`
    # backup, cross-restart armed flag, `EACCES`, and `stats` non-creating check!
    h3_dir = tmp_path / "h3_state"
    h3_pol = h3_dir / sf.POLICY_FILE_NAME
    sf.update_policy_row(
        path=h3_pol,
        scope="116:electric-motor-magnetics 1.9",
        enabled=True,
        amount_rao=25_000_000,
    )
    # Deleting `h3_pol` while `fee_policy_armed.flag` exists fails closed even on a NEW watcher ("restart")!
    h3_pol.unlink()
    fresh_restart_watcher = sf.LiveFeePolicySource(
        SimpleNamespace(submission_fee=None, fee_ledger=None, fee_indexer=None),
        challenge_id="electric-motor-magnetics",
        version="1.9",
        expected_netuid=116,
        ledger_path=h3_dir / sf.ledger_file_name(116),
        path=h3_pol,
    )
    assert not fresh_restart_watcher.current().ready
    fresh_restart_watcher.close()

    # `kill_switch: true` overrides even a malformed row in `rows`!
    h3_pol.write_text(
        json.dumps(
            {
                "schema": sf.SCHEMA,
                "source": "test",
                "kill_switch": True,
                "rows": {"116:bad_row_key": {"broken": 1}},
            }
        ),
        encoding="utf-8",
    )
    assert (
        sf.for_door("electric-motor-magnetics", "1.9", expected_netuid=116, path=h3_pol)
        is None
    )
    # `disable --kill-switch --force` backs up the malformed rows file and clears `fee_policy_armed.flag`!
    repaired_doc = sf.disable_policy(path=h3_pol, kill_switch=True, force=True)
    assert "backed_up_corrupt_file" in repaired_doc
    assert repaired_doc["dropped_corrupt_rows"] == ["116:bad_row_key"]

    # `dial` refuses while `kill_switch` is True unless `--clear-kill-switch` is given!
    with pytest.raises(ValueError, match="kill_switch"):
        sf.update_policy_row(
            path=h3_pol,
            scope="116:electric-motor-magnetics 1.9",
            enabled=True,
            amount_rao=25_000_000,
        )
    sf.update_policy_row(
        path=h3_pol,
        scope="116:electric-motor-magnetics 1.9",
        enabled=True,
        amount_rao=25_000_000,
        clear_kill_switch=True,
    )

    # `EACCES` (`chmod 000`) on an unarmed file still fails closed (`503`), never reads as dark!
    if os.geteuid() != 0:
        eacces_dir = tmp_path / "eacces_state"
        eacces_dir.mkdir(mode=0o700)
        eacces_pol = eacces_dir / sf.POLICY_FILE_NAME
        eacces_pol.write_text("{}", encoding="utf-8")
        os.chmod(eacces_pol, 0)
        try:
            eacces_src = sf.LiveFeePolicySource(
                SimpleNamespace(submission_fee=None, fee_ledger=None, fee_indexer=None),
                challenge_id="electric-motor-magnetics",
                version="1.9",
                expected_netuid=116,
                ledger_path=eacces_dir / sf.ledger_file_name(116),
                path=eacces_pol,
            )
            assert not eacces_src.current().ready
            eacces_src.close()
        finally:
            os.chmod(eacces_pol, 0o600)

    # `stats` CLI refuses without creating an empty SQLite file!
    empty_stats_dir = tmp_path / "no_db_yet"
    empty_stats_dir.mkdir(mode=0o700)
    with pytest.raises(SystemExit):
        sf.main(["--state-dir", str(empty_stats_dir), "stats", "--netuid", "116"])
    assert not (empty_stats_dir / sf.ledger_file_name(116)).exists()

    # 6. `H13`: Real `RequestBuckets` with `burst=1` — `charge_preflight` leaves `group` token intact!
    rb = RequestBuckets(
        {
            "guard": {"rate_per_s": 10.0, "burst": 10},
            "group": {"rate_per_s": 0.01, "burst": 1},
            "chunks": {"rate_per_s": 10.0, "burst": 10},
        }
    )
    assert rb.charge_preflight("funder-1") is True
    assert rb.charge_group("funder-1", chunk=False) is True
    assert rb.charge_group("funder-1", chunk=False) is False

    # 7. Multi-process (`subprocess`) `FeeLedger` double-spend race + `0600` WAL sidecar check!
    mp_db = tmp_path / "mp_race.sqlite3"
    mp_ldg = sf.FeeLedger(
        mp_db, expected_netuid=116, expected_genesis_hash=FINNEY_GENESIS
    )
    mp_ldg.record_indexed_block(9600100, [_make_burn("9600100-9", idx=9)])
    worker_code = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(sf.REPO_ROOT)!r})",
            "from carbon.challenge_validator import submission_fee as sf",
            f"ldg = sf.FeeLedger({str(mp_db)!r}, expected_netuid=116, expected_genesis_hash={FINNEY_GENESIS!r})",
            "pol = sf.FeePolicy('tao-burn-v1', 25000000, 116, 9600000)",
            "try:",
            (
                "  with ldg.claim_for_admission(policy=pol, payment={'kind':'burn','extrinsic_id':'9600100-9'}, "
                f"hotkey={HOTKEY_1!r}, receiver={RECEIVER_1!r}, challenge_id='electric-motor-magnetics', "
                "challenge_version='1.9', known_finalized_head=9600105) as c:"
            ),
            "    c('rtsk_' + sys.argv[1] * 64)",
            "  print('ADMITTED')",
            "except sf.FeeRefused as e:",
            "  print(e.code)",
        ]
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", worker_code, str(i)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(6)
    ]
    mp_res = [p.communicate(timeout=15) for p in procs]
    mp_outs = [out.strip() for out, _err in mp_res]
    assert mp_outs.count("ADMITTED") == 1, mp_res
    assert mp_outs.count(sf.FEE_ALREADY_SPENT) == 5
    for suffix in ("", "-wal", "-shm"):
        sp = tmp_path / f"mp_race.sqlite3{suffix}"
        if sp.exists():
            assert stat.S_IMODE(sp.lstat().st_mode) == 0o600

    # 8. Client `B9` (>2 `fee_not_finalized`), `M1` (no auto re-burn on fresh burn),
    # `M2` (lost-202 retry at 0 extra TAO), `M3` (`record_path` before `note_spent`),
    # `N5` (malformed `facts["fee"]`), and REAL `FeePoster` + `submit_and_wait`!
    ctx = ChainContext("finney", "wss://chain.example", "finney", FINNEY_GENESIS, 116)
    kit = bundle_material_v5()["construction_kit"]
    recipe = ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": "sha256:" + "e" * 64},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
    )

    # `N5`: Non-dict `facts["fee"]` or bad `max_lookback_blocks` raises `DirectIntakeRefusal("fee_facts_invalid")`!
    for bad_facts in (
        {"fee": "not-a-dict"},
        {"fee": 123},
        {
            "fee": {
                "policy_version": "v1",
                "amount_rao": 25_000_000,
                "netuid": 116,
                "challenge_id": "synthetic-linear-field-2d",
                "min_block": 0,
                "max_lookback_blocks": "not-an-int",
                "preflight_tool": "construction_preflight",
            }
        },
    ):
        with pytest.raises(client.DirectIntakeRefusal) as nf_err:
            client._validate_fee_facts(
                bad_facts,
                ctx,
                SimpleNamespace(challenge_id="synthetic-linear-field-2d"),
            )
        assert nf_err.value.code == "fee_facts_invalid"

    kp_miner = Keypair.create_from_uri("//Charlie")

    class _DummyAuthSigner:
        def __init__(self, _s):
            pass

        def sign(self, _body, *, receiver, nonce_ns):
            assert receiver == RECEIVER_1 and nonce_ns > 0
            return {"x-bittensor-signature": "0x00"}

    monkeypatch.setattr(client, "BittensorMessageSigner", _DummyAuthSigner)

    fb_pol = fb.load_fee_burn_policy("finney")
    call_bytes, _, _ = fb.fee_burn_call(
        fb_pol,
        hotkey=kp_miner.ss58_address,
        receiver=RECEIVER_1,
        challenge_id="synthetic-linear-field-2d",
        amount_rao=25_000_000,
        limit_price_rao=None,
    )
    u_stub = {
        "era": {"period": 128, "current": 9600500},
        "nonce": 1,
        "spec_version": 497,
        "transaction_version": 1,
        "era_block_hash": "0x" + "cd" * 32,
    }
    ext_b, add_b = cm._extension_parts(fb_pol, u_stub)
    pre_b = call_bytes + ext_b + add_b
    pay_b = (
        hashlib.blake2b(pre_b, digest_size=32).digest() if len(pre_b) > 256 else pre_b
    )
    unsigned_dict = {
        "call_data": "0x" + call_bytes.hex(),
        "era": {"period": 128, "current": 9600500},
        "nonce": 1,
        "tip": 0,
        "genesis_hash": FINNEY_GENESIS,
        "era_block_hash": "0x" + "cd" * 32,
        "spec_version": 497,
        "transaction_version": 1,
        "metadata_hash": None,
        "included_in_extrinsic": "0x" + ext_b.hex(),
        "included_in_signed_data": "0x" + add_b.hex(),
    }

    burns_broadcast = []
    e2e_ledger = sf.FeeLedger(
        tmp_path / "e2e_door_fees.sqlite3",
        expected_netuid=116,
        expected_genesis_hash=FINNEY_GENESIS,
    )
    e2e_pol = sf.FeePolicy("tao-burn-v1", 25_000_000, 116, 9_600_000)

    class _RealPosterChain:
        def finalized_block(self):
            return 9_600_505

        def read_block_burns(self, block):
            return (
                (
                    _make_burn(
                        f"{block}-1",
                        block=block,
                        idx=1,
                        hotkey=kp_miner.ss58_address,
                        receiver=RECEIVER_1,
                        challenge_id="synthetic-linear-field-2d",
                    ),
                )
                if block == 9_600_501
                else ()
            )

        def read_burns_in_range(self, s, e):
            return {b: self.read_block_burns(b) for b in range(s, e + 1)}

        def prepare_and_estimate(self, **_kw):
            return (
                {"unsigned": unsigned_dict, "payload": pay_b.hex()},
                {"partial_fee_rao": 120_000, "deposit_rao": 0},
            )

        def broadcast(self, _prep, _sig):
            burns_broadcast.append(1)
            obs = _make_burn(
                "9600501-1",
                block=9_600_501,
                idx=1,
                hotkey=kp_miner.ss58_address,
                receiver=RECEIVER_1,
                challenge_id="synthetic-linear-field-2d",
            )
            e2e_ledger.record_indexed_block(9_600_501, [obs])
            return {
                "outcome": "FINALIZED",
                "block": 9_600_501,
                "extrinsic_id": "9600501-1",
            }

    real_poster = FeePoster(
        hotkey=kp_miner.ss58_address,
        receiver=RECEIVER_1,
        netuid=116,
        challenge_id="synthetic-linear-field-2d",
        chain=_RealPosterChain(),
        sign=lambda _req: {
            "signature": bytes(kp_miner.sign(pay_b)),
            "call": call_bytes,
            "tx_fee_ceiling_rao": 5_000_000,
            "remark_hash": fee_remark_hash(
                116, "synthetic-linear-field-2d", RECEIVER_1, kp_miner.ss58_address
            ),
        },
        state_dir=tmp_path / "miner_poster_dir",
        verify=lambda p, s, _hk: kp_miner.verify(p, s),
    )

    info_doc = {
        "schema": client.PUBLIC_SCHEMA,
        "network": ctx.network,
        "genesis": ctx.genesis_hash,
        "netuid": ctx.netuid,
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
        "receiver": RECEIVER_1,
        "snapshot": {"id": "snap-e2e"},
        "discovery_path": client.INFO_PATH,
        "path": client.SUBMIT_PATH,
        "tools": [client.SUBMIT_TOOL, client.STATUS_TOOL],
        "served_contracts": [{"level": 0, "digest": contract_s.digest}],
        "fee": e2e_pol.facts("synthetic-linear-field-2d", receiver=RECEIVER_1),
        "score_pack": None,
        "qualification": False,
        "reward": False,
    }
    pinned_ids = {
        "contract_digest": contract_s.digest,
        "rule_digest": "sha256:" + "b" * 64,
        "implementation_digest": "sha256:" + "c" * 64,
        "identities_digest": "sha256:" + "d" * 64,
    }
    target_sub_id = "rtsk_" + "f" * 64

    # `M1`: Freshly minted burn receiving `400 fee_burn_not_found` from a buggy validator MUST NOT burn a second time!
    def buggy_not_found_door(_u, body, _h):
        msg = json.loads(body)
        if msg["tool"] == "construction_preflight":
            return 200, sf.preflight_reply(
                policy=e2e_pol,
                ledger=e2e_ledger,
                challenge_id="synthetic-linear-field-2d",
                receiver=RECEIVER_1,
                hotkey=kp_miner.ss58_address,
                known_finalized_head=9_600_505,
                predicted_submission_id=target_sub_id,
            )
        return 400, {"refused": "fee_burn_not_found"}

    fclock = [100.0]
    with pytest.raises(client.DirectIntakeRefusal) as m1_err:
        client.submit_and_wait(
            "http://127.0.0.1:9080",
            "signer",
            root=tmp_path / "m1_camp",
            epoch=1,
            recipe=recipe,
            contract_digest=contract_s.digest,
            receiver=RECEIVER_1,
            context=ctx,
            read=lambda _u: info_doc,
            send=buggy_not_found_door,
            clock=lambda: fclock[0],
            sleep=lambda dt: fclock.__setitem__(0, fclock[0] + dt),
            fee_poster=real_poster,
            wait_s=0,
        )
    assert m1_err.value.code == "fee_burn_not_found"
    assert len(burns_broadcast) == 1  # Strictly 1 burn — NEVER burned twice (`M1`)!

    # `B9` (4 consecutive `409 fee_not_finalized` > `BUSY_RETRIES = 2`),
    # `M2` (lost-202 network drop after door commits burn, followed by stateless retry at 0 extra TAO!),
    # and `M3` (`note_spent` raising RuntimeError STILL writes `record_path`!):
    not_finalized_left = [4]
    drop_202_once = [True]

    def e2e_door(_u, body, _h):
        msg = json.loads(body)
        if msg["tool"] == "construction_preflight":
            return 200, sf.preflight_reply(
                policy=e2e_pol,
                ledger=e2e_ledger,
                challenge_id="synthetic-linear-field-2d",
                receiver=RECEIVER_1,
                hotkey=kp_miner.ss58_address,
                known_finalized_head=9_600_505,
                predicted_submission_id=target_sub_id,
            )
        if not_finalized_left[0] > 0:
            not_finalized_left[0] -= 1
            return 409, {"refused": "fee_not_finalized"}
        with e2e_ledger.claim_for_admission(
            policy=e2e_pol,
            payment={"kind": "burn", "extrinsic_id": msg["fields"]["fee_extrinsic"]},
            hotkey=kp_miner.ss58_address,
            receiver=RECEIVER_1,
            challenge_id="synthetic-linear-field-2d",
            challenge_version="1.3",
            known_finalized_head=9_600_505,
            door_id="e2e-door",
            expected_submission_id=target_sub_id,
        ) as commit_fn:
            commit_fn(target_sub_id)
        if drop_202_once[0]:
            drop_202_once[0] = False
            raise OSError("network dropped 202 response after door committed burn!")
        return 202, {
            "schema": client.RESULT_SCHEMA,
            "kind": "OUTCOME",
            "code": None,
            "pinned": pinned_ids,
            "outcome": {
                "schema": client.OUTCOME_SCHEMA,
                "submission_id": target_sub_id,
                "task_id": target_sub_id,
                "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
                "state": "ADMITTED",
                "evidence": contract_s.evidence_label,
                "qualification": False,
                "reward": False,
            },
            "evidence": "DEVELOPMENT",
            "qualification": False,
            "reward": False,
        }

    # Attempt 1: survives 4 x `409 fee_not_finalized` (`B9`), door commits `9600501-1`, then `202` drops!
    e2e_camp = tmp_path / "e2e_camp"
    with pytest.raises(OSError, match="dropped 202"):
        client.submit_and_wait(
            "http://127.0.0.1:9080",
            "signer",
            root=e2e_camp,
            epoch=1,
            recipe=recipe,
            contract_digest=contract_s.digest,
            receiver=RECEIVER_1,
            context=ctx,
            read=lambda _u: info_doc,
            send=e2e_door,
            clock=lambda: fclock[0],
            sleep=lambda dt: fclock.__setitem__(0, fclock[0] + dt),
            fee_poster=real_poster,
            wait_s=0,
        )
    assert len(burns_broadcast) == 1

    # Make `note_spent` raise to prove `M3` (`record_path` is already durably written first!)
    monkeypatch.setattr(
        real_poster,
        "note_spent",
        lambda _ext: (_ for _ in ()).throw(RuntimeError("note_spent boom")),
    )
    # Attempt 2 (lost-202 retry, `M2`): succeeds at 0 extra TAO (`len(burns_broadcast) == 1`)!
    with pytest.raises(client.DirectConstructionPending) as ok_pending:
        client.submit_and_wait(
            "http://127.0.0.1:9080",
            "signer",
            root=e2e_camp,
            epoch=1,
            recipe=recipe,
            contract_digest=contract_s.digest,
            receiver=RECEIVER_1,
            context=ctx,
            read=lambda _u: info_doc,
            send=e2e_door,
            clock=lambda: fclock[0],
            sleep=lambda dt: fclock.__setitem__(0, fclock[0] + dt),
            fee_poster=real_poster,
            wait_s=0,
        )
    assert ok_pending.value.task_id == target_sub_id
    assert len(burns_broadcast) == 1  # Zero extra burn across M1 + B9 + M2 + M3!
    rec_file = e2e_camp / "construction-intake-epoch-1.json"
    assert rec_file.is_file()
    assert stat.S_IMODE(rec_file.lstat().st_mode) == 0o600
    assert json.loads(rec_file.read_bytes())["submission_id"] == target_sub_id
    capsys.readouterr()
