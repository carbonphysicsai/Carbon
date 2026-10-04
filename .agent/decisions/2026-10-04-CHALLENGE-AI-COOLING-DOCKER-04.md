# CHALLENGE-AI-COOLING-DOCKER-04 — Docker-only registered campaign

**Date:** 2026-10-04

**Status:** selected engineering control; counted execution remains
owner-reserved

**Authority:** user-authorized operational follow-up to
`CHALLENGE-AI-COOLING-FOUNDATION-01`

## Decision

The frozen AI-accelerator-cooling registered campaign may execute only through
the Docker branch of `scripts/dev/cold_plate/reference/run_batch.py`. The
runner refuses `--native` before constructing or reserving the campaign ledger,
creating output artifacts, or dispatching a solver. The campaign continues to
pin the OpenFOAM image and requires the registered CPU, parallelism, timeout
and artifact-retention settings. This restriction does not remove native mode
from unrelated unregistered workflows.

Interrupted reservations remain charged. The current ledger is durable budget
accounting, not an automatic recovery engine: it has no supported transition
for reconciling an ambiguous `RESERVED` execution after its process state is
lost. Operators must preserve the ledger and artifacts, inspect retained
records and surviving containers, and stop for a specific owner reconciliation
decision when the existing terminal transitions cannot describe the evidence.

## Authority boundary

This decision adds no science or compute/spend approval. It leaves the frozen
8-design x 6-condition study, limits, methods, reference policy and 60-attempt
hard cap unchanged. Counted CFD remains blocked until the exact science and
compute/spend owners approve the registered campaign.
