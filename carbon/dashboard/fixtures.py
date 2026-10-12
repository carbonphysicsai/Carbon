"""Synthetic, signed score feeds for building and testing the dashboard.

Until VALIDATOR-29 serves its feed, the dashboard runs on these. Every one is
labelled FIXTURE and DEVELOPMENT, names a made-up Challenge, and uses hotkeys
of the form `fixture-…`, which can never be valid SS58 addresses. The numbers
are made up. They are not results of any model, Challenge or exam.

The fixture key is derived from a public string, so anyone can sign a fixture:
that is the point. `feed.Trust` refuses this key for production, and a fixture
trust accepts nothing else.

The ranks, incumbent and challenger states here are invented to fill the
fixture. In a real feed they are the validator's, and the dashboard copies
them as given.
"""

from __future__ import annotations

import hashlib
import random

from carbon.dashboard import feed

_SEED = hashlib.sha256(b"carbon.dashboard.fixture-key.v1").digest()
PRECISION = 0.001
GATES = ("finite_outputs", "envelope", "g_feas")


def fixture_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(_SEED)


def fixture_public_key():
    from cryptography.hazmat.primitives import serialization

    return (
        fixture_key()
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


def fixture_trust():
    return feed.Trust(keys=frozenset({feed.FIXTURE_PUBLIC_KEY}), fixture=True)


def sign(document, key=None):
    """Sign with the fixture key (or the key given, for refusal tests)."""
    body = {k: v for k, v in document.items() if k != "signature"}
    signature = (key or fixture_key()).sign(feed.canonical_bytes(body))
    return {**body, "signature": signature.hex()}


def _round(value):
    return round(value, 3)


def _fingerprint(*parts):
    return "sha256:" + hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


SECTION_META = {
    "accuracy": {
        "display": "Accuracy",
        "unit": "fixture score",
        "sense": "lower_is_better",
    },
    "design_q": {"display": "Design q", "unit": "q", "sense": "higher_is_better"},
    "near_limit": {
        "display": "Near-limit accuracy",
        "unit": "fixture score",
        "sense": "lower_is_better",
    },
    "gates": {"display": "Safety gates", "unit": "PASS/FAIL", "sense": None},
}


def board_document(challenge_id, device_class, *, seed, miners=6, testnet=True):
    """One synthetic feed document in VALIDATOR-29's v1 shape, unsigned."""
    rng = random.Random(f"{challenge_id}|{device_class}|{seed}")
    base = 8_100_000
    windows = [_fingerprint(challenge_id, device_class, "window", i) for i in range(6)]
    submissions = []
    history = {}
    bests = {}
    for m in range(1, miners + 1):
        hotkey = f"fixture-miner-{m:02d}"
        error = rng.uniform(0.15, 0.6)
        for n in range(rng.randint(2, 5)):
            window_index = min(len(windows) - 1, n + rng.randint(0, 1))
            used = [windows[window_index]]
            receipt = base + 7_200 * window_index + rng.randint(100, 7_000)
            submission_id = f"fixture-sub-{m:02d}-{n}"
            error = max(0.03, error * rng.uniform(0.75, 1.05))
            eligible = rng.random() > 0.12
            sections = {
                "accuracy": _round(error),
                "design_q": _round(
                    min(0.99, max(0.05, 1 - error + rng.uniform(-0.1, 0.1)))
                ),
                "gates": {"eligible": "PASS" if eligible else "FAIL"},
                "near_limit": _round(error * rng.uniform(1.0, 1.6)),
            }
            if not eligible:
                sections["gates"]["g_feas"] = "FAIL"
            row = {
                "hotkey": hotkey,
                "submission_id": submission_id,
                "receipt_block": receipt,
                "windows": used,
                "state": "SCORED",
                "device_class": device_class,
                "sections": sections,
            }
            if n % 2 == 0:
                row["detail"] = {
                    used[0]: {
                        "cases": [
                            {
                                "case_id": f"fixture-case-{window_index}-{c:03d}",
                                "error": round(rng.uniform(0.002, 0.08), 4),
                            }
                            for c in range(8)
                        ]
                    }
                }
            submissions.append(row)
            history.setdefault(hotkey, []).append(
                {"receipt_block": receipt, "sections": sections}
            )
            if eligible and (
                hotkey not in bests or sections["accuracy"] < bests[hotkey][0]
            ):
                bests[hotkey] = (sections["accuracy"], receipt, submission_id)
    order = sorted(bests, key=lambda h: (bests[h][0], bests[h][1]))
    standing = [
        {
            "rank": rank,
            "hotkey": hotkey,
            "best": {"accuracy": bests[hotkey][0]},
            "best_at_block": bests[hotkey][1],
        }
        for rank, hotkey in enumerate(order, start=1)
    ]
    by_id = {s["submission_id"]: s for s in submissions}
    leader = order[0]
    states = ["FROZEN", "COMPLETE", "FROZEN"]
    return {
        "schema": feed.SCHEMA,
        "labels": ["DEVELOPMENT", *(["TESTNET"] if testnet else []), "FIXTURE"],
        "validator": {
            "hotkey": "fixture-validator",
            "feed_key": feed.FIXTURE_PUBLIC_KEY,
        },
        "challenge": {
            "id": challenge_id,
            "version": "0.0-fixture",
            "rule": "fixture-rule",
            "rule_digest": _fingerprint(challenge_id, "rule"),
        },
        "device_class": device_class,
        "sections": SECTION_META,
        "version": 3 + seed,
        "released_through_block": base + 7_200 * (len(windows) + 1),
        "generated_at": "2026-10-08T00:00:00Z",
        "values": {
            "registered": "FIXTURE-VALUES",
            "released": {"precision": PRECISION, "display_threshold": None},
            "live": None,
        },
        "release": {
            "predicate": "every case a window drew is retired and published",
            "retire_at": 5,
            "rotation_every_blocks": 7_200,
            "expected_lag_blocks": 36_000,
        },
        "released_windows": sorted(windows),
        "submissions": submissions,
        "leaderboard": {
            "incumbent": {
                "hotkey": leader,
                "submission_id": bests[leader][2],
                "since_block": bests[leader][1],
                "sections": by_id[bests[leader][2]]["sections"],
            },
            "challengers": [
                {
                    "hotkey": hotkey,
                    "submission_id": bests[hotkey][2],
                    "state": states[i % len(states)],
                }
                for i, hotkey in enumerate(order[1:4])
            ],
            "standing": standing,
            "history": history,
        },
        "excluded": {"canary_hotkeys": 1},
    }


# The validator's registered showcase task (VALIDATOR-29 showcase).
SHOWCASE_TASK = {
    "task_id": "ev4-charge-protocol-selection.v1:development",
    "contract": "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    "contract_sha256": "fc6f504f3ff69b3add10099056b7a652a28112d3ca1d63ada2fb194aac2d3e18",
    "split": "development",
    "data_scope": "PUBLIC_SYNTHETIC",
    "registered": "Test Lead, 2026-10-08 (VALIDATOR-29 showcase)",
    "incumbent": "LIVE",
    "label": "current incumbent, public cases",
}


def unavailable_panel(document):
    """A showcase panel for the fixture incumbent with no predictions. The
    fixtures never carry made-up model predictions on the public task."""
    incumbent = document["leaderboard"]["incumbent"]
    return {
        "schema": feed.SHOWCASE_SCHEMA,
        "label": SHOWCASE_TASK["label"],
        "task": SHOWCASE_TASK,
        "contract_digest": "sha256:fixture-not-predicted",
        "model": {
            "hotkey": incumbent["hotkey"],
            "submission_id": incumbent["submission_id"],
        },
        "state": "UNAVAILABLE",
        "code": "fixture_no_model",
    }


def documents():
    """The fixture set the local build draws: signed, two device classes."""
    return [
        sign(
            _with_panel(
                board_document("fixture-challenge-alpha", "gpu:FIXTURE-GPU", seed=1)
            )
        ),
        sign(board_document("fixture-challenge-alpha", "cpu", seed=2, testnet=False)),
        sign(board_document("fixture-challenge-beta", "gpu:FIXTURE-GPU", seed=3)),
    ]


def _with_panel(document):
    return {**document, "showcase": unavailable_panel(document)}


#: The fixtures' clock (2026-10-08T01:00:00Z), so a fixture build shows each
#: board.v2 phase whatever the day: the boards above are an hour old (LIVE).
FIXTURE_NOW = 1_791_421_200


def post_cutover_document():
    """A feed right after a rule cutover, unsigned: a new (v3) rule digest, a
    fresh state with no released window, submission, incumbent or history.
    board.v2 phase PRE_FIRST_RELEASE."""
    document = board_document("fixture-challenge-delta", "gpu:FIXTURE-GPU", seed=4)
    return {
        **document,
        "challenge": {
            **document["challenge"],
            "version": "0.1-fixture",
            "rule": "fixture-rule-v3",
            "rule_digest": _fingerprint("fixture-challenge-delta", "rule-v3"),
        },
        "version": 1,
        "generated_at": "2026-10-08T00:30:00Z",
        "released_through_block": None,
        "released_windows": [],
        "submissions": [],
        "leaderboard": {
            "incumbent": None,
            "challengers": [],
            "standing": [],
            "history": {},
        },
        "excluded": {"canary_hotkeys": 0},
    }


def stale_document():
    """A populated feed generated a day before FIXTURE_NOW, unsigned: board.v2
    phase STALE."""
    document = board_document("fixture-challenge-gamma", "cpu", seed=5)
    return {**document, "generated_at": "2026-10-07T01:00:00Z"}


def ladder_document(challenge_id, device_class, *, seed, sealed):
    """A LIVE feed with the proposed coldkey ladder (OWNER-BATTERY-
    CHAMPIONSHIP-03), unsigned. Two hotkeys share each made-up coldkey.
    `sealed`: every entry SEALED_UNTIL_GRAIN, as while the grain is
    HUMAN_INPUT; otherwise SHOWN, and NO_IMPROVEMENT_BEYOND_GRAIN for every
    second coldkey. The displayed scores and the grain are made up."""
    document = board_document(challenge_id, device_class, seed=seed)
    owners = {}
    for row in document["leaderboard"]["standing"]:
        number = int(row["hotkey"].rsplit("-", 1)[1])
        owners.setdefault(f"fixture-coldkey-{(number + 1) // 2:02d}", []).append(row)
    order = sorted(owners, key=lambda c: min(r["best"]["accuracy"] for r in owners[c]))
    rows = []
    for rank, coldkey in enumerate(order, start=1):
        top = min(owners[coldkey], key=lambda r: r["best"]["accuracy"])
        best = top["best"]["accuracy"]
        submission = next(
            s["submission_id"]
            for s in document["submissions"]
            if s["hotkey"] == top["hotkey"]
            and s["receipt_block"] == top["best_at_block"]
        )
        hotkeys = sorted(r["hotkey"] for r in owners[coldkey])
        if sealed:
            entry = {"status": "SEALED_UNTIL_GRAIN", "displayed_score": None}
        elif rank % 2 == 0:
            entry = {"status": "NO_IMPROVEMENT_BEYOND_GRAIN", "displayed_score": best}
        else:
            entry = {"status": "SHOWN", "displayed_score": best}
        rows.append(
            {
                "coldkey": coldkey,
                "rank": None if sealed else rank,
                "hotkeys": hotkeys,
                "best_submission_id": None if sealed else submission,
                "displayed_at_block": None if sealed else top["best_at_block"],
                **entry,
            }
        )
    ladder = {"grain_pct": None if sealed else 0.5, "coldkeys": rows}
    return {
        **document,
        "leaderboard": {**document["leaderboard"], "ladder": ladder},
    }


FIXTURE_HOUR_MS = 3_600_000


def chain_document(challenge_id, device_class, *, seed, released_king=True):
    """A LIVE feed with VALIDATOR-33 A's fields (#1143), unsigned: the chain
    time it was read at (10 min before FIXTURE_NOW), the next rotation block,
    a king from a made-up winner ledger with two handovers, and a target to
    beat. Every value is made up; the margins, share and noise guard are not
    any rule's. With `released_king` False, the ledger's king is a miner the
    leaderboard has not released as its incumbent yet, and is not paid."""
    document = board_document(challenge_id, device_class, seed=seed)
    incumbent = document["leaderboard"]["incumbent"]
    others = [
        r["hotkey"]
        for r in document["leaderboard"]["standing"]
        if r["hotkey"] != incumbent["hotkey"]
    ]
    now_ms = FIXTURE_NOW * 1000
    crowned = now_ms - 30 * FIXTURE_HOUR_MS
    block = document["released_through_block"] + 1_000
    king = incumbent["hotkey"] if released_king else others[0]
    first = others[1] if released_king else incumbent["hotkey"]
    return {
        **document,
        "as_of_block": {
            "number": block,
            "hash": "0x" + hashlib.sha256(challenge_id.encode()).hexdigest(),
            "timestamp_ms": now_ms - 600_000,
        },
        "release": {**document["release"], "next_rotation_block": block + 350},
        "king": {
            "hotkey": king,
            "uid": 7,
            "coldkey": "fixture-coldkey-07",
            "submission_id": incumbent["submission_id"] if released_king else None,
            "crowned_utc_ms": crowned,
            "eligible": released_king,
            "reason": "fixture-final" if released_king else "fixture-not-paid",
            "share_now": 0.5 if released_king else 0.0,
            "next_halving_utc_ms": (
                crowned + 48 * FIXTURE_HOUR_MS if released_king else None
            ),
            "challenges_survived": 2,
        },
        "handovers": [
            {
                "utc_ms": crowned - 72 * FIXTURE_HOUR_MS,
                "to_hotkey": first,
                "from_hotkey": None,
                "kind": "FIRST",
                "eligible": True,
                "reason": "fixture-first",
            },
            {
                "utc_ms": crowned,
                "to_hotkey": king,
                "from_hotkey": first,
                "kind": "FINAL",
                "eligible": released_king,
                "reason": "fixture-final" if released_king else "fixture-not-paid",
            },
        ],
        "target_to_beat": {
            "kind": "registered_score_margin_then_final",
            "screening_margin_rel": 0.04,
            "final_margin_rel": 0.05,
            "final_comparison": {
                "n_min": 20,
                "n_boot": 1000,
                "alpha": 0.1,
                "important_min": 5,
                # Not a noise guard parameter: dropped.
                "bootstrap_seed": 12345,
            },
            "score": {
                "candidate": "FIXTURE-SCORE>@0.1",
                "registry_sha256": hashlib.sha256(b"fixture-registry").hexdigest(),
                "decision": "FIXTURE-DECISION-01",
            },
            "gates": ["eligibility", "registered_score_gate", "important_region"],
        },
    }


def chain_documents():
    """Signed fixtures with VALIDATOR-33 A's fields: a released, paid king,
    and a ledger king the leaderboard has not released yet. The default
    fixture set carries none of these fields, as feeds before #1143."""
    return [
        sign(chain_document("fixture-challenge-eta", "gpu:FIXTURE-GPU", seed=8)),
        sign(
            chain_document(
                "fixture-challenge-theta", "cpu", seed=9, released_king=False
            )
        ),
    ]


def phase_documents():
    """Signed fixtures for the board.v2 states the documents() set lacks:
    PRE_FIRST_RELEASE after a cutover, STALE, and the coldkey ladder with
    each status (SHOWN and NO_IMPROVEMENT_BEYOND_GRAIN; SEALED_UNTIL_GRAIN)."""
    return [
        sign(post_cutover_document()),
        sign(stale_document()),
        sign(
            ladder_document(
                "fixture-challenge-epsilon", "gpu:FIXTURE-GPU", seed=6, sealed=False
            )
        ),
        sign(ladder_document("fixture-challenge-zeta", "cpu", seed=7, sealed=True)),
    ]
