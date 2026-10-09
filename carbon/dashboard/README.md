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

`--fixtures` draws signed synthetic feeds labelled FIXTURE.

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

## What the build writes

| Path | Content |
|---|---|
| `data/index.json`, `data/boards/<slug>.json` | One board per Challenge and device class, checked by `feed.py` |
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
