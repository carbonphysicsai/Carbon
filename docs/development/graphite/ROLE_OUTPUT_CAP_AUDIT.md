# PLT-22: current role caps versus public grant reservations

This is read-only DEVELOPMENT arithmetic, not a spending grant or evidence of
a provider/host run. Run through the canonical wrapper with the locked
science-jax, chain, archive and mcp groups:

```sh
CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/canonical.sh python -m scripts.dev.graphite_grant_cap_audit
```

The current public snapshot is
`docs/development/evidence/role-output-cap-audit/audit-v2.json`. Its basis is
main `e13f973a0da7b887bcbf28796ca895fc7e697451`: 34 public grant files, each
hashed, and 11 hashed selection/role/price/grant/budget source files. It uses
the real session selector and the phase-3/phase-4 budget calculators. It lists
every role/model's uncached maximum input and output reservation. Reasoning
tokens are included in the registered output cap and charged at that output
price. No current provider price or context is guessed from an outside source.

The original `audit-v1.json` remains byte-identical, with SHA256
`d799faa3d25b592e1109e62f63835e9e8945716f9d8cc24995051bb459584916`.
Its 33-grant basis is main `07314d0bde9138c55452aec06e5448816b2a7b63`.
Snapshot version 2 keeps the same data-format schema and records its source
revision and the superseded snapshot's path, hash and count. It prospectively
adds Constructor grant -6 and records the current registered -5 to -6
replacement. It does not reinterpret v1 or historical sessions. Grant -6's
owner-approved USD 14.94 ceiling, USD 14.91 run cap, USD 0.03 cleanup allowance,
one permitted run and 39,600-second runtime are read from its public file;
the registered USD 10.99 token share still fits four full Kimi reservations.

Before v2 merged, argument-event logging changed the pinned `provider.py`
source. This prospective refresh regenerates v2 at the newer main revision;
all 34 grant files, other ten source files and every cost/selection row retain
their prior values. The exact regeneration control stays unchanged.

## What changed at the larger cap

Kimi's Constructor/Attacker output cap is now 32,768. On the registered full
input window, a call reserves USD 2.3642112; the earlier 2,048 output cap
reserved USD 2.0646912. The output component is 16 times larger; the whole
call's increase is USD 0.29952 because its large input reservation also counts.
At the existing USD 10.99 token share, four full-price calls fit instead of
five. Cheaper actual replies may permit more, but the next call must always
reserve its entire maximum before transport. No cached-input discount or cheap
reply is assumed in the audit.

The grant's `worst_case_run_cost` remains an **enforced combined run cap**.
Model tokens and pods share that cap. New output settings do not authorize
more money, alter an owner-approved file, or promise the old number of turns.
The current v2 session rule has no per-role call cap: money and runtime bind.
Multiplying the retired 150-turn cap into a new grant would invent a run policy.
Closed planner/triage/Score Lab tasks still report their actual registered
maximum call count and whether all full reservations fit at each rung; their
money gate may stop a dearer rung before all of those calls.

## Coverage and named limitations

All 34 current files were examined: 28 mapped workloads, two replaced grants evaluated
as a current-settings scenario, three zero-spend admission grants, and one
unmapped historical grant. Planner-01 is deliberately not accepted by today's
`level_planner.PLANNER_GRANTS`; its old settings are not reconstructed or
reinterpreted. SPUR has no registered rates, so each of its six role profiles
is RATE_UNRECORDED, never a free successful audit.

The full Kimi call cannot fit these current token shares:

| Grants | Role | Token share USD | Full call USD |
|---|---|---:|---:|
| Phase3, Phase3-R2, Phase3-R3, Phase3-COOLING-CPU | Constructor | 1.95 | 2.3642112 |
| Phase4, Phase4-COOLING | Attacker | 1.93 | 2.3642112 |

These small shares also could not fit the old full Kimi reservation; the cap
change increases the shortfall. The audit does not turn inability to call the
highest rung into grant permission, nor claim the cheaper starting rung cannot
run. Current registered shares and grants stay unchanged. Restoring five full
Kimi calls or funding an unfit rung requires the spending owner's decision:
**HUMAN_INPUT**. No grant re-approval or execution occurred here.

## Test basis

The same synthetic USD 2.10 grant admits the old 2,048-token call and refuses
the current 32,768-token reservation before dispatch. The actual session,
selector and ledger execute; the refused case records zero model requests,
zero settled/pending spend and typed `run_cap_reached/provider_nanodollars`.
Deliberately advertising a USD 3.00 run cap for that same fixture grant makes
the refusal test fail because a request is dispatched; the guard can detect
the claimed defect.
Additional controls count/hash every public grant, reject empty inventories,
keep new unmapped workloads unknown and missing owner amounts unresolved.
The versioned snapshot control compares the entire current snapshot against
actual regeneration, including every file hash, source pin, selection and
replacement relation. An omitted grant or stale pin fails that equality;
the separate immutable v1 hash guards its historical interpretation.
Historical session records and recorded selections retain their original
meaning; the snapshot describes new-session settings only.
