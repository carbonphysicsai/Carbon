## 2026-10-13 — VALUE-METRIC-V2-REGISTRATION-01: register the V2 rev-2 definition and the Challenge-neutral V2 bank spec, prospectively, with every value HUMAN_INPUT

**Authority.** The owner's directive of 2026-10-13: "Scoring alignment needs to be priority one along with a bank of challenges that are ready to go through the system." The Test Lead assigned Track A step 2 to the Carbon Validator (`shared/operator/PRIORITIES_2026-10-13.md`). Score design is the Carbon Validator's (gate and scoring design ownership). Adopting values, the scored population, payout and mainnet stay with the owner.

**Decision.**
- Register `docs/development/value-metric-v2/definition.v2.json`, canonical-JSON sha256 `sha256:0f0e28fbe10127580ada8dd58b3b0fa844a445a9472ee9996653d6596c16a6c0`, with its normative text `DEFINITION.md` and the bank contract `BANK_SPEC.md`.
- It is registered **before any V2 bank exists**, so the owner's values come from curves on a real bank against a fixed definition, and the sealed confirmation tests a pre-registered rule.

**What it fixes against the current metric** (RES-07 #1209, RES-08 #1218, RES-09 #1241):
- abstention scores 0, not near the top;
- value is verified gain over the buyer's fallback, minus the reference solves spent;
- safety stays a mandatory gate and a tie-break, never a price;
- the shortlist is the validator's;
- takeover uses an absolute Δ_min with a paired block test.

**Not decided here:**
- κ, k, u, the fallbacks, P_V2 acceptance, the rescue unit, Δ_min, α, the cheap-arm thresholds, the payout condition and mainnet. All are HUMAN_INPUT, set later by an owner record that binds this digest.
- The proof Challenge: Track A step 3.
- Any re-scoring. This changes no current rule, candidate or history. OWNER-BATTERY-SCORE-CANDIDATE-01 stays active.

**Reversibility.** Prospective and inert until an owner value record and a passed sealed confirmation exist. A revision is a new definition digest.

**Validation.** Documentation and JSON only, with no runtime change. Canonical document checks run, and the digest is recomputable with `json.dumps(sort_keys=True, separators=(",", ":"))`.
