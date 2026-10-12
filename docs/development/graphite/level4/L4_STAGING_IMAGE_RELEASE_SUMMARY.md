# The next analysis-image release: what new code it carries (for the owner's decision)

**What this page is.** A plain-language summary for the owner, written by the Graphite Testing Manager. It needs the
owner's own acceptance before the image is rebuilt and released. Nothing here is a security acceptance, and no one
else's word replaces his. It recommends nothing that goes around his decision.

**Why it is needed now.** The analysis image the readiness gate pins was built before GRAPHITE-L4-STAGING-01 (#1098).
That change altered the files the image must carry, so the current image no longer matches the repository
("analysis runtime source binding differs"). Rebuilding it at the current main IS the release that #1098 reserved to the
owner ("the analysis image release that carries slice 1; the owner's word"), together with the isolation review of what
it carries. Until it ships, the sandbox cannot run the Level 4 lowering tool, and the gate's containment check (item R1)
cannot pass.

## What new code enters the image

Fourteen small Carbon modules (the last of them a leaf helper) and one data file, all already in the public miner-facing part of the repository:

- the Level 4 tooling that turns a participant's model into a graph description (`carbon.level4.tooling` with its JAX and
  PyTorch lowering helpers, a `graph`, `params`, `named`, `initializers`, `interpret` and `submission` helper, and the
  allow-list data file `allowlist_v1.json`);
- a step that packs the result as one gzipped "envelope" (`carbon.level4.staging`);
- one tiny leaf module, `strict_json`, plus an empty package stub, so none of the validator's own code rides along
  (the leaf module is counted in the fourteen).

A test proves that a real lowering reaches nothing outside this list. Nothing from the controller, the evaluator's
orchestration, private stores, the chain or scoring is in the image.

## What it can touch (the sandbox the code runs in)

The tool runs inside the same miner analysis container that participants' own Python already runs in today. That container
has: no network at all; a read-only root; no added privileges and all Linux capabilities dropped; a private IPC space; an
unprivileged user; the shared-memory size capped to the host's; one read-only input folder; and one writable scratch
folder, its only place to write. On Carbon's own host an operator's CPU and memory bounds apply as well.

What is new is not the container but what runs in it: the tool loads the participant's model source and executes it to lower it
(the model is untrusted). It writes its result into the scratch folder. Carbon never runs that source on a Carbon host. Carbon
later reads one exported file through the miner door's ordinary file read, in bounded chunks, unzips it under a size bound, and
parses it strictly as data. It then runs three checks on it (G0, G3 and G4) and keeps it by digest. A malformed or oversized
envelope is a typed refusal, never a score.

## What is verified, and what is not

- **Verified by tests (on CPU, with stand-ins):** the image closure test above; the packing and the stage tool; that a
  proposal naming a staged digest carries its documents, and that an unstaged digest is refused; the pod path and the
  rebuild of a bundle; a scripted Level 4 session end to end.
- **A check exists but has not run on the new image:** the fixed containment check (a planted host file, the host's
  process list and control groups, the host home, network attempts, writes outside scratch) checks the container profile above from the host. It has not been run against an image carrying the new code, because
  it cannot run until this image is rebuilt.
- **Not verified:** a live lowering in the real miner container; the lowering of a hostile model source (for example one that
  tries to exhaust memory or time, or to write a very large file into scratch); graph training of a lowered graph on a real
  pod; G5 (compile in isolation), which is not wired into this path. The tests show behaviour, not an audit; no one has
  performed a security audit of the lowering tool.
- **Not covered by anything accepted so far:** the owner's earlier acceptance (OWNER-L4-G5-COMPILE-ISOLATION-01) covers
  compiling a Carbon-checked graph in the compile lane for development and testnet. It does not cover running a participant's
  model source through the lowering tool, nor the envelope transport. Mainnet stays outside every acceptance and needs its own
  review.

## The owner's decision

The owner decided on 2026-10-13, directly in the coordinating session. Asked to accept the isolation of lowering untrusted model
source in the existing analysis container and the envelope transport for development and testnet only, to have the containment
check run on the new image first, or to decline, he answered: "I fully accept it into testing. We will analyze it there"
(`.agent/decisions/2026-10-13-OWNER-L4-STAGING-IMAGE-RELEASE-01.md`). That is the release word for the rebuild, for testing
(development and testnet) only; mainnet is outside it. The "not verified" list above stays attached: this is an acceptance into
testing, not a claim that a security audit was done. The Test Lead's conditions apply to the release: the containment check on the
rebuilt image runs first and must pass before any Level 4 lowering, and a hostile-model lowering probe goes in the first Level 4
test batch.
