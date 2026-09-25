# Battery testnet: executable host handoff (after M3)

**Authority:** OWNER-BATTERY-TESTNET-01 (OD-2 to OD-8) and -03.
**Status:** prepared. No paid step and no chain step has run in this track.
M4 and M7 are **not complete**. Each needs hardware or testnet observations
that only this handoff's operator can produce.

**Host readiness, as the operator observed it (2026-09-25).**

| Requirement | State |
|---|---|
| Publisher UID 0 (owns netuid 567) | Wallet present on the authorized WSL host. Ready. |
| Miner UID 1 | Registered, with its signing key at `0600`. The public miner metadata still says `registered: false`. Leave it unedited: the M7 preflight supersedes it with a fresh chain-bound record. |
| Validator identity | None, by OD-6. Correct. |
| Validator service key | Not yet created. Create it only from the accepted `main` commit. |
| Host | Ubuntu 24.04, cgroup v2, Docker 29.8.0, 20 CPUs, about 16 GiB. The C-03 worker passes the doctor. |
| Truth base image | Present by digest. The overlay is not yet materialized (§2.2). |
| Local GPU (RTX 3060, 6 GiB) | Preflight only. It is not M4 acceptance. |
| Model-provider key | Present at `0600`. |
| RunPod key | Placed by the owner at the §3 path (2026-09-25). Use it only for the §4 matrix. |
| Testnet read | Working. The chain is at runtime spec 471. |
| Testnet write | Blocked. The operator fails closed with `UNSUPPORTED_RUNTIME_VERSION` because it was validated for 460 (§5.1). |
| OD-4a executable record | Missing (§5.2). |
| OD-4b | Not authorized. |

This document never contains a secret. Keys, wallets and credentials are named
**by location only**. Never paste a token, key or password into a chat, a
ticket or a log.

## 1. Source and image identities

Recompute every identity on the host at the exact commit you run
(`operate status` prints the bound set). Values at M3 authoring:

| Identity | Value |
|---|---|
| Source | the M3 PR's merge commit on `main` (record the SHA you check out) |
| Battery contract digest | `sha256:4eec5824d3b8b1387ac53f26441685a95696be4ab85e552308198c387ea71b45` |
| OD-2 rule digest | `sha256:e108df6891aecd7c2111442267b182680cdb5516185bcaf188afead1c9c110c5` |
| TRAIN v1 | `3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3` |
| OCV table | `847cb3e92acaca7340072ca5c5bea8e4e6273b3bffea09378ba672e5f93372d7` |
| Frozen calibration (prepare.json) | `b23e3151d21eadd7fa63950ad41f6460d9fe21d75a345f825adcfa44182d5e99` |
| Battery implementation digest | printed by `operate status` (changes with battery code) |
| Truth image (CPU, PyBaMM) | `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940` plus overlay lock `scripts/dev/exam_design/locks/battery-overlay.lock.json` (`pybamm==26.8.0.0`) |
| Validator reconstruction image (CPU) | the accepted C-03 worker image named by the runner profile's `image_manifest`. It is checked by `verify_current_worker` and the host `doctor`. |
| Validator reconstruction image (GPU) | **to be pinned in M4.** The JAX GPU variant of the worker image. OD-3 security review applies before the testnet run. |

## 2. Host checks (stop on any failure)

1. Linux with cgroup v2, Docker and the carrier's `doctor`. The M3 container
   tests ran on cgroup v1 with a local image. That is not host acceptance.
   ```bash
   uv run --locked python -c "from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity as l; i=l('<image_manifest>'); print(doctor(image_id=i.image_id, image_identity=i))"
   ```
2. **Truth environment.** The base image alone does not import `pybamm`, so
   build the pinned overlay and verify it (`truth_env`):
   ```bash
   uv run --locked python -m carbon.battery.operate truth-materialize --target /srv/carbon/battery/truth-overlay
   uv run --locked python -m carbon.battery.operate truth-verify --target /srv/carbon/battery/truth-overlay
   ```
   - Materialize downloads the 27 locked wheels. It checks each wheel's size
     and SHA-256, and refuses any member that would leave the directory.
   - Verify runs the pinned image with no network and the overlay read-only.
     It requires `pybamm==26.8.0.0` and the lock's numpy and scipy.
   - The overlay was materialized and hash-checked in the development
     sandbox. Verification needs the image, so it runs on the host.
3. Owner-only permissions (`0600` files, `0700` directories) on every path in
   §3. A group-readable file is refused by name, and so is a shared work
   directory.
4. For M4: `nvidia-smi` in the GPU worker image, and JAX sees the device.

## 3. Non-secret configuration (schema and paths)

`/srv/carbon/battery/validator/deployment.json`, mode `0600`, schema
`carbon.battery.validator-deployment.v1`:

```json
{
  "schema": "carbon.battery.validator-deployment.v1",
  "state": "/srv/carbon/battery/validator/state.sqlite3",
  "private_root": "/srv/carbon/battery/validator/root.bin",
  "journal": "/srv/carbon/battery/validator/journal.jsonl",
  "work": "/srv/carbon/battery/validator/work",
  "backend": "carrier",
  "image_manifest": "/srv/carbon/images/worker-image.json",
  "seconds": 600,
  "require_commitment": false,
  "service_key": "/srv/carbon/keys/battery-validator.key"
}
```

- `require_commitment`: set it to `true` only once a chain commitment reader
  exists. Until then a `true` deployment refuses every submission as
  `commitment_reader_unavailable`, by design. `false` is recorded in every
  admission as `commitment: null`.
- The Launchpad runner profile adds the optional path
  `"battery_validator": "/srv/carbon/battery/validator/deployment.json"`.
- The private root and seed journal are created once:
  `seeds.PrivateRoot.create` and `SeedJournal.commit_root`, with the seed pin
  from the M2 seed service. **Back up the journal and state together.** The
  journal is append-only commitment evidence.

**Secret locations (reference only):**

| Secret | Location on the authorized host | Who holds it |
|---|---|---|
| Validator service key (OD-6) | `/srv/carbon/keys/battery-validator.key`, 32 raw bytes, `0600`. Create it with `signing.ServiceKey.create` from the accepted `main` commit. | Carbon operator |
| Publisher wallet (UID 0, OD-4a) | `/home/carbon/.bittensor/wallets/carbon-testnet-20260915` | Owner |
| Publisher wallet password | `/home/carbon/.local/share/carbon-testnet/secrets/wallet-password` | Owner |
| Miner UID 1 signing key (OD-7) | `/home/carbon/.local/share/carbon-testnet/secrets/miner-session-key` | Owner/miner |
| Model-provider key | `/home/carbon/.local/share/carbon-testnet/secrets/openai-api-key` | Owner |
| RunPod API key | `/home/carbon/.runpod/api_key` (`0600`, directory `0700`) | Owner |

Validators hold **no** hotkey (OD-6). Never copy a wallet into a
reconstruction container. Never register a replacement identity because a
sandbox lacks access.

## 4. Budget (OD-5): reconciliation, remaining ceiling, run matrix

**Reconciliation.**
- The exam-design campaign's RunPod ledger
  (`docs/development/evidence/exam-design-2026-09-24/accounting/ledger.jsonl`,
  2026-09-24 19:54 to 2026-09-25 06:00 UTC) records:
  - 13 pods;
  - 12 terminations, each verified;
  - about **USD 4.79** (pod-seconds × USD 0.49/h, plus a USD 0.011
    connectivity test).
- That campaign predates OWNER-BATTERY-TESTNET-01, which recorded OD-5 on
  2026-09-25. It is counted against the USD 20 track total *conservatively*
  until the owner says otherwise.
- M1 to M3 spent **USD 0** on RunPod and **USD 0** on the model provider. The
  agent tests use a scripted provider.

| Ceiling | Total | Spent (conservative) | Remaining |
|---|---|---|---|
| RunPod | 14.00 | 4.79 | **9.21** |
| Model provider | 6.00 | 0.00 | **6.00** |
| Track | 20.00 | 4.79 | **15.21** |

Before any paid step:
1. Re-read the account balance and the ledger.
2. Confirm the step's worst case fits the *remaining* ceiling.
3. Record the pod ID.
4. Verify termination afterwards.

Account credit is not spending authority. Do not restart the allowance per
milestone.

**Run matrix.** Rates use the recorded USD 0.49/h. Each pod adds a 0.25 h
cleanup reserve to its worst case.

| # | Step | Where | Expected | Worst case |
|---|---|---|---|---|
| R1 | Fresh private references: 4 screening + 1 finalist batch, about 590 solves at the recorded ~70 s mean, 6 workers | CPU (truth image). Run it on the operator host at no RunPod cost if it has 6 or more cores. | 2.0 h, USD 0.98 | 4.25 h, USD 2.08 |
| R2 | M4 determinism, host A: build/pull, doctor, rebuild KNN/MLP/DeepONet twice, infer 300 | 1 GPU pod | 0.5 h, USD 0.25 | 1.25 h, USD 0.61 |
| R3 | M4 cross-host reproducibility, host B: same as R2 | 1 GPU pod | 0.5 h, USD 0.25 | 1.25 h, USD 0.61 |
| R4 | M7 window: 2 validator instances | 2 GPU pods × 4 h | USD 3.92 | 2 × 5.25 h, USD 5.15 |
| **RunPod total** | | | **USD 5.40** | **USD 8.45** (fits 9.21) |
| A1 | One real autonomous-agent battery campaign: 2 epochs × at most 48 calls, reserved at USD 0.02048 each; ceilings `provider_attempts: 96`, `provider_nanodollars: 1966080000` | Model provider | about USD 0.3 | **USD 1.97** |
| A2 | Up to two further agent campaigns, same ceilings | Model provider | about USD 0.6 | USD 3.93 (A1 + A2 = 5.90, fits 6.00) |

Every pod is terminated at its deadline by the existing exam-design runner
pattern. R4 needs its own window approval (§5).

## 5. Transaction authority (OD-4a, OD-7): the exact sequence

The repository holds the decision text (OD-4a, OD-7), not executable values.
Nothing below is inferred from general testnet approval.

### 5.1 Runtime 471

The operator pins the runtime it validated (460). Carbon publishes through
`bittensor==11.1.0`, whose bindings name the calls and storage it encodes.
The read-only probe compares that exact surface with the live runtime:

```bash
uv run --locked --group chain python -m carbon.chain.runtime_probe \
  --config /absolute/private/operator/development-testnet.json > probe.json
```

- **`COMPATIBLE_USED_SURFACE`:** these are unchanged:
  - the weight calls (`set_mechanism_weights`,
    `commit_timelocked_mechanism_weights`);
  - the MEV-shield `submit_encrypted` call;
  - the 27 storage items, and `SubnetInfoRuntimeApi.get_metagraph`.

  The report lists the runtime's raw argument types, and its digest covers
  them. It does not prove runtime behaviour. After reading it (and the
  upstream release notes), the owner may set `expected_runtime_spec: 471`
  in the operator config.
- **`INCOMPATIBLE`:** stop. The SDK pin must move first, which is a code
  change.

### 5.2 OD-4a Phase A all-burn: one numbered record per publication

1. M3 accepted and deployed; M4 complete with the GPU image and evidence
   pinned.
2. Runtime probe compatible (§5.1), with the owner's decision on spec 471
   recorded.
3. `operate export` writes the signed `weight-intent.json`, which is ALL_BURN
   only.
4. Generate the exact request. This is read-only; no chain call is made and
   no wallet is opened:
   ```bash
   uv run --locked python -m carbon.battery.od4a request \
     --operator-config OP.json --probe probe.json \
     --intent EXPORT/weight-intent.json --sequence 1 \
     --start-after <blocks> --window <blocks> --expires-utc <UTC>
   ```
   The request binds these fields into `request_digest`:
   - `OD4A-BATTERY-0001`, the testnet genesis and netuid 567;
   - UID 0 and its public hotkey, and mechanism 0;
   - the row `[[0, 65535]]` and spec 471;
   - the probe digest and its finalized block;
   - the window and `max_dispatches: 1`;
   - `max_fee_tao: 0` and `max_spend_tao: 0`, refused at dispatch if any
     nonzero fee is observed;
   - the expiry and the signed intent's digest;
   - the exclusion of miner and winner rows;
   - the reconcile-never-resend and consumption rules.

   The window is the operator's proposal, and it is anchored to a fresh
   finalized block. Do not choose blocks days ahead.
5. **The owner approves that exact `request_digest`** in writing. The digest
   of that approval record is the fragment's `authority_record_digest`.
6. Paste the fragment into the operator config. Dispatch once through
   `python -m carbon.development_testnet run|resume`
   (`docs/development/CW1_DEVELOPMENT_TESTNET_TRANSACTION_PLAN.md`).
7. Reconcile to the finalized state. The record is then consumed.
8. Each further publication needs a new sequence number and its own
   approval. OD-4b stays disabled.

A positive fee cap would need an explicit owner value **and** a code change:
`max_spend_tao` is fixed at 0 in `DevelopmentTransactionAuthorization`.

### 5.3 OD-7 miner recipe-hash commitments

Commitment posting and the daemon's chain reader are not implemented.
Validators run with `require_commitment: false` until both exist, and until
the count per day, window, fee cap and expiry are recorded as their own
write scope.

## 6. Commands

```bash
C=/srv/carbon/battery/validator/deployment.json
# status / identities / pool / incumbent
uv run --locked python -m carbon.battery.operate status --config $C
uv run --locked python -m carbon.battery.operate batches --config $C
# resume after any crash (never dispatches work)
uv run --locked python -m carbon.battery.operate recover --config $C
# prepare private batches from the root (4 screening, 1 finalist)
for r in pscreen-T00 pscreen-T01 pscreen-T02 pscreen-T03; do
  uv run --locked python -m carbon.battery.operate prepare --config $C --role $r --kind screening
done
uv run --locked python -m carbon.battery.operate prepare --config $C --role pfinal-T00 --kind finalist --count 200
# references: export jobs (owner-only), solve in the truth container, ingest
mkdir -m 0700 -p /srv/carbon/battery/solve/<fp>
uv run --locked python -m carbon.battery.operate jobs --config $C --batch <fp> \
  --out /srv/carbon/battery/solve/<fp>/jobs.json
uv run --locked python -c "import shlex; from carbon.battery.truth_env import solve_command as c; print(shlex.join(c('/srv/carbon/battery/truth-overlay', '/srv/carbon/battery/solve/<fp>', repository='.', workers=6)))"
#   run the printed docker command: no network, read-only, sees only the
#   overlay, Carbon's source and that one directory
uv run --locked python -m carbon.battery.operate ingest --config $C --batch <fp> \
  --records /srv/carbon/battery/solve/<fp>/records.jsonl
# open the pool once three screening batches are complete
uv run --locked python -m carbon.battery.operate open --config $C
# advance queued submissions and finals
uv run --locked python -m carbon.battery.operate run --config $C
# export signed outcomes + Phase A all-burn intent for the owner publisher
uv run --locked python -m carbon.battery.operate export --config $C --out /srv/carbon/battery/export-<utc>
```

Cleanup:
- remove pods by recorded ID and verify termination;
- `docker ps -a --filter name=carbon-d4-` must be empty;
- keep `state.sqlite3` and `journal.jsonl`.

## 7. Expected evidence

- **M4:**
  - two-host rebuild and inference digests for each backbone;
  - the image digest and doctor report;
  - pod IDs with verified termination;
  - the spend recorded against §4.
- **M7:**
  - the daemon status over the window;
  - signed outcomes and signed all-burn intents;
  - publication receipts under the §5 records;
  - an agent campaign's plan, notes, tool results and stop reason;
  - a disclosure scan of every exported file.

## 8. Stop conditions

Stop and report when any of these occurs:
- any identity differs from §1, or `start` refuses `identities_changed`;
- the doctor fails;
- a paid step's worst case exceeds the remaining ceiling;
- a pod's termination cannot be verified;
- a chain write lacks its exact §5 record, or the record is exhausted or
  expired;
- the pool is `ROTATION_PENDING` with no prepared complete batch;
- any exported file contains a private case, input, label or seed;
- two attempts fail for the same infrastructure reason.
- the runtime probe reports `INCOMPATIBLE`, or the chain's spec differs from
  the one the owner adopted;
- `truth-verify` fails, or a solve refuses its environment;
- an OD-4a request's window has passed or its expiry is reached (generate a
  new numbered request; never stretch an approved one).
