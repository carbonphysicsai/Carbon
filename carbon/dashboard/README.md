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

## Hosting (owner decision; nothing is deployed)

The plan's §6 sets out the options:
- **Proposed:** Cloudflare Workers static assets on Carbon's existing account.
  The expected cost is USD 0, and the owner holds custody.
- **Alternative:** GitHub Pages.

Until the owner decides, the site runs only locally. No deploy credential is
kept in this repository.
