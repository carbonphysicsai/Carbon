# OWNER-INTAKE-EXPOSURE-03R: rehearse the public intake tunnel on a rented machine (testnet)

Date: 2026-10-23
Status: **ACCEPTED by the owner, directly in the Carbon Validator's session.** The Validator offered "(2) your direct OK for a rented-box tunnel, testnet only, no sealed data". The owner replied: "I'm good with 2 nothing bad is going to happen. WE ARE TESTING."
Extends: OWNER-INTAKE-EXPOSURE-03 (same design, routes, limits and gate) to a **rehearsal** host.

## Accepted (testnet 567 only)

- **The host:** a rented secure-tier GPU machine used for rehearsal only, not the monthly validator host.
  - **No sealed exam material, no validator signing key, no custody data** on it.
  - Public TRAIN and practice material only.
  - Deleted after the rehearsal, once its results are fetched and verified.
- **Exposure:** the same Cloudflare trusted-proxy tunnel design (#1267, PLT-15) and the same two-route allow-list as EXPOSURE-03. A **rehearsal hostname**, not the production `intake.carbonphysics.ai` (for example a staging subdomain), so the production name is never pointed at a rented box.
- **The same go-live checks** as EXPOSURE-03: the offline ingress check; §5.3 with the URL unpublished, including the three-outcome forged-header test with its negative control; the added checks (internal routes 404, tool allow-list, the four Challenges end to end). Any miss is a rollback.
- **The rented machine's cost** falls under the standing GPU test rental rule (≤ $5 per rental) or the weekly grant.

## Not covered

Mainnet; the production hostname on a rented box; any sealed material on the rehearsal host; leaving the rehearsal tunnel up after the rehearsal.
