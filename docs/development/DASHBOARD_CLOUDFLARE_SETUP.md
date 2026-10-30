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
key. Each is read from a file kept off the repository.

**Wait before deploying publicly:**
- the real feed must be served: VALIDATOR-29, #854, merged and its door up. At launch the four
  signed launch boards (section 7) are the feed; follow section 8;
- never deploy a fixture build. The Worker refuses to serve one anyway: every
  path answers 503.

Run everything from a current checkout of `main`, in Git Bash or a Linux
shell, at the repository root, with the repository's Python environment.

## 1. One-time setup

**Sign wrangler in.** Pick one way.

The first way is browser sign-in, which writes no token file:

```bash
npx wrangler@4.151.3 login
```

The second way is an API token read from a file. Create the token in the
Cloudflare dashboard: My Profile → API Tokens → "Edit Cloudflare Workers"
template, and add **Zone → DNS → Edit** for `carbonphysics.ai`. Save the token
and the account id as the two files below, then load them:

```bash
chmod 600 <token file> <account id file>
```

```bash
export CLOUDFLARE_API_TOKEN="$(cat <token file>)"
```

```bash
export CLOUDFLARE_ACCOUNT_ID="$(cat <account id file>)"
```

**Write the feed settings.** These are two one-line files. They are not
secret, but they stay out of the repository:
- The feed URLs file (`<urls>`): comma-separated `https://` feed URLs,
  one per Challenge and device class, each
  `https://<validator door>/carbon/v1/feed/<challenge>`. The Carbon Validator
  session gives you the exact URLs.
- The feed key file (`<keys>`): the validator's feed public key (64
  hex), from its configuration (`score_feed keygen` printed it). Several keys
  are comma-separated. Never take the key from the feed itself.

## 2. Build the site from the real feed

Fetch one feed and build against the pinned key. Repeat `--feed` for each
feed file.

```bash
python -m carbon.dashboard fetch --url "$(cut -d, -f1 <urls>)" --out ~/carbon-dashboard-feed.json
```

```bash
python -m carbon.dashboard build --feed ~/carbon-dashboard-feed.json --trust-key "$(cut -d, -f1 <keys>)" --out ~/carbon-dashboard-site
```

Every board line must print `ACCEPTED`. If one prints `REFUSED <code>`, stop
and send the code to the Carbon Validator session.

## 3. Deploy

```bash
npx wrangler@4.151.3 deploy --config carbon/dashboard/wrangler.dashboard.toml --assets ~/carbon-dashboard-site
```

Then give the Worker its feed settings as secrets. This takes effect at once.

```bash
python -c "import json,pathlib,sys; print(json.dumps({'FEED_URLS': pathlib.Path(sys.argv[1]).read_text().strip(), 'FEED_KEYS': pathlib.Path(sys.argv[2]).read_text().strip()}))" <urls> <keys> > <secrets json>
```

```bash
npx wrangler@4.151.3 secret bulk <secrets json> --config carbon/dashboard/wrangler.dashboard.toml
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

## 6. The network snapshot (optional, DASHBOARD-02 S3)

`/data/network.json` shows testnet 567's public state: each UID's hotkey,
incentive, emission, validator permit and stake. The validator host reads the
chain and signs a snapshot with its **feed key**, under the snapshot's own
signing domain, so the key the Worker pins (`FEED_KEYS`) does not change.
Until `SNAPSHOT_URLS` is set, the path answers `404`. A snapshot that fails a
check is listed as `REFUSED` with its reason and no data.

**On the validator host (the operator).** Write the builder's config as
a snapshot config file (`<snapshot config>`, mode 600). The chain block is the
validator's own chain context; `key` is the feed key file the feed build
already uses:

```json
{"schema": "carbon.validator.network-snapshot.config.v1",
 "chain": {"network": "testnet", "endpoint": "<validator chain endpoint>", "provider": "<provider>", "genesis_hash": "<testnet genesis>", "netuid": 567},
 "key": "<path to the feed key file>",
 "hotkey": "<validator hotkey SS58>"}
```

Run it on a timer, every 5 minutes, and upload the file next to the feed, the
same way and to the same bucket as the feed upload, as `valv2/network.json`:

```bash
python -m carbon.challenge_validator.network_snapshot build --config <snapshot config> --out <feed directory>/network.json
```

```bash
npx wrangler@4.151.3 r2 object put "<feed bucket>/valv2/network.json" --file <feed directory>/network.json --content-type application/json --remote
```

A systemd timer does it. Make the service `Type=oneshot` with those two
commands in order, and the timer `OnBootSec=1min` and `OnUnitActiveSec=5min`.
The build prints `{"block": …, "neurons": …}`, or `{"refused": "<code>"}` and
exit code 2. `snapshot_chain_unavailable` is an infrastructure failure: the
next run retries.

**On the Worker (the owner).** Save the snapshot's public URL,
`https://<public bucket host>/valv2/network.json`, as
a file (`<snapshot urls>`), then set it as a secret:

```bash
npx wrangler@4.151.3 secret put SNAPSHOT_URLS --config carbon/dashboard/wrangler.dashboard.toml < <snapshot urls>
```

A snapshot older than 30 minutes, by its block's chain timestamp, is refused
as `snapshot_stale`. The optional var `SNAPSHOT_MAX_AGE_SECONDS` changes that
bound, within 60 to 86400 seconds.

**Check it:**

```bash
curl -s https://dashboard.carbonphysics.ai/data/network.json
```

Expect every snapshot `"state": "ACCEPTED"` with labels `DEVELOPMENT` and
`TESTNET`. A `REFUSED` `snapshot_stale` means the timer stopped. Any other
code, send it to the Carbon Validator session.

## 7. The launch boards (OWNER-DASHBOARD-01; the Test Engineer's valV3 step 6)

The four launch Challenges are graded on the validator's own exams and have no score feed. Their
standing is one signed **launch board** each (`carbon.validator.launch-board.v1`, its own
signing domain): the king (exactly the receiver's `GET /carbon/v1/koth/<id>` answer), the
Ladder's best total per graded hotkey (rounded to the Ladder step), and counts. Nothing
finer. The same **feed key** signs it, so the key the Worker pins (`FEED_KEYS`) does not
change; this repository never reads that key.

**On the validator host (the operator).** Write
a launch-boards config file (`<launch boards config>`, mode 600, never committed):

```json
{"schema": "carbon.launch-board.operator.config.v1",
 "network": "testnet",
 "ledger": "<the receiver's attempt-ledger file>",
 "receiver_url": "http://127.0.0.1:<receiver port>",
 "key": "<the feed key file>",
 "out": "<feed directory>/launch",
 "upload_command": ["npx", "wrangler@4.151.3", "r2", "object", "put", "<feed bucket>/valv3/{name}",
                    "--file", "{file}", "--content-type", "application/json", "--remote"],
 "challenges": [
  {"id": "electric-motor-magnetics", "version": "1.5", "exam_version_label": "<label>"},
  {"id": "chip-cold-plate", "version": "1.6", "exam_version_label": "<label>"},
  {"id": "f08-ribbed-bracket", "version": "1.7", "exam_version_label": "<label>"},
  {"id": "f02", "version": "2.5", "exam_version_label": "<label>"}]}
```

`exam_version_label` is only used while the receiver publishes no king document yet.
The exam is the one of each Challenge's most recent graded result (a rotated bank moves
the board to a fresh ladder by itself); set `"exam_key"` on a Challenge to pin one.

Run it once, then on a timer:

```bash
python scripts/dev/launch_board_operator.py run --config <launch boards config>
```

```bash
python scripts/dev/launch_board_operator.py systemd --config <launch boards config>
```

The first command prints one row per Challenge: `UPLOADED` (or `WROTE` without an
`upload_command`), or `REFUSED` with a closed code and exit code 2. Before any result is
recorded every board is the empty state ("No hotkey has a graded result yet"); the next
run after the first grade shows it. `receiver_unavailable` leaves the last board in place
(the dashboard marks it STALE by its own age): restart the receiver and run again. The
second command prints a oneshot service and a 5-minute timer to install.

**On the Worker (the owner).** Add each board's public URL, `https://<public bucket
host>/valv3/<slug>.json` (slugs: `electric-motor-magnetics--no-class`,
`chip-cold-plate--no-class`, `f08-ribbed-bracket--no-class`, `f02--no-class`), to the
`FEED_URLS` list of step 1 and set it again as the secret. The Worker reads launch boards
as the static build does (`feed.mjs`, held equal to `launch.py` by
`tests/cpu/test_dashboard_launch_worker.py`).

**Check it:** `curl -s https://dashboard.carbonphysics.ai/data/index.json` lists each
launch board `"state": "ACCEPTED"` with labels `DEVELOPMENT` and `TESTNET`. A `REFUSED`
code names what the Worker's checks found; send it to the Carbon Validator session.

## 8. Launch day: repoint the live dashboard to the four launch boards

The launch versions are Motor 1.5 (`electric-motor-magnetics`), Cooling 1.6 (`chip-cold-plate`),
Ribbed Bracket 1.7 (`f08-ribbed-bracket`) and Burst Thermal 2.5 (`f02`). Section 7's example uses
them. The dashboard is already deployed and serving (`dashboard.carbonphysics.ai`, with `FEED_URLS` and
`FEED_KEYS` already set), so this is a repoint, not a first deploy. Run it after the receivers are
prepared and serving, in this order. Steps A to C are the Test Lead's, on the validator host; D is the
owner's, in Cloudflare.

**A. Read each exam's label (Test Lead).** The label is only a fallback while a receiver publishes
no king document, but the config needs one per Challenge. Take it from the receiver, not from
memory:

```bash
curl -s http://127.0.0.1:<receiver port>/carbon/v1/koth/electric-motor-magnetics
```

Repeat for `chip-cold-plate`, `f08-ribbed-bracket` and `f02`. If an answer is `404`, use the exam
exam version label for that Challenge. It must match
`[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}`. Do not invent one.

**B. Write `<launch boards config>` (Test Lead, mode 600, never committed).** Use
section 7's JSON with the four versions above: `network` is `testnet`; `ledger`, `receiver_url`,
`key` and `out` are this host's; `upload_command` names the feed bucket. Then:

```bash
chmod 600 <launch boards config>
```

```bash
python scripts/dev/launch_board_operator.py run --config <launch boards config>
```

Expect four rows, each `UPLOADED` (or `WROTE` with no `upload_command`). Before the first graded
result every board is the empty state ("No hotkey has a graded result yet"), which is correct.
Any `REFUSED <code>` (exit code 2): stop and send the code to the Carbon Validator session.
`receiver_unavailable` means the receiver is not up; start it and run again.

```bash
python scripts/dev/launch_board_operator.py systemd --config <launch boards config>
```

Install the printed oneshot service and 5-minute timer.

**C. Hand the owner two files (Test Lead).** Both stay off the repository, and the owner keeps them
somewhere private:
- the new feed URLs file: the four board URLs, comma-separated, each
  `https://<public bucket host>/valv3/<slug>.json`, with slugs
  `electric-motor-magnetics--no-class`, `chip-cold-plate--no-class`,
  `f08-ribbed-bracket--no-class`, `f02--no-class`;
- the feed key file: the validator's feed **public** key (64 hex), from the validator's own
  configuration (`score_feed keygen` printed it); never from a board. The launch boards are signed by
  the same feed key (section 7), so if `FEED_KEYS` already holds it, it does not change. If a different
  key signs them, the file lists both, comma-separated.

**D. The owner's steps in Cloudflare.** `<urls>` and `<keys>` are the two files the Test Lead hands
you. The domain, the DNS record and the Worker already exist: skip section 4. The Battery board is
removed: `FEED_URLS` ends up holding **only the four launch board URLs**.

0. **Which checkout.** Run steps 3 and 5 in a Git Bash checkout of the exact commit the Carbon
   team names for the launch Worker and page. That may be a reviewed branch carrying the Launchpad UX
   polish rather than `main`. Check out that commit, run `git rev-parse HEAD`, and send the printed
   sha back. Deploying reads the files in your checkout and uploads them to Cloudflare; it pushes
   nothing and changes nothing in `main`. Build the site (step 3) and deploy it (step 5) from the same
   checkout.
1. Sign in: `npx wrangler@4.151.3 login`.
2. **Keep the current `FEED_URLS` value** in a private file. A Worker secret cannot be read back.
   It is the way to roll back.
3. Build the page shell from the launch boards. This is needed, not optional: the shell now
   deployed was built from the Battery feed and still carries Battery's data files. Fetch the four
   boards and build against the pinned key:

```bash
mkdir -p ~/carbon-launch-feed && i=0 && for u in $(tr ',' ' ' < <urls>); do i=$((i+1)); python -m carbon.dashboard fetch --url "$u" --out ~/carbon-launch-feed/board$i.json; done
```

```bash
python -m carbon.dashboard build $(for f in ~/carbon-launch-feed/board*.json; do printf -- '--feed %s ' "$f"; done) --trust-key "$(cut -d, -f1 <keys>)" --out ~/carbon-dashboard-site
```

   Every board line must print `ACCEPTED`. A `REFUSED <code>`: stop and send the code to the Carbon
   Validator session.
4. Set the two Worker secrets, `FEED_URLS` (exactly the contents of `<urls>`: the four launch
   boards and nothing else; **do not add the Battery URL back**) and `FEED_KEYS` (the contents of
   `<keys>`; unchanged when the same feed key signs the launch boards). Put them in a JSON file kept
   off the repository, `{"FEED_URLS": "...", "FEED_KEYS": "..."}`, and load it:

```bash
npx wrangler@4.151.3 secret bulk <secrets json> --config carbon/dashboard/wrangler.dashboard.toml
```

5. Deploy the Worker and the site built in step 3, from the checkout of step 0. The route is
   unchanged:

```bash
npx wrangler@4.151.3 deploy --config carbon/dashboard/wrangler.dashboard.toml --assets ~/carbon-dashboard-site
```

6. Check it (section 5): `curl -s https://dashboard.carbonphysics.ai/data/index.json` lists
   exactly the four launch boards, each `"state": "ACCEPTED"` with labels `DEVELOPMENT` and
   `TESTNET`, and no Battery board. `curl -sI` the Battery board path
   (`/data/boards/battery-fastcharge-ageing-development-v1--cpu.json`) answers `404`. A board
   listed `REFUSED` carries a code: send it to the Carbon Validator session. A `503 Feed not
   configured` means step 4 is not done or the list is wrong.
7. **Roll back**, if the page looks wrong: set `FEED_URLS` back to the list you kept in step 2 and
   load it the same way; `npx wrangler@4.151.3 rollback --config carbon/dashboard/wrangler.dashboard.toml`
   returns the code and site to the previous deployment. Nothing else changed.

**Does the old Battery board stay cached?** The Worker keeps no copy of its own: it rebuilds the board
list from `FEED_URLS` on each request, and a feed it no longer lists is not shown. What can still
show it is a cache holding a response from before the change:
- Every `/data/` answer carries `Cache-Control: public, max-age=60`, so a browser or a cache in front
  may show the old list for up to 60 seconds.
- The Worker also asks Cloudflare to cache each feed fetch for `CACHE_SECONDS` (60) seconds. That
  only affects feeds still listed.
- To clear it: wait a minute, then reload the page with a hard refresh (Ctrl+Shift+R). If it still shows
  Battery, check `curl -s https://dashboard.carbonphysics.ai/data/index.json` first: if that answers
  without Battery, the page is the browser's cache. If it still lists Battery, `FEED_URLS` was not
  updated (step 4); in the Cloudflare dashboard you can also use Caching > Configuration > Purge
  Everything for `carbonphysics.ai` as a last step. The deployed site files cannot show Battery
  after step 5, because every `/data/` path the Worker does not serve answers `404`.

The first crown appears on the next 5-minute run after the first graded result. Nothing here is
done automatically or from this repository: the Cloudflare login, the secrets and any deploy are
the owner's.

## Afterwards

- **The leaderboard** updates by itself, within about 60 s of a new feed
  version.
- **The design showcase** is static. Repeat steps 2 and 3 (not the secrets)
  when the incumbent changes, so its replay shows the new incumbent's
  predictions.
- **Roll back:**

  ```bash
  npx wrangler@4.151.3 rollback --config carbon/dashboard/wrangler.dashboard.toml
  ```

- **Cost.** Static asset requests are free on the Workers Free plan. Requests
  for the live leaderboard data count toward the plan's daily free request
  allowance. Check Cloudflare's current limits. Going past them would need the
  paid plan, which is your spend decision.
