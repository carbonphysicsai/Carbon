# Stage A score-to-value analysis: development intake

**Scope:** Graphite's confirmed battery recipes, after Stage A records arrive.
This analyzer uses aggregate development summaries only. It opens no hidden
cases, references, predictions, Graphite operator records, or solver outputs.
Historical v2 exam scores stay historical; the v3 comparison is a prospective
calculation from V3-SCORE-INPUTS-01 reports on the same confirmed members.

## Intake

Give `python -m scripts.dev.battery.stage_a_alignment --input <manifest.json>`
one `carbon.battery.stage-a-alignment-input.v1` JSON file. The closed shape is:

```json
{
  "schema": "carbon.battery.stage-a-alignment-input.v1",
  "scope": "DEVELOPMENT_SUMMARY_ONLY",
  "context": {
    "challenge": "battery-fastcharge-ageing-development-v1",
    "level": 0,
    "decision_measure": "<registered development decision-loss measure>",
    "decision_panel_sha256": "sha256:<digest>",
    "v3_panel_sha256": "sha256:<V3-SCORE-INPUTS-01 panel digest>",
    "v3_registry_sha256": "sha256:<registry-v4 digest>"
  },
  "members": [
    {
      "member": "<opaque confirmed member label>",
      "recipe": "<opaque recipe label, common across seeds>",
      "recipe_digest": "sha256:<compiled recipe digest>",
      "seed": 17,
      "confirmation_sha256": "sha256:<confirmation receipt digest>",
      "practice": {
        "state": "SCORED",
        "score": 0.1,
        "panel_sha256": "sha256:<public practice panel digest>",
        "source_sha256": "sha256:<practice summary source digest>"
      },
      "exam": {
        "state": "SCORED",
        "score": 0.2,
        "eligible": true,
        "rule": "v2",
        "rule_sha256": "sha256:<v2 rule digest>",
        "pool_version": 1,
        "device_class": "<rebuild device class>",
        "source_sha256": "sha256:<operator aggregate source digest>"
      },
      "decision": {
        "state": "RESOLVED", "loss": 0.3,
        "source_sha256": "sha256:<development value source digest>"
      },
      "v3_report": {
        "path": "<development v3 report relative to manifest>",
        "sha256": "sha256:<report digest>"
      }
    }
  ]
}
```

Numbers above illustrate the schema and are **synthetic**, not Stage A
measurements. The summary producer must verify each value and source digest
against the corresponding Stage A record before writing this manifest;
this analyzer cannot authenticate a number merely because it appears in JSON.
V2 practice and exam scores are both lower-is-better. A non-scored state has
`score: null`; a scored but ineligible v2 exam may also have `score: null` and
is ranked below every eligible exam member. An unresolved or infrastructure-
failed decision has `loss: null`.
`v3_report` may be `null` until the separate public-development references
are registered and the V3-SCORE-INPUTS-01 collector has run.

The v3 report is read only beneath the manifest directory and checked against
its digest, member, seed, registered panel and registry identity. The input's
SHA-256 appears in the output. Distinct level, v2 rule, pool version, device
class, decision panel, or v3 panel means distinct cohorts. Missing v3 inputs
leave v3 `UNMEASURED` while a complete v2/value panel is reported `V2_ONLY`.
Missing v2 or value leaves the planned cohort `UNMEASURED`; no convenient
subset is silently called the answer. Scores are never compared across
cohorts. This matters because hidden pools and CPU/GPU rebuilds can differ.

For each measured cohort the report gives v2 and v3 Kendall tau-b/Spearman
rho against the same decision loss, recipe-cluster bootstrap bands and their
defined-draw counts, v3 accuracy/Q3/G-FEAS term correlations, each member's
log-score contributions and gate verdict, and pairwise divergent members.
The pairwise contribution columns describe the ranking, not a causal effect.
The practice/exam table lists every recipe and seed; its rank association is
withheld when practice panels differ or any exam member is ineligible.
Bootstrap bands are descriptive because Stage A recipes and shared decision
cases are not independent draws from a qualified population.

Use `--draws` and `--seed` to reproduce a report. No threshold, positive
alignment criterion, or scoring-rule change is chosen here. The Test Lead and
owner decide how to use the evidence. If the v3 development references have
not arrived, the report says `UNMEASURED` and names the affected members.

## One-page owner summary template

Copy the template below after the report exists. Keep one page per comparable
cohort; do not fill a missing metric with zero.

> **Stage A score/value check — <cohort identity and input SHA-256>**  
> Confirmed recipes / seeds: `<n recipes>/<n members>`; exam rule and pool:
> `<v2 rule digest>/<pool version>/<device class>`; development decision panel:
> `<measure>/<digest>`; v3 input panel: `<digest>`.
>
> **Alignment:** v2 exam τ-b `<value or UNMEASURED>` [descriptive 95% band
> `<band>`], ρ `<value>` [band `<band>`]. Prospective v3 τ-b `<value or
> UNMEASURED>` [band `<band>`], ρ `<value>` [band `<band>`]. Defined bootstrap
> draws: `<counts>`. Describe any cohort smaller than the planned panel.
>
> **What drove the ordering:** accuracy `a` τ/ρ `<...>`; Q3 `q` τ/ρ `<...>`;
> G-FEAS τ/ρ `<... or undefined>` and gate failures `<count>`. List divergent
> member labels and whether their accuracy, Q3, or gate contribution favored
> the inversion. These are associations, not causes.
>
> **Practice versus exam:** `<per-recipe table link or summary>`; association
> `<value or withheld because panels differ/ineligibility>`. Note which
> recipes looked strong in practice but weak on the exam.
>
> **Limits and owner decision:** `<missing inputs, seed count, shared cases,
> selection/exposure, device/pool comparability>`. Recommendation:
> `<HUMAN_INPUT: retain, study, or prospectively change the rule>`. No
> historical score is rewritten and no qualification follows from this page.
