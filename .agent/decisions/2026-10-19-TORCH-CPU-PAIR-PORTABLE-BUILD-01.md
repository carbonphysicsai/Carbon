# Torch CPU pair: portable image identity steps

Root and Lead assigned the independent public CR02 worker/analysis readiness
slice while the CR01 diagnostic handoff is held. Start from exact
a2622ca4787d05455806196053f706770a905e17; preserve that CR01 branch and its
artifacts. Do not access the rejected R16 diagnostic or edit receiver/retry
and lifecycle code owned by the separately held P2 slice.

The Torch CPU Dockerfile uses heredoc RUNs for its embedded identity rewrite
and installed-pin verification. The held VM has already demonstrated a legacy
builder that accepts Dockerfile heredocs without running their bodies. Skipping
the rewrite retains the C03 parent's base-image, recipe and lock in the embedded
record while Torch labels name the child values. Public historical setup only
records worker_image_unverified; this source analysis predicts the three-field
mismatch and does not fabricate missing historical image records.

REPAIR the two build-only steps with a hash-bound copied Python helper and
ordinary RUN commands. Keep the CPU requirements, profile, determinism and
parent verification unchanged. KEEP the existing ordinary COPY/RUN analysis
builder, whose manifest must name the actual Torch worker parent. No GPU recipe,
model code, TRAIN, scoring, science value, isolation or permission changes.

Focused checks exercise record rewrite/agreement, malformed identities and
installed-pin/determinism refusal. Native-host checks are diagnostics. Product
alone builds and doctors the exact new matched pair on the admitted VM after
R16 evidence is safe, then considers a bounded normal CR02 task at use time.
No image identity, model result or readiness is earned by this source slice.
The Development Hub remains frozen under current delivery policy. No provider
call, PR, push, main change or runtime dispatch is authorized by this packet.
