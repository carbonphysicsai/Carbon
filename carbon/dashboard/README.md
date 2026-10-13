# Carbon Dashboard

A public, read-only display of the Carbon Validator's signed score feed (the
leaderboard), and a replay of Carbon's design optimizer driven by a model on a
public design task (the design showcase). Plan:
`docs/development/DASHBOARD_PLAN.md`. Ticket: DASHBOARD-01.

DEVELOPMENT / TESTNET display software. It holds no score, rank, frontier,
weight, settlement, qualification or production authority, and it never reads
hidden or live material.

## Build and preview

From a checkout. The build reads the brand assets and the public EV4 evidence
from the repository.

```bash
python -m carbon.dashboard build --fixtures --out /tmp/carbon-dashboard
python -m carbon.dashboard serve --dir /tmp/carbon-dashboard --port 8765
```

`--fixtures` draws signed synthetic feeds labelled FIXTURE, at the fixtures'
clock, so board.v2 shows each phase: LIVE, STALE, and PRE_FIRST_RELEASE after
a rule cutover.

## board.v2

LP-02/LP-03's optional `miner_status` block is carried by both the Python
builder and the Worker serving path. Each row contains only the public
hotkey, received/scored counts and refused counts by closed code; unknown or
unclassified code names become `other`. Absent/null stays absent, and an
empty block stays empty. Counts may precede a first released score and do
not create a score or standing. Malformed, duplicate or unsafe-integer rows
refuse the whole feed, preserving the Worker's existing last-good fallback.
Deployment of this serving change belongs to Launchpad.

`board_v2.project` reads only the verified board model `feed.py` returns.
- Every `null` has a reason at `reasons[<key>]` beside it. `not_in_feed` means
  the signed feed does not carry the field yet.
- An era is one rule digest; histories never cross digests.
- Rule statements (rule text, round period, release predicate and lag) show
  only when a rules card from the Validator matches the feed's rule digest
  (`rules.status` OK). No card is configured yet, so they are null with
  `rules_unavailable`.
- `phase` is STALE once the feed is more than 2 h old: an engineering UI
  default (`STALE_AFTER_SECONDS`), not a registered value. The age runs from
  the feed's `as_of_block` chain time when it carries one (`freshness.basis`).
- VALIDATOR-33 A's fields (#1143, DASHBOARD-02 S1b), each null with
  `not_in_feed` in an older feed:
  - the ledger king's UID, coldkey, crowning, share, next halving, defences
    (finals survived) and reward eligibility fill `king` only when the ledger
    king is the released incumbent (else `king_not_released`);
  - `history.handovers` and `history.kings` (each reign) from `handovers`;
  - `target_to_beat`: the rule's kind, the posted (final) and screening
    margins, the noise guard (the final comparison's `alpha`, `n_min`,
    `n_boot`, `important_min`; other keys dropped), the registered score and
    the gates, kept as the signed feed posts them. They are rule statements
    (Test Lead, #1144): the page draws the bars only with an OK rules card,
    and otherwise shows the king's score and gates and the one "Rules
    unavailable" line in the target panel;
  - `next_release.next_block` is the next rotation block, and `next_utc` its
    time estimated from `as_of_block` at 12 s per block.
- `worker/feed.mjs` ports it as `projectV2`; the Worker serves it at
  `/data/v2/<slug>.json`.

To build from a real feed, fetch it from a validator's public door, then build
it against that validator's pinned feed key:

```bash
python -m carbon.dashboard fetch --url https://<door>/carbon/v1/feed/<challenge> --out feed.json
python -m carbon.dashboard build --feed feed.json --trust-key <feed public key hex> --out site/
```

How the key and the feed are handled:
- Take the key from the validator's configuration, out of band. Never take it
  from the feed.
- A feed that fails any check is refused whole. The last accepted board stays,
  marked with the reason.
- `--no-showcase` skips the showcase replays (about 10 s).

## The pages (DASHBOARD-02 S2)

`web/` draws every Challenge page from `data/v2/<slug>.json` only: the king,
the target to beat with both bars, the eligible ladder (per coldkey when the
feed carries one), the history sparkline, the championship rounds, the next
round and release, and the safety gates. It computes no rank, king, margin or
rule value. A null field is not drawn: its reason stays in the board.v2 JSON,
and a section with one (king, target, timing, championship, network) shows a
single muted line, "More coming as the Validator publishes it". Rule text and
the release lag show only while the rules card's status is OK; otherwise one
"Rules unavailable" line stands where they would be. Before the first release
a board shows a hero state (the feed's rotation, labels, "What is scored" and
"How to mine"), never an empty table. The feed key shows as the pinned public
key's first and last bytes. `data/network.json` (S3's signed network snapshot)
is fetched only when `index.json` says `network: true`.

- Plain HTML, CSS and JS, mobile first; no framework, CDN or inline script or
  style, under the strict CSP. HTML, CSS, JS and the wordmark stay under
  120 KB (`tests/cpu/test_dashboard_web.py`).
- `tests/cpu/dashboard_check.cjs` renders every fixture board in each phase
  in Node and mounts it into a minimal DOM. A third argument, a site built from
  `fixtures.chain_documents()`, checks the #1143 fields: the king's share and
  halving countdown, the release countdown, the margins only with a rules
  card, and the handovers.

## What the build writes

| Path | Content |
|---|---|
| `data/index.json`, `data/boards/<slug>.json` | One board per Challenge and device class, checked by `feed.py` |
| `data/v2/<slug>.json` | The same board as `carbon.dashboard.board.v2` (`board_v2.py`, DASHBOARD-02 S1): king, target to beat, eligible leaderboard, history, rounds, gates and phase |
| `showcase/index.json`, `showcase/*.json` | Replays of EV4's public decision: the released incumbent's panel, when the feed carries one, and the synthetic controls |
| `index.html`, `*.js`, `style.css`, `fonts/`, `brand/` | The static app. No third-party script, no CDN, no cookies |

## Hosting: the `carbon-dashboard` Worker

The owner approved Cloudflare Workers hosting (2026-10-08). The Worker is in
`worker/` and its config is `wrangler.dashboard.toml`; it holds no account id,
token, feed URL or key.

- **Static app:** the Worker serves the built site.
- **Live leaderboard:** it computes `/data/index.json` and
  `/data/boards/*.json` from the live feeds, fetched server-side and checked
  against the pinned keys (Worker secrets).
  - `worker/feed.mjs` is a port of `feed.py`.
  - `tests/cpu/test_dashboard_worker.py` holds the two equal on every fixture
    and refusal case.
- **Fail closed:** a FIXTURE build is never served, and the fixture key is
  never trusted.

The owner's copy-paste setup is `docs/development/DASHBOARD_CLOUDFLARE_SETUP.md`.
The public deploy waits for the real feed (VALIDATOR-29).
