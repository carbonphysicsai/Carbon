# Battery testnet: executable host handoff (after M3)

**Authority:** OWNER-BATTERY-TESTNET-01 (OD-2 to OD-8) and -03.
**Status:** prepared. No paid step and no chain step has run in this track.
M4 and M7 are **not complete**. Each needs hardware or testnet observations
that only this handoff's operator can produce.

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
2. The truth image pulls by digest, and `python -c "import pybamm"` runs inside
   it.
3. Owner-only permissions (`0600` files, `0700` directories) on every path in
   §3. A group-readable file is refused by name.
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

| Secret | Location | Who holds it |
|---|---|---|
| Validator service key (OD-6) | `/srv/carbon/keys/battery-validator.key`, 32 raw bytes, `0600`. Create it with `signing.ServiceKey.create`. | Carbon operator |
| Owner/publisher wallet (UID 0, OD-4a) | the existing subnet-567 operator config's `wallet` / `publisher` entries on the authorized host | Owner |
| Miner hotkey (UID 1, OD-7) | the Launchpad runner profile's `miner_public` and `miner_password_file` | Owner/miner |
| RunPod API key | the operator's existing RunPod credential file on the authorized host | Owner |
| Model-provider key | the runner profile's `api_key_file` | Owner |

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

## 5. Transaction authority (OD-4a, OD-7): records needed before any chain write

The repository holds the decision text (OD-4a, OD-7), not executable values.
Nothing below is inferred from general testnet approval. Each field must be
supplied by the owner and recorded before any dispatch.

**OD-4a Phase A all-burn weights.** Each publication is one
`DevelopmentTransactionAuthorization`, with `max_dispatches` fixed at 1 in
code. Supply these per publication, or as a numbered series:

| Field | Needed from the owner |
|---|---|
| `authorization_id` | an id per publication |
| `authority_record_digest` | the digest of the owner's written approval record |
| `publisher_hotkey` | UID 0's hotkey (public SS58, which is not a secret) |
| `expected_runtime_spec` | from `development_testnet doctor --online` |
| `valid_from_block`, `valid_through_block` | **the block window** |
| number of publications in the window | **the transaction count** |
| fee cap | **the maximum fee (test TAO) per transaction.** `max_spend_tao` is 0 in code, so confirm fees are acceptable at 0 spend, or approve a cap as a code change. |
| expiry | **the date after which unused authorizations lapse** |

**OD-7 miner recipe-hash commitments.**
- **Missing before any commitment:**
  - hotkeys: UID 1 and any added hotkeys (their registration cost in test
    TAO);
  - count per day;
  - window (first and last block, or UTC dates);
  - fee cap;
  - expiry.
- Commitment posting is not implemented in code, and neither is the
  daemon's chain reader. Both are required before `require_commitment: true`.

Dispatch and reconciliation follow
`docs/development/CW1_DEVELOPMENT_TESTNET_TRANSACTION_PLAN.md`:
`python -m carbon.development_testnet doctor|status|run|resume`.

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
# solve references (inside the truth image) and ingest
uv run --locked python -m carbon.battery.operate solve --config $C --batch <fingerprint> \
  --records /srv/carbon/battery/validator/refs-<fingerprint>.jsonl --workers 6
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
