# An admitted inbox row unknown to the validator store

PLT-35a, DEVELOPMENT engineering repair. The reported host outage is attributed
handoff evidence; this PR does not access the AX42 or claim service restoration.

The intake inbox and validator store are separate durable records. Previously,
`work_once` called `target.outcome` on every admitted inbox row before pending
work. An unknown submission raised `pool_store.StateError("unknown_submission")`
and aborted the entire pass. One orphan could therefore prevent later known
submissions and `run_pending` from being attempted.

The repair catches **only that typed code, only around outcome lookup**, inside
the existing writer scope. It increments `moved["orphaned"]`, logs a fixed
`worker_orphan_skipped` event with `code: unknown_submission, count: 1`, and
continues. Worker pass counts report the cumulative orphan count. `operate._pass`
forwards its operator stream to the inbox pass, so skipped conditions remain
visible even if later pending work fails. Neither event names an identifier,
recipe, hotkey, path or state object. Each skipped row remains ADMITTED unchanged;
the condition repeats until the Validator resolves it.

This does **not** delete, refuse, re-register, recover, score, settle, charge or
change the identity of an orphan. Recovery/loss/disposition of real submissions
remains the Carbon Validator's decision. No migration or new terminal state.
Other StateError codes, process errors and infrastructure failures propagate to
the existing infrastructure-retried pass handler. The score-capability guard and
writer/locking behaviour remain unchanged. The existing two run_pending call
sites in work_once/operator routing are retained, not opportunistically refactored.

## Safe diagnostic boundary

The handoff's literal raw-message/args request is DOCUMENTATION_LAG relative to
the existing privacy contract and sentinel tests. StateError combines its code
and detail in args/string; detail can contain cases, fingerprints, model IDs,
paths or other protected content. Raw str, repr, args and traceback are **not**
operator diagnostics added by this patch.

`pass_failed` still reports exception type and now adds argument **count** and a
closed diagnostic code. Only exact StateError types with `unknown_submission`,
`unknown_state` or `submission_replay_conflict` are allow-listed. The exact
KeyError argument `fingerprint` maps to `missing_fingerprint_key`; an arbitrary
fingerprint value is not logged. Everything else is `exception_details_withheld`.
A generic/subclass exception's spoofed .code or overridden args property is not
trusted. Missing StateError.code also stays withheld rather than crashing the
retry logger. No exception detail is echoed, even for a known typed code.

## Evidence and limits

```text
./scripts/dev/canonical.sh python -m pytest -q tests/cpu/test_validator_inbox_orphans.py tests/cpu/test_battery_intake.py tests/cpu/test_battery_validator_service.py
```

The discriminating control plants public synthetic ADMITTED rows before,
between and after known rows. It proves that known rows/pending work advance,
skips are counted/logged and the inbox remains unchanged. Non-orphan errors,
private content, spoofed properties/codes and later pending failures are negative
controls. These tests do not need the operator's keys, actual bank or host state.
On native Windows, an import-only fcntl stub refuses locking; tests explicitly
mock the writer and scoring capability. On canonical Linux, imports use actual
fcntl, but these focused fixtures still do not qualify real file locking or
deployment. Existing subsystem/service regressions cover their own declared scope.

Native diagnostics do not replace exact-head canonical acceptance. Engineering
merge, host deployment, recovery disposition and live-service checks remain
separate. No resumed scoring, security, scientific, LIVE or launch qualification
is claimed by this code or by green fixtures.
