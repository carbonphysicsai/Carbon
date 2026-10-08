# Motor's hidden pool on the producer host (VALIDATOR-21)

**Authority:** OWNER-MOTOR-HIDDEN-POOL-01 and OWNER-DATA-MOTOR-01.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.

Carbon's producer draws, solves once and seals hidden motor screening
batches. Validators import them through the answer key and score recipes on
them with motor's existing exam, unchanged. This page covers the
motor-specific steps on the AX42. The battery steps
([HIDDEN_HOST_SETUP.md](HIDDEN_HOST_SETUP.md)) and the answer key
([ANSWER_KEY_OPERATIONS.md](ANSWER_KEY_OPERATIONS.md)) stay as they are.

## The rule (pinned in every commitment)

`motor_hidden.hidden_rule`, as `rule_digest`:
- motor's existing exam rule (gates, components, TRAIN scales), unchanged;
- the DEVELOPMENT population, uniform (Q = P);
- the solver image by digest;
- which reference outcomes end a case. Only `OK` is scored. A failed
  reference is counted and excluded, never charged to a candidate.
- the owner's values:
  - a fresh screening batch every **1080** finalized blocks;
  - **3** batches active at once;
  - **30** cases per batch;
  - **1** scored submission per hotkey per **360** blocks.

Motor serves screening batches only: it has no finals, so the producer
draws no finalist batch for it.

## Cost

About 18 core-minutes per case, so about 9 core-hours per batch. A tick
solves with 6 workers of 2 CPUs each, about 1.5 hours of wall time per batch,
one batch per 1080 blocks (about 3.6 hours).

## Steps, as root on the AX42

**1. Pull the solver image by digest.** Run this once, and again after any
change to the pin:

```bash
docker pull ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05
docker image inspect --format '{{index .RepoDigests 0}}' ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05
```

**2. The producer's motor deployment and custody.** These are owner-only and
separate from battery's root:

```bash
E=/var/lib/carbon-producer/etc
cat >$E/motor-producer.json <<'JSON'
{"schema": "carbon.motor.hidden-deployment.v1",
 "store": "/var/lib/carbon-producer/motor/store",
 "custody": "/var/lib/carbon-producer/motor/custody"}
JSON
chown carbon-producer:carbon-producer $E/motor-producer.json && chmod 600 $E/motor-producer.json
install -d -m 0700 -o carbon-producer -g carbon-producer /var/lib/carbon-producer/motor
P carbon.challenge_validator.motor_source init --deployment $E/motor-producer.json
```

It prints only `seed_pin`. **Send it back.**

**3. Add motor to the producer configuration** (`sources`). The approval is
pinned by the decision file's sha256 in the tagged checkout:

```bash
sha256sum /opt/carbon/.agent/decisions/2026-10-07-OWNER-MOTOR-HIDDEN-POOL-01.md
```

```json
"electric-motor-magnetics": {
  "deployment": "/var/lib/carbon-producer/etc/motor-producer.json",
  "approval": {
    "record": "OWNER-MOTOR-HIDDEN-POOL-01",
    "file": "2026-10-07-OWNER-MOTOR-HIDDEN-POOL-01.md",
    "sha256": "<the sha256 above>"
  }
}
```

The existing producer timer then rotates motor with battery. Each tick
draws, solves, seals, schedules and publishes the next slot's batch into
`producer/outbox/electric-motor-magnetics/`.

**4. Push the whole outbox.** The distribution host serves one subdirectory
per Challenge. In `/usr/local/bin/carbon-push`, set
`OUT=/var/lib/carbon-producer/producer/outbox`, the parent of the
per-Challenge directories. `--delete` still removes retired packages.

**5. Validators.**
- A validator deployment is `{"schema": "carbon.motor.hidden-deployment.v1", "store": DIR}`,
  owner-only.
- `answer_key sync` (fetch) or `answer_key import` (the same-host
  development pool) picks motor's adapter from that schema.
- `python -m carbon.challenge_validator.motor_hidden status --deployment FILE --block N`
  prints counts only.

## Refusals

| Code | Meaning |
|---|---|
| `producer_challenge_not_approved` | The approval is missing or its sha256 is wrong. |
| `producer_motor_no_custody` | The producer deployment names no `custody`. |
| `producer_confirmation_custody_*` | The custody is missing, not owner-only, or inside the repository. |
| `producer_published_case` | A draw repeated a published motor case. The role is not committed; report it. |
| `producer_role_reused` | A role was asked to draw a different batch. |
| `producer_reference_malformed` | A solver record is not for its own case's inputs, comes from another image, or has a malformed curve. |
| `answer_key_published_case` | A package holds a published case. It imports nothing. |

## Security notes for the dedicated review (AGENTS.md §13)

- The motor solve runs `run_batch.py`'s container as it always has: no
  network, `--cpus`, the producer's uid, and only the case directory
  mounted. It does not add battery's `--read-only`, `--cap-drop ALL` or
  `no-new-privileges`. Hardening it is a follow-up for that review.
- The producer account already runs Docker for battery's truth solves.
  Motor adds no new privilege.
