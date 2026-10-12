# Cooling central point B, optional stress C

Owner relay of Test Lead decision, 2026-10-11. Source for every numerical
setting: merged research #1084, Business/research/ai-chip-cooling-sources/
operating-points.json and SOURCE_REVIEW.md (merge 58e712d43).
B freezes 40 C / 1000 W / 1.50 L/min / 25 kPa cell allocation. C freezes
45 C / 1400 W / 2.80 L/min / 30 kPa only if Data Collection's value check
needs optional stress; C is not P by default. Keep separate registrations
so fixed service flows are not silently overridden by geometry actions.

Lid is REPRESENTATIVE vapor-chamber, sourced thickness 1–10 mm, typical
3–4 mm; no calibrated tensor/through-plane law or map supplied by research.
Its 2000/5000/10000 effective-k sensitivity is an assumption screen, not
reference physics. Existing complete registration and hashes still required;
missing map/uncertainty, P/Q/w and objective stay explicit and fail closed.
No historical rescore, full plate, solver runs, grant or spend.
