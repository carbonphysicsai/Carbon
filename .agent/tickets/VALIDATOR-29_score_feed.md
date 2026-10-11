# VALIDATOR-29: the validator score feed (items 2–5; schema published early)

**Status:** PLANNED, schema DRAFT v1 for the dashboard team. Code follows in
slices.

**Authority:**
- the owner, 2026-10-08, relayed by the Test Lead: "approve dashboard plan.
  we have to have an awesome dashboard with leaders and their scores";
- OWNER-BATTERY-3B-AND-EXPOSURE-01: rule v2's disclosure is SEALED.

**Not here: item 1** (live per-section scores on unretired windows). That
reverses the SEALED term. It needs its own owner record, confirmed directly
with the owner, with its leak bound stated, before any code. The schema
reserves `live` for it, and it is always absent until then.

## What may be shown, and when (the release predicate)

Nothing computed from a hidden window is shown before that window is
**released**. A window is released when **every case it drew** is retired
and published in the training pool:
- the bank's `reveal_window` / `publish`;
- a non-bank batch's retirement and publication.

Under the bank, a case retires after E draws, so a window ends before all its
cases retire. **A window that has ended is not yet released.** A submission's
scores are released when **every window its score used** is released. Until
then, the submission appears in no feed field: no row, no count, no rank.

Public before release, as today:
- the on-chain weights;
- the submission's own receipt (accepted / queued);
- the sealed outcome, which carries no score.

## The feed

`GET /carbon/v1/feed/<challenge>` on each validator's public door. The same
document is written to the validator's state, signed, one version per
release event.

```json
{
  "schema": "carbon.validator.score-feed.v1",
  "labels": ["DEVELOPMENT", "TESTNET"],
  "validator": {"hotkey": "<ss58>", "feed_key": "<ed25519 public hex>"},
  "challenge": {"id": "<id>", "version": "<v>", "rule": "<rule name>", "rule_digest": "sha256:…"},
  "device_class": "cpu | gpu:<kind>",
  "version": 17,
  "released_through_block": 8182080,
  "values": {"precision": {"<section>": 0.01}, "display_threshold": {"<section>": 0.01}, "registered": "<record id>"},
  "released_windows": [{"fingerprint": "sha256:…", "slot": 7572, "released_at_block": 8190000}],
  "submissions": [
    {
      "hotkey": "<ss58>",
      "submission_id": "<public id>",
      "receipt_block": 8178428,
      "windows": ["sha256:…"],
      "state": "SCORED | INVALID_CONSTRUCTION | RECONSTRUCTION_FAILED | VOID",
      "sections": {
        "accuracy": 0.42,
        "design_q": 0.87,
        "gates": {"<gate id>": "PASS | FAIL"},
        "near_limit": 0.91
      },
      "detail": {"<window fingerprint>": {"cases": [{"case_id": "…", "error": 0.013}]}}
    }
  ],
  "leaderboard": {
    "incumbent": {"hotkey": "<ss58>", "since_block": 8180000, "sections": {}},
    "challengers": [{"hotkey": "<ss58>", "state": "NOMINATED | FINAL_PENDING | FINAL_LOST | FINAL_WON"}],
    "standing": [{"rank": 1, "hotkey": "<ss58>", "best": {"accuracy": 0.40}, "best_at_block": 8179000}],
    "history": {"<hotkey>": [{"receipt_block": 8178428, "sections": {"accuracy": 0.42}}]}
  },
  "excluded": {"canary_hotkeys": 1},
  "signature": "<ed25519 hex over the canonical document without this field>"
}
```

**Schema notes (v1, with the dashboard session's requests):**
- **Signed bytes:** `b"carbon.validator.score-feed.v1\0"` followed by the
  feed without `signature`, as `json.dumps(sort_keys=True, separators=(",", ":"),
  allow_nan=False, ensure_ascii=True)` encoded UTF-8.
- **The feed key is pinned out of band:** the dashboard verifies against its
  configured key, and the in-document `feed_key` is informational.
- **`sections`:** each section's display name, unit and sense
  (`lower_is_better` for battery's scores, `higher_is_better` for design q).
- **`generated_at`:** UTC. It sits outside the versioned body, so it never
  forces a new version.
- **Released values** are rounded to 3 decimals (precision 0.001), and
  `values.live` is null.
- **v1 emits no `detail`** (per-case breakdown). When it is added, its keys
  are released-window fingerprints only, and its per-case fields are
  registered first.

**Rules:**
- **Rounded** to `values.precision` per section. A displayed best (`standing.best`)
  moves only when a released score improves on it by more than
  `display_threshold`: the Ladder rule. The raw value never appears.
- **`detail`** (item 2) carries per-case values of **released** windows only.
  The cases are already public in the training pool.
- **Canary hotkeys** (OWNER-CANARY-LIST-01) never appear. Only their count
  does.
- **Labels:** `DEVELOPMENT` always, and `TESTNET` on testnet. A dashboard
  shows them on every view.
- **Signed** by the validator's feed key (an ed25519 key made like the
  producer key; its public half is in the feed and in the validator's
  configuration). Each release event increments `version`; earlier versions
  are kept.
- **Device class:** a feed is one Challenge and one device class.
  `require_one_class` holds: CPU and GPU scores are never ranked together.

## The values (registered; conservative until the study tunes them)

The Test Lead registers these. Proposed starting values:
- `precision`: 0.01 on every section;
- `display_threshold`: 0.01 on accuracy and design_q.

The submission-rate study's revealed arm (D1, pending the owner) tunes them.
Until registered, the feed refuses to publish (`feed_values_unregistered`):
fail closed.

## Slices

1. **The release predicate and records** (pool store): which windows are
   released, from the bank's and producer's publication records that the
   validator imports with each sync (the public training listing). Then a
   submission's sections, assembled from its score, `design_report` and quiz
   report, all of them already stored.
2. **The feed document:** rounding, the Ladder best, the leaderboard (incumbent,
   challenger states, standing, history), canary exclusion, the feed key,
   signing and versioning.
3. **Serving:** `GET /carbon/v1/feed/<challenge>` on the hardened listener
   (OWNER-DOOR-HARDENING-ACCEPT-01), read-only, signed bytes only.
4. **Item 1 (live)**, only after its owner record.
