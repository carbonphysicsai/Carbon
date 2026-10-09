# Carbon Dashboard on Cloudflare: owner setup sheet

**For:** the owner, who approved Cloudflare Workers hosting at USD 0
(2026-10-08, relayed by the Test Lead). DASHBOARD-01 D4. Plan: §6 of
`DASHBOARD_PLAN.md`.

**What gets deployed:**
- **The Worker:** `carbon-dashboard`, serving the static dashboard.
- **The leaderboard:** fetched live from the validator's signed feed. The
  Worker checks the feed's signature against the pinned key and caches it at
  the edge for 60 s.

**What stays out of the repository:** no account id, token, feed URL or feed
key. Each is read from a file under `~/.config/carbon/`.

**Wait before deploying publicly:**
- the real feed must be served: VALIDATOR-29, #854, merged and its door up;
- never deploy a fixture build. The Worker refuses to serve one anyway: every
  path answers 503.

Run everything from a current checkout of `main`, in Git Bash or a Linux
shell, at the repository root, with the repository's Python environment.

## 1. One-time setup

**Sign wrangler in.** Pick one way.

The first way is browser sign-in, which writes no token file:

```bash
npx wrangler@4 login
```

The second way is an API token read from a file. Create the token in the
Cloudflare dashboard: My Profile → API Tokens → "Edit Cloudflare Workers"
template, and add **Zone → DNS → Edit** for `carbonphysics.ai`. Save the token
and the account id as the two files below, then load them:

```bash
mkdir -p ~/.config/carbon && chmod 700 ~/.config/carbon
chmod 600 ~/.config/carbon/cloudflare-dashboard.token ~/.config/carbon/cloudflare-account-id
```

```bash
export CLOUDFLARE_API_TOKEN="$(cat ~/.config/carbon/cloudflare-dashboard.token)"
```

```bash
export CLOUDFLARE_ACCOUNT_ID="$(cat ~/.config/carbon/cloudflare-account-id)"
```

**Write the feed settings.** These are two one-line files. They are not
secret, but they stay out of the repository:
- `~/.config/carbon/dashboard-feed-urls`: comma-separated `https://` feed URLs,
  one per Challenge and device class, each
  `https://<validator door>/carbon/v1/feed/<challenge>`. The Carbon Validator
  session gives you the exact URLs.
- `~/.config/carbon/dashboard-feed-keys`: the validator's feed public key (64
  hex), from its configuration (`score_feed keygen` printed it). Several keys
  are comma-separated. Never take the key from the feed itself.

## 2. Build the site from the real feed

Fetch one feed and build against the pinned key. Repeat `--feed` for each
feed file.

```bash
python -m carbon.dashboard fetch --url "$(cut -d, -f1 ~/.config/carbon/dashboard-feed-urls)" --out ~/carbon-dashboard-feed.json
```

```bash
python -m carbon.dashboard build --feed ~/carbon-dashboard-feed.json --trust-key "$(cut -d, -f1 ~/.config/carbon/dashboard-feed-keys)" --out ~/carbon-dashboard-site
```

Every board line must print `ACCEPTED`. If one prints `REFUSED <code>`, stop
and send the code to the Carbon Validator session.

## 3. Deploy

```bash
npx wrangler@4 deploy --config carbon/dashboard/wrangler.dashboard.toml --assets ~/carbon-dashboard-site
```

Then give the Worker its feed settings as secrets. This takes effect at once.

```bash
python -c "import json,pathlib; h=pathlib.Path.home()/'.config/carbon'; print(json.dumps({'FEED_URLS': (h/'dashboard-feed-urls').read_text().strip(), 'FEED_KEYS': (h/'dashboard-feed-keys').read_text().strip()}))" > ~/.config/carbon/dashboard-secrets.json
```

```bash
npx wrangler@4 secret bulk ~/.config/carbon/dashboard-secrets.json --config carbon/dashboard/wrangler.dashboard.toml
```

## 4. The custom domain (one-time)

The config's route, `dashboard.carbonphysics.ai` with `custom_domain = true`,
makes the first deploy create the DNS record and certificate in the
`carbonphysics.ai` zone. That needs:
- the zone in the same Cloudflare account;
- no existing DNS record named `dashboard`.

For a different hostname, change the `pattern` line in
`carbon/dashboard/wrangler.dashboard.toml` through a PR before deploying.

## 5. Check it

```bash
curl -sI https://dashboard.carbonphysics.ai/
```

```bash
curl -s https://dashboard.carbonphysics.ai/data/index.json
```

Expect:
- `200` and a `content-security-policy` header;
- every board `"state": "ACCEPTED"` and `"fixture": false`.

A `503 Feed not configured` means step 3's secrets are not set yet.

## Afterwards

- **The leaderboard** updates by itself, within about 60 s of a new feed
  version.
- **The design showcase** is static. Repeat steps 2 and 3 (not the secrets)
  when the incumbent changes, so its replay shows the new incumbent's
  predictions.
- **Roll back:**

  ```bash
  npx wrangler@4 rollback --config carbon/dashboard/wrangler.dashboard.toml
  ```

- **Cost.** Static asset requests are free on the Workers Free plan. Requests
  for the live leaderboard data count toward the plan's daily free request
  allowance. Check Cloudflare's current limits. Going past them would need the
  paid plan, which is your spend decision.
