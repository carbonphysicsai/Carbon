# C-CORE-20 delivery review: one real finding, and the checklist

External review of the C-CORE-20 implementation report. Most of it confirms work
already done. **Item 1 is a genuine gap I verified in the tree** and is the reason
this document exists.

Do not restart design work. Preserve the implementation under test.

---

## 1. Cancellation crosses lanes. Recovery says it does; cancel implies it does not

`miner_launch._cancel_path` is:

```python
Path(state_root) / CANCEL_DIRECTORY / f"{exact_token(execution_id)}.json"
```

**Keyed only by `execution_id`.** Neither lane nor schema appears in the path -
the schema only labels the content written inside. So
`validator_launch.request_cancel(state_root=X, execution_id=<a miner execution>)`
writes exactly the file a miner cancel would write, and a running miner launch
reads it and stops. The same holds in the other direction.

The two docstrings disagree about whether that is intended:

- `recover` states its lane-independence deliberately: *"Reclaiming a container
  that a launch still owns is a property of the host and its launch store, not of
  the lane the launch ran in."* Intent stated, and defensible - a leaked container
  is a leaked container.
- `request_cancel` says *"Ask a running **validator** launch to stop"*, implying a
  lane scope the path does not enforce.

**Decide which it is, then make the code and the test say the same thing.**

Either is defensible. Cancellation may be a host-operator property keyed by
execution id, deliberately lane-independent like recovery - in which case say so
in the docstring as recovery does, and test it. Or lanes must not cancel each
other - in which case the cancel path or its reader must carry the lane, and a
cross-lane cancel must be refused.

What is not acceptable is the current state: a docstring implying a boundary that
the filesystem layout does not have, with no test either way.

**The existing tests do not cover this.** There are four cancel/recover tests and
none is a cross-lane negative. `test_recover_shares_one_implementation_with_the_miner_path`
asserts `validator_launch._recover_launches is miner_launch.recover` - that
documents reuse, not isolation.

Add direct coverage: can a validator entry point cancel a miner execution, can a
miner entry point cancel a validator execution, and can one lane's recovery
reclaim the other lane's launch record. Assert the decided semantics, whichever
they are.

Confirm too that the optional schema argument added for reuse cannot choose a
role, convert work between lanes, or change a durable execution identity, and
that the miner regressions stay green unmodified.

## 2. Image injection - mostly covered, finish the set

Already covered in `test_validator_launch_orchestration.py`: the forbidden-field
set at line 232 is `("role", "lane", "backend", "official", "eligible", "image")`,
which is the anti-laundering set plus `image`, and line 292 covers `image_id`.

Add what is missing: `worker_image`, and an unknown additional field, each refused
by the closed schema **even when its value equals the legitimate installed
image**. Refusal must come from the schema being closed, not from a value
comparison.

Then prove the image-record path itself cannot be redirected by manifest content,
untrusted request content, a caller-supplied filesystem path, a symlink where
Carbon's private-file rules forbid one, or an environment variable unless an
existing trusted configuration contract owns it.

## 3. Attempt accounting - correct the wording

`/var/lib/carbon/accelerators` being absent does **not** establish that no
historical GPU work occurred. It establishes that the formal journal is absent.
C-CORE-19 did run GPU determinism work on the owner device under separate
authorization, and that must not be erased by a sentence about this ticket.

Report it in two parts:

> **0 formal journaled C-CORE accelerator attempts were consumed by C-CORE-20.**

and then, separately and explicitly, whether C-CORE-20 attached a device, created
a container, or incurred spend. If none did, say so in those words. Do not
retroactively describe earlier diagnostic GPU activity as journaled attempts, and
do not imply the device has never been used.

## 4. Two-host plan - close the circularity

The power condition stands and is the best thing in the plan. Four constraints to
add, one of which is a real soundness hole:

- **Circularity.** Any target scale for `delta` must be derived from previously
  retained same-device or public calibration evidence - **never from the two-host
  results being tested.** Choosing the separation after seeing the comparison
  rigs the study in either direction.
- **Protected material.** Select calibration strategies using public or synthetic
  DEVELOPMENT material only. **Never use hidden exam cases, seeds, traces or
  protected outputs to choose a near-margin pair.** Choosing a pair by its
  distance to a protected threshold is a leak of that threshold.
- **Controls.** Retain larger-margin controls beside the near-margin cases, and
  fix every pair and its pre-study `delta` before the comparison runs.
- **Language.** Compare underlying predictions and physical measurements, not only
  a development comparison outcome, and **do not imply a production rank or gate
  exists where Carbon has qualified none.**

The study must be able to return a result that blocks the execution class. Do not
run it under C-CORE-20.

## 5. The rest of the checklist, confirmed rather than new

Verify against the final tree before delivery rather than trusting the
implementation report:

- Role fixed as trusted logic, not caller-selectable; a manifest supplying a miner
  role fails.
- Durable queue identity authoritative; the manifest proves correspondence and
  constructs nothing. Refusal coverage retained for mismatched plan, profile,
  policy, recipe, seed, case, protected material and execution identity.
- **No generic backend selection added to `repeats.py`.** CPU stays CPU. Where
  trusted policy declares GPU and GPU cannot proceed, **fail truthfully** - never
  fall back to in-process CPU reconstruction.
- No change to `compare_r1`, backend qualification, thresholds, hard gates,
  tolerance policy, scoring or rank logic.
- Protected-material boundary negatives retained and extended.

## 6. Finish the run before changing anything

Let the running suite finish. Record the exact HEAD it tested, the exact command,
pass and fail counts, skips, duration, and whether the tree changed during the
run. **If HEAD or relevant source changed while it ran, that result is not final
acceptance** - re-run on the final tree. Do not kill a healthy suite to
reorganize commits.

Note that items 1 to 4 above will change source, so the currently running suite
cannot be the final acceptance for them.

## 7. Delivery

Branch `agent/core-platform-20-validator-orchestration` if not reserved. Main may
advance while the suite runs: fetch `origin/main`, inspect every advancement since
the C-CORE-20 base, integrate normally, resolve source-level Hub records, then
regenerate derived Hub output - **delay Hub regeneration until the runtime is
stable** to reduce cross-workstream churn. Retain every immutable event.

One coherent PR, truthful maturity language, exact-head CI, repair real failures
rather than weakening checks, no re-running already-green jobs without reason. No
force-push, no `--no-verify`, no history rewriting, no hardware experiment, no
MQ-008 activation.

Keep separate: #242, #246, #248, #251, #252.

## 8. Maturity, uncollapsed

SPECIFIED yes. IMPLEMENTED yes on delivery. TESTED within proven engineering
scope. HARDWARE_EXERCISED no. SCIENTIFICALLY_QUALIFIED no. SECURITY_QUALIFIED no.
PRODUCTION_QUALIFIED no.

> Validator GPU orchestration is implemented and engineering-tested; official
> backend qualification remains unresolved.

Do not say "GPU validator deployable."

**After normal C-CORE-20 delivery, stop.** Do not start the two-host experiment
or another accelerator ticket.
