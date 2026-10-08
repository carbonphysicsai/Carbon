## 2026-10-08 — VALUE-COST-T3-EXPOSURE-01: conditional cross-window power

**Authority.** The owner's VALUE_COST_ANALYSIS.md Part T3 direction requests
detection probability over k questions per batch and multiple windows within
exposure E. Merged VALIDATOR-23 design-bank code defines E per question:
`BankLedger.draw_window` samples distinct live cases in a window, increments
each selected case once, and retires that case at its own E.

**Engineering decision.** The DEVELOPMENT power harness simulates sequential
uniform draws from the finite sealed case bank, without replacement within
each window and with each question's registered remaining exposures. It keeps
all appearances from the same solved reference bank in one sign-test cluster.
If any simulated path cannot fill a complete window, the detection estimate
for that k/window cell is null and the feasible-path rate is reported.

**Reporting boundary.** This curve is conditional on the provided sealed
bank. It is separate from P and Q law reports. It is not a future-batch
probability and does not simulate producer top-ups or overlapping active
windows. Those cases need their own registered model and solved material.
Alpha, target power, k, E, control severities, and scientific interpretation
remain owner/Test Lead inputs. No result qualifies power, score use, or LIVE.

**Reason.** Treating E as one global draw cap would falsely refuse k=8,
E=5 even when eight distinct questions can each be used five times.
