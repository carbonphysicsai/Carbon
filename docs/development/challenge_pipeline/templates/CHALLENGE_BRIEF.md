# Challenge brief: <family id> <family name>

**Template, DRAFT until protocol lock** (Challenge Roadmap §02, Stage 1).
Graphite may draft it. It is a draft until the science owner accepts the
scope, which is recorded as the pipeline record's `scope` gate with the
decision or review that made it.

| Field | Value |
| --- | --- |
| Family | `<fid>`, from `carbon/challenge_pipeline/families.json` |
| Queue position at entry | rank, composite, solve-time source (estimate or measured) |
| Protocol version | the locked protocol this challenge runs under |
| Drafted by | Graphite session id, or a person |

## 1. The engineering decision

Who uses the result, and what they decide with it. Start from the family's
`cust` and `ev`. Name the consequence of error.

## 2. v1 scope

Restate the family's `first` scope, then the exact v1 choices:
- inputs, from `inputs`;
- predictions, from `preds`;
- exclusions: what v1 does not claim.

Any departure from the family brief is stated with its reason.

## 3. Prerequisites

- Each family in `needs`, its rank and stage.
- For each one ranked lower and still queued: pulled forward, or built
  inside this challenge, and why.

## 4. Reference route

The family's `ref` candidate. Name the solver and route only: exact
versions, bounds and thresholds are set in Design.

## 5. Prior work and reusable infrastructure

From the pipeline record's `prior_work`, plus anything else in the
repository this challenge reuses (KEEP, WRAP, REPAIR or REPLACE).

## 6. Missing infrastructure

What Design must build first (the family's `build`).

## 7. Expected cost and risks

The reference solve-time estimate and its basis (`est`), and the stop rules
most likely to apply.

## Scope acceptance

Left blank by the drafter. The science owner's acceptance is recorded in the
pipeline record's `scope` gate: `{by, on, ref}`.
