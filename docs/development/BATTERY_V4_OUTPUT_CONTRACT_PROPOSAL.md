# Battery v4 output contract proposal (PLT-02)

DEVELOPMENT proposal; reviewed by Carbon Validator, adopted only by the owner.
No v4 Challenge is registered and no scorer, validator or miner path consumes it.

The executable plain-data contract is `carbon.battery.outputs_v4.CONTRACT`.
`outputs_v4.digest()` gives its prospective canonical JSON identity. Successful
records use `carbon.battery.reference-record.v4` and bind that identity.

| Output | Unit | Shape | Meaning |
| --- | --- | --- | --- |
| voltage_v | V | 121 | Existing first-hour voltage |
| temperature_c | degC | 121 | Existing first-hour cell temperature |
| plating_margin_v | V | scalar | Existing cycle-1 charge plating overpotential minimum |
| capacity_ah | Ah | 4 | Existing discharge capacities at cycles 1, 10, 20, 30 |
| current_a | A | 121 | PyBaMM Current [A]; positive discharge, negative charge |
| heat_w | W | 121 | PyBaMM Total heating [W]; signed, includes reversible heat |
| soc | dimensionless | 121 | Nominal-capacity coulomb-counting observable, defined below |

The common grid is 0, 30, …, 3600 seconds. No truncated reference is
extrapolated. Missing, non-finite or wrongly shaped quantities make the
reference export fail; they never become candidate failures or zero outputs.

SOC is `soc0 - (D(t) - D(0))/Q_nominal`, with D the solver's Discharge capacity
[A.h] and Q the published OKane2022 Nominal cell capacity [A.h], retained in
each record. It is not clipped. It is an explicitly proposed nominal charge
observable, not a qualified estimate of usable capacity or ageing-aware
electrochemical SOC. The proposed balance is
`soc(t)-soc0 = -integral(current_a dt)/(3600*Q_nominal)`.

Law limits and tolerances remain HUMAN_INPUT. B11's sign, units and SOC
interpretation need scientific review; sampled-grid quadrature has its own
reference residual and is not assumed exact. B12 needs the registered protocol
and cut-off interpretation. B13 needs the reference's thermal parameter
contract. B14 needs irreversible/reversible heat separately: total heat alone
cannot establish the sign of irreversible heat. This output proposal does
not implement or qualify those gates.

The default `truth_env.solve`/`solve_command` path remains v3. v4 is explicit:

```python
truth_env.solve_command(overlay, workdir, output_version="v4")
```

It runs the existing pinned offline container with `solve-v4`, reads
`jobs.v4.json` and appends to `records.v4.jsonl`. Jobs declare
`schema: carbon.battery.truth-jobs.v4`, `output_contract_digest`, `fingerprint`
and the existing list of `jobs`. The v4 file binds a sidecar
`records.v4.jsonl.output-contract.json`. A pre-existing v3/unversioned records
file is refused. v3 refuses v4 jobs, the v4 sidecar, and existing v4 record
lines even if that sidecar has been deleted. Resumed earlier lines retain
their exact bytes. Both routes retain typed reference/timeout/infra semantics
and the pinned solver-image/overlay/version provenance.

Re-pinned helper: `carbon/battery/truth_env.py` in the producer's exact helper
registry (`carbon/development_comparison/campaign_adapters/producer.py`).
The literal v3 golden test in `tests/cpu/test_battery_truth_v3_golden.py` is
the compatibility justification: it runs unchanged against the old helper
and this prospective helper, pinning the complete default command and the
serialized success/failure records, including provenance. v3 adds no record
schema. The producer still refuses any helper whose exact bytes mismatch
its registered digest; no pin check or failure is relaxed.

Pinned domain/recipe/training modules and implementation snapshots are
unchanged. Existing v3 records, output contracts and recipe digests stay as
history. Adoption of this prospective schema, downstream model retraining,
law contracts, scientific validity and LIVE registration remain separate work.
