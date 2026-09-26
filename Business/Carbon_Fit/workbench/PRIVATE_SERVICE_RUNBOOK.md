# Private Workbench service: start, check, stop, recover

This is the operator sequence for the internal connected Workbench: one command
composes the existing admitted research campaign, the registered public Julia
material, `WorkbenchScience`, the fixed scientific routes and the reviewed
private build. It replaces assembling those objects by hand.

It is an engineering composition. It qualifies no physics, grants no rights,
creates no campaign or grant, and activates no public customer collection.
Nothing here is a deployment; see **Not enabled here** at the end.

## 0. What you need before you start

| Input | Where it comes from | If it is missing |
|---|---|---|
| Admitted campaign + runner profile | The existing private Launchpad runner profile (`carbon.launchpad.runner-profile.v1`) and its grant file | The host refuses to start. No campaign is created here. |
| Pinned worker image manifest | The existing prepared campaign | `check` reports `numerical_worker_image: CONFIGURED_UNAVAILABLE` |
| Named staff token file | You write it once, privately (below) | The host refuses to start |
| Private draft registry path | Created by `register-draft` | Every scientific request is refused until a draft is installed |
| Private-science build directory | `tools/build.py --private-science` | The host refuses to serve an offline or polluted directory |

The scientific routes act as the single admitted campaign principal by
construction. A named staff token records **who opened the session**; it grants
no additional scientific, rights or economic authority to that person.

## 1. Fresh supported checkout

Linux (Ubuntu 24.04 or Ubuntu on WSL2). Source must live on a Linux-native
filesystem; a Windows-mounted path is refused by the repository bootstrap.

```bash
cd /path/to/Carbon
CARBON_UV_GROUPS="chain science-jax mcp" ./scripts/dev/bootstrap.sh
```

`chain` is required to open the existing miner hotkey, `mcp` supplies the HTTP
runtime, and `science-jax` supplies the numerical array reader. Node.js
**24.19.0** is required for the Workbench release checks, not for the service.

Build the private artifact into its own directory. Never overwrite the tracked
generated HTML, and never publish the private artifact:

```bash
.venv/bin/python Business/Carbon_Fit/workbench/tools/build.py \
  --private-science --output-directory "$PWD/.carbon-local/workbench-private"
```

## 2. Write the named staff token file once

Create it under a private, owner-only directory (`chmod 700` on the directory,
`chmod 600` on the file). It must be canonical JSON — sorted keys, no spaces,
no trailing newline — and it must name the campaign principal. That is the
`owner` recorded in the prepared campaign's `campaign-manifest.json`, the
identity the service authenticates as, **not** the `principal` in the runner
profile, which names the operator in the grant. The host refuses to start with
a file naming anyone else:

```bash
install -d -m 700 /private/carbon-workbench
python3 - <<'PY'
import json, secrets, hashlib, pathlib
tokens = {name: secrets.token_urlsafe(36) for name in
          ("Ryan Bequette", "Nick Fitzpatrick", "Harshdeep Sharma")}
document = {
    "schema": "carbon.workbench.host-principals.v1",
    "campaign_principal": "REPLACE_WITH_THE_ADMITTED_CAMPAIGN_PRINCIPAL",
    "staff": [{"name": n, "token_sha256": hashlib.sha256(t.encode()).hexdigest()}
              for n, t in tokens.items()],
}
path = pathlib.Path("/private/carbon-workbench/staff.json")
path.write_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
path.chmod(0o600)
for name, token in tokens.items():
    print(name, token)   # Hand each person their own token out of band, then clear this.
PY
```

Only the SHA-256 digest is stored. The host never logs, prints or returns a
token, and the capability report contains no token, path or principal.

## 3. Check before starting

`check` reads the already-verified profile and campaign manifest. It starts no
container, probes no accelerator, and prints no secret:

```bash
.venv/bin/python -m carbon.scientific_tasks.workbench_host check \
  --configuration /private/carbon-workbench/runner-profile.json \
  --draft-registry /private/carbon-workbench/drafts.json
```

Each capability is reported as exactly one of:

- `ENABLED` — registered in this campaign and its local inputs are present;
- `CONFIGURED_UNAVAILABLE` — registered, but a required local input is absent;
- `FIXTURE_ONLY` — available only as a local synthetic control, never live;
- `UNSUPPORTED` — not registered for this campaign, or the Workbench exposes no
  such route at all.

`reference_feasibility` needs the registered single-case Julia scope;
`operating_envelope` additionally needs the second registered envelope scope.
GPU and authored research are always `UNSUPPORTED` here: the Workbench adds no
solver of its own and substitutes no backend for another.

## 4. Register the reviewed draft

A browser cannot register a draft. Export the exact design scope from the
Workbench, then install it as an operator action:

```bash
cat > /tmp/draft.json <<'JSON'
{"job_id": "job-001", "design_id": "job-001-design-1", "revision": 1,
 "draft_scope": {"physics_family": "periodic_viscous_burgers_1d_v1",
                 "requested_goal": "Dynamics", "rights_scope": "SYNTHETIC_INTERNAL",
                 "inputs": "...", "outputs": "...", "units": "...",
                 "geometry": "...", "conditions": "...", "regime": "...",
                 "exclusions": "...", "query_workload": "...",
                 "reference_equation": "...", "reference_method": "..."}}
JSON

.venv/bin/python -m carbon.scientific_tasks.workbench_host register-draft \
  --configuration /private/carbon-workbench/runner-profile.json \
  --draft-registry /private/carbon-workbench/drafts.json \
  --draft /tmp/draft.json
```

The registry binds each revision to the exact granted public physical
definition. It stores the definition's digest, never a definition of its own, so
a registry written against a different grant fails closed instead of binding a
study to something the service would not accept.

Installing a new revision makes it current and leaves earlier revisions
installed but **stale**: a stale revision can still be cancelled for cleanup,
and it can no longer start, poll or claim a result. `revoke-draft` removes one
revision or a whole design and takes effect on the next request without a
restart.

## 5. Start

```bash
.venv/bin/python -m carbon.scientific_tasks.workbench_host serve \
  --configuration /private/carbon-workbench/runner-profile.json \
  --draft-registry /private/carbon-workbench/drafts.json \
  --principals /private/carbon-workbench/staff.json \
  --static "$PWD/.carbon-local/workbench-private" \
  --origin http://127.0.0.1:8770 --port 8770
```

**Open `http://127.0.0.1:8770/`.** That serves the private build's
`Carbon_Opportunity_Workbench.html`. Begin in **Owner Console**, open the job's
design view, then in the study panel enter your own staff access token and press
**Connect private service**. Adopt the allowed public source definition, run the
physical-definition check, then start a study.

The token is the one handed to you out of band in section 2. The page holds it
in memory for that browser tab only: it is never embedded in the build, written
to storage, placed in a URL, or included in an export or saved study file.
Reloading the tab clears it, and **Clear credential** removes it immediately.
Each staff member uses their own token, which records who opened the session;
the scientific routes still act as the single admitted campaign principal.

Plain HTTP is accepted only for a loopback origin. For any other host, pass the
exact `https://…` origin your reviewed TLS terminator serves and keep the
process bound to loopback behind it. The origin must match byte for byte.

Routes:

| Route | Auth | Purpose |
|---|---|---|
| `/api/scientific-studies/{capabilities,start,status,cancel,result}` | staff token | the existing fixed scientific routes, unchanged |
| `/api/workbench-host/health` | same-origin only | `SERVING` or `DRAINING` |
| `/api/workbench-host/capabilities` | staff token | the section 3 report, live |
| `/` and the three build artifacts | same-origin only | the private build |

The host status routes report composition state only. They contain no physical
definition, no result and no scientific value; those stay on the scientific
routes, behind `WorkbenchScience`.

## 6. Stop

Send `SIGINT` or `SIGTERM` (Ctrl-C). The process drains, `health` reports
`DRAINING`, and the campaign attachment then runs its existing reconciliation:
admitted workers are settled, the controller generation is released and the task
store is closed. The process then exits `0` and the campaign records
`INTERRUPTED`. Do not `SIGKILL` a host with a running study — that skips
reconciliation and leaves the campaign requiring recovery.

This sequence is exercised as processes, not described:
`tests/service/test_workbench_host_process.py` runs the build, `check`,
`register-draft` and `serve` as separate commands against a real Julia worker,
stops with `SIGTERM`, restarts, crashes the host with `SIGKILL` and starts it
again. A restart returns the saved study from the campaign's records and does no
new numerical work. Only the external hotkey and testnet runtime is substituted,
and the campaign is a test-owned synthetic one.

The whole team journey can be rehearsed the same way:
`tests/service/workbench_team_journey.py [--mobile]` starts this host and the
stage-1 receiver, then drives one browser session through them. It goes from the
client's preview, through the relayed inquiry, team assessment, registered draft
and real-worker study, to saving and reopening the workspace. It needs Node,
Playwright and a Chromium build (`NODE_PATH` pointing at `node_modules`).

A closed browser tab is not a stop. Controller and task ownership are held by
this process, not by the browser, so a disconnect, reload or laptop sleep leaves
a running study running and its result retrievable on reconnect.

## 7. Recover

| Symptom | What it means | Action |
|---|---|---|
| `check` reports `CONFIGURED_UNAVAILABLE` | a local input is missing | restore the named input; nothing is re-created for you |
| start fails with "unresolved consumption requires reconciliation" | a previous run ended without settling | attach cleanup-only (`carbon.miner_mcp.standard_cli --cleanup-only`) and let it observe worker cleanup before serving again |
| a study shows `REQUIRES_RECONCILIATION` | the task failed or was cancelled while capacity is still reserved or held | do not restart the study; reconcile the campaign first |
| a cancel stays pending | worker cleanup has not been observed yet | wait for the controller's observation; a browser acknowledgement is not cleanup |
| every scientific request is refused | no current registered draft for that job/design/revision | `list-drafts`, then `register-draft` the reviewed revision |
| the host refuses the static directory | it is an offline build, or it holds a file that is not a build artifact | rebuild with `--private-science` into an empty directory |
| the panel says to enter a staff access token | no credential is held in this tab | enter your token and connect; nothing is sent until you do |
| the panel reports a rejected staff credential | the token is not in the operator's principals file | confirm the token with the operator; a 401/403 is a credential problem, not a dead service |

Cancellation after expiry releases only capacity that was never claimed. Claimed
consumption of unknown size stays charged. A reconnect never creates another
allowance and never infers cleanup from a missing worker journal.

## 8. The private team receiver (separate process)

The private intake receiver is a separate local process and is **not** started
by the Workbench host:

```bash
CARBON_TEAM_USERS_FILE=/private/carbon-workbench/team-users.json \
CARBON_TEAM_INTAKE_STORE=/private/carbon-workbench/intake-store.json \
CARBON_TEAM_NOTIFY_DESTINATION=Hello@carbonphysics.ai \
node Business/Carbon_Fit/workbench/tools/team_intake_server.cjs
```

It listens on `127.0.0.1` only. An accepted inquiry is written and flushed to
disk before its receipt is returned, so a receipt always survives a restart or
power loss, and a storage failure returns no receipt at all. Team triage is
append-only: a correction adds a revision and retains the superseded assessment,
its author and who superseded it.

`CARBON_TEAM_NOTIFY_DESTINATION` records **where a notification would go**. It
is not a mailbox credential, a sender, or permission to contact anyone. This
process opens no outbound connection. `GET /private/outbox` lists queued events
and `POST /private/outbox/{id}/attempt` retries one; with no configured
transport the attempt is recorded as an observable failure and is never reported
as a delivery. A queued notification carries only the inquiry identity, its
canonical digest, the queue state, an authenticated record path and a minimal
count summary — no client words, contact details or reviewed package.

### External model processing (per-client switch, off by default)

Chutes is the one scheduled external model provider
(`data/client_model_provider_schedule.json`, model
`deepseek-ai/DeepSeek-V4-Flash-0731-TEE`). The receiver builds it only when all
three settings are present, and otherwise answers `501` to a model request:

```bash
CARBON_TEAM_MODEL_PROVIDER=chutes \
CARBON_TEAM_MODEL=deepseek-ai/DeepSeek-V4-Flash-0731-TEE \
CARBON_TEAM_MODEL_CREDENTIAL_FILE=/path/to/chutes.key \
```

The key is read from its file at send time. The file must be a regular file,
not a link, mode `0600`, and at most 1024 bytes.

The switch is per client and off by default:

- A data steward records the client's separately signed opt-in with
  `POST /private/intake/{id}/model-opt-in` and `{"provider","ref"}`, and
  withdraws it with `.../model-opt-in/withdraw` and `{"reason"}`.
- A reviewer then asks one question at a time with
  `POST /private/intake/{id}/model-assist` and `{"purpose","question"}`.
- Each request is an E5 release (`EXTERNAL_MODEL`), logged before it is sent.
  It carries the brief, the pilot and the open assumptions, never the contact
  details.
- Nothing sends automatically.

**A real client's record goes only with that client's own signed opt-in.** The
owner lifted the synthetic-only restriction on 26 September 2026. What still
applies:

- A synthetic opt-in reference is refused on any record that carries a real
  agreement or export-control reference.
- A real record is reachable only by staff screened under counsel's standard
  (E7, `CARBON_TEAM_SCREENING_STANDARD`). Under the synthetic development
  standard it stays unreachable, opt-in or not.

The live synthetic rehearsal is `tests/live_model_provider_rehearsal.cjs`.

Launchpad's miner research inference stays on Engy. It is a separate
provider, chosen for a different reason.

## 9. Required checks

```bash
./scripts/dev/canonical.sh bash scripts/dev/workbench_science_checks.sh
./scripts/dev/workbench_release_checks.sh
```

Run the release checks before any suite that regenerates artifacts in place.
These two are different scopes and neither is a browser journey:
`workbench_release_checks.sh` begins with the read-only freshness gate;
`workbench_science_checks.sh` does not run that gate and adds the
scientific-service, HTTP and host suites plus both builds.

### Browser suites

The browser suites are operator-run: neither check script nor CI invokes them.
They use Playwright's own bundled Chromium by default, so on a supported Linux
host with Playwright installed they need no configuration:

```bash
cd Business/Carbon_Fit/workbench
node tests/browser_smoke.cjs
node tests/browser_goal_smoke.cjs
node tests/browser_routing_smoke.cjs
node tests/browser_intake_smoke.cjs
node tests/browser_source_assessment_smoke.cjs
node tests/browser_team_review_smoke.cjs
node tests/browser_scientific_studies_smoke.cjs <private.html> <offline.html>
```

`CARBON_BROWSER_EXECUTABLE` selects a different Chromium-family binary,
`CARBON_SCIENCE_PYTHON` a different interpreter for the authoring bridge, and
`CARBON_MOBILE=1` runs a 390px viewport. If Chromium fails to start with a
missing `libnspr4`, `libnss3` or `libasound.so.2`, install those system
packages; the suites deliberately will not fall back to an HTML parser and
claim browser coverage they did not obtain.

This is Chromium at desktop and narrow widths. It is not Mobile Safari and not
hands-on assistive-technology acceptance; do not record it as either.

## Not enabled here

Public customer collection, a public host, DNS or route changes, a real sender
or mailbox, a signed privacy policy or retention decision, real customer
notifications, paid resources, and any deployment acceptance. Those need the
owner's separate authority and credentials and are not supplied by this runbook.
A working internal host is not a deployed product, and neither is a
scientific qualification: every study result remains `NOT_QUALIFIED`.
