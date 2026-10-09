# f13 saved-integral check — Data Collection handoff

**F13-SAVED-INTEGRAL-CHECK-01 / DEVELOPMENT diagnostic.** Implements the
algebra proposed in [#929](https://github.com/carbonphysicsai/Carbon/pull/929)
at b4a8553ed0f7111cf4a876b2826518c9cf4545d1. No solver invocation, installation,
spend, input mutation or actual acquisition-output measurement by Codex.
KEEP the [buyer packet](f13-compressor-silencer.md). DC runs real public
DEVELOPMENT outputs; never supply hidden EVAL/STRESS, quiz/tuning or AX42 data.

## Run on retained material, not an extractor summary

Use Python 3.11+, stdlib only:

```sh
python scripts/dev/f13_saved_integral_check.py \
  --data /retained/case/ports.dat --names /retained/case/ports.dat.names \
  --deck /retained/case/deck.json --mapping /retained/case/operator-mapping.json
```

The CLI writes JSON to stdout, never rewrites the case. Retain stdout and exit
code in DC's return. Exit 0 means **both accounting definitions** meet the
packet criterion on every declared row; 1 means an accounting/integral finding;
2 means input is missing, malformed or incomplete. All outputs keep physical
reference status **UNRESOLVED**. A sparse deck can pass only its declared rows,
not a dense curve. DC must compare that declaration with its frozen run manifest.

DC supplies a sidecar with these exact keys (no automatic column-order guess):

```json
{
  "schema": "carbon.f13-saved-integral-input.v1",
  "scope": "PUBLIC_DEVELOPMENT",
  "sha256": {"data": "<64 lowercase hex>", "names": "<64 lowercase hex>", "deck": "<64 lowercase hex>"},
  "source": {
    "revision": "0f12834226f65cdb317e7407e1e83e68c135801b",
    "image_digest": "sha256:<actual run manifest digest>",
    "model": "EQUAL_PORT_PLANE_ROBIN_REAL_INCIDENT",
    "phasor": "exp(+i*omega*t)"
  },
  "area_basis": "OPERATOR_VERIFIED_EQUAL_PORT_AREAS_AND_BC_IDS",
  "columns": {
    "frequency": {"index": 1, "name": "<exact .names label>"},
    "in_real": {"index": 2, "name": "<exact .names label>"},
    "out_real": {"index": 3, "name": "<exact .names label>"},
    "in_imag": {"index": 4, "name": "<exact .names label>"},
    "out_imag": {"index": 5, "name": "<exact .names label>"},
    "in_abs2": {"index": 6, "name": "<exact .names label>"},
    "out_abs2": {"index": 7, "name": "<exact .names label>"}
  }
}
```

Indices above are **examples**, not the real output layout. Copy exact labels
and one-based indices from the retained names file; independently match each
variable and inlet/outlet BC to the deck and mesh. Duplicate labels are allowed
because SaveScalars can repeat labels; indices must be unique. Hashes bind
files, not correct column meaning. DC verifies equal port areas against mesh,
deck ideal pi*r² area, source amplitude and normals/BC IDs; if these differ,
stop and return INPUT_REQUIRED rather than asserting the sidecar basis.
The tool explicitly says those assertions were not independently verified.

Deck fields read: rho, c, port_area_m2, amplitude_pa, frequencies_hz. Extra
geometry fields are ignored, never executed. Complete, ordered, unique expected
frequencies must match all raw rows exactly; no filtering, redraw, deduplication
or dropping an unfavorable row. Each file is bounded to 4 MiB and 10,000 rows
(resource guards, not scientific limits). Missing integrals mean DATA_REQUIRED,
not permission for new solves. Record actual source/deck/image/file hashes;
the config image is not the run-manifest image identity.

## What the diagnostic checks

Let S be the verified equal port area, Z0=rho*c, A the real incident amplitude,
I the complex pressure boundary integral and H the pressure-square integral.

```
Pinc = A² S / (2 Z0)                     # calculated, not forced to 1 W
Pref_plane = |Iin/S - A|² S / (2 Z0)
Pout_plane = |Iout|² / (2 Z0 S)
Vin/out = (Hin/out - |Iin/out|²/S) / (2 Z0)
Pout_all = Hout / (2 Z0)
Pref_robin = (Hin - 2 A Re(Iin) + A² S) / (2 Z0)
r_old = Pinc - Pref_plane - Pout_all
r_robin = r_old - Vin = Pinc - Pref_robin - Pout_all
```

Both signed residuals are retained; **abs(r)/Pinc <= 0.01** is the existing
packet's power-balance criterion. The report includes every row, worst signed
residual/frequency (lowest frequency breaks ties), negative-variance findings,
normalization offset from unit power and algebraic identity error. No dB curve
is silently replaced. A negative H or variance beyond 64 machine epsilons of
its subtraction scale is an integral finding, not a candidate failure.
This allowance covers arithmetic only, not an invented quadrature tolerance.
Even smaller negative values are retained, not clamped.

If r_old is positive and approximately Vin while r_robin closes, the return
is MIXED_EXTRACTION_FINDING: it supports the mixed-definition hypothesis.
If r_robin remains outside 1%, return CLOSURE_FINDING. If either variance is
invalid, return INTEGRAL_FINDING, even when residuals happen to be small.
ACCOUNTING_CLOSURE means only the current saved-integral Robin accounting
closes. Neither Vin nor Vout is claimed to be propagating acoustic power for
evanescent modes. Modal radiation, velocity flux, exact product quadrature,
mesh/lead convergence and Tier 2 witnesses remain untested.

## Return to packets/Test Lead

Return the complete JSON, mapping and raw-file identities, declared vs frozen
frequency coverage, original extractor version, and a BC/area/source verification
note. Name the worst nominal frequency, its signed old/Robin residuals and both
variances; do not infer a signed result from the old unsigned 4.7% summary.
Keep the original sealed reference identity/results unchanged. DC owns any
extractor/package repair and proposed follow-up verification; this check grants
no new reference runs, qualified truth, candidate verdict or buyer feasibility.
