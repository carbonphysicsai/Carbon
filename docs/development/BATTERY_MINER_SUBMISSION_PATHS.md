# Battery: how a miner's submission reaches the validator (decision brief)

**Status.** This is a brief for the owner. **Nothing here is implemented or
chosen.** Both paths are approved in principle in the same OD-7 row of
OWNER-BATTERY-TESTNET-01 (`.agent/DECISIONS.md`, 2026-09-25). No record picks
between them.

**The problem.** The owner's goal is: "I want to go to launchpad from the
website and set up an agent to run on testnet in the control center. I want
this experience for all future miners." Today that journey works **only on
the owner's host**:
- a submission is a `battery_submit` message signed with the miner's hotkey;
- it goes to `AuthenticatedGateway.receive`, in the same process
  (`carbon/battery/campaign.py`, the submit step);
- the gateway is documented as having "no public listener"
  (`carbon/transport/gateway.py:1`).

So a miner on their own machine has no way to reach the validator.

## The two approved paths

**OD-7 wording.** OD-7 approves both:
- "(a) the Launchpad's miner hotkey … may post **recipe-hash commitment
  transactions** on netuid 567, bounded in count per day and in window";
- "(b) a **Carbon submission intake** (NET-2 signed transport) may be exposed
  publicly during the testnet window, hosted with the validator pods (RunPod
  HTTP proxy) and covered by the OD-3 security review".

### (a) The chain path: recipe-hash commitments

**What it binds.** M3-D9 defines the digest format
`carbon.battery.commitment.v1`. It is a SHA-256 over:
- the Challenge;
- the contract digest;
- the strategy hash.

It does **not** include the recipe itself, a submission id or a time window.

**What exists: only the consumer side.**
- The daemon's admission check (`carbon/battery/daemon.py:400-418`):
  - computes the expected digest;
  - when `require_commitment` is on, reads the hotkey's current commitment
    from a reader;
  - refuses with `CommitmentRequired` unless the digests match;
  - records `{digest, block}` in the admission.
- Tests use a fake reader.
- The deployment always passes `commitments=None`
  (`carbon/battery/deployment.py:152`). That is why the live deployment runs
  `require_commitment: false`, and why every admission records
  `commitment: null`.

**What is missing:**
- a chain `CommitmentReader`;
- a miner-side posting tool;
- runtime-probe coverage for the chain's commitments call and its storage;
- a freshness and window check, so a commitment cannot be reused;
- an approval sequence for miner transactions, like OD-4a's;
- **the bounds themselves.** The count per day, the window, the fee cap and
  the expiry are owner values, and none is recorded.

**Cost:**
- about **3-5 engineering days**. The reader is modelled on the existing
  chain adapters; the posting path on the bounded, approval-gated OD-4a
  pattern;
- **owner values** for the bounds;
- **a per-transaction approval sequence.** Every commitment is a chain write
  from a miner hotkey.

**The limit.** The chain path **does not deliver a submission.** A
commitment is a hash. The validator still needs the recipe itself, so the
chain path on its own does not let a stranger's submission reach the
validator.

### (b) The intake path: a public NET-2 intake

**What exists: authentication and abuse limits, complete** (NET-2,
`carbon/transport/`). The gateway:
- checks the method and path;
- enforces header and body size limits;
- checks the network, genesis, netuid and Challenge;
- requires a metagraph snapshot no more than 60 s old;
- requires the receiver to be registered;
- verifies the hotkey signature.

The journal:
- rejects replays and conflicting resends;
- enforces a capacity limit;
- allows at most 32 requests per hotkey per second.

**What is missing:**
- **a listener:** a server that passes the raw body and headers to `receive`
  and then to evaluation;
- **an asynchronous queue and a status endpoint.** Evaluation takes minutes
  and runs synchronously today;
- TLS and the proxy configuration;
- **limits that apply before authentication.** Today's per-hotkey limit
  applies only after the signature is verified, and each request fetches a
  chain snapshot, which is an amplification risk;
- a miner client;
- **a security review scoped to the intake.** OD-3 as recorded covers only
  the PyBaMM truth image and the GPU validator image
  (OWNER-BATTERY-TESTNET-04). It does not cover an intake.

**A mismatch with OD-7(b).** OD-7(b) says the intake is "hosted with the
validator pods". The battery validator now deploys **on this host** (#357).
- Exposing an intake means making this host reachable from outside.
- For this host that is gated by the owner's §4 security review
  (`docs/development/CONTROL_CENTER_PROGRAMME.md`).
- The review's text is not in the repository.

**Cost:**
- about **2-4 engineering days**. Authentication, replay protection and
  per-hotkey limits already exist;
- plus TLS and exposure configuration;
- plus **the security review, which is not engineering work and is not yet
  scoped.**

## Recommendation: build the intake first, then the commitment reader

1. **Only the intake delivers a submission.** Without it, no path from a
   miner's machine exists, whatever is on chain. The chain path adds binding
   and timestamping on top of an intake. It does not replace one.
2. **The launch path already orders them this way.** v1.0.4 specifies
   "authenticated submission intake → candidate commitment verification", in
   sequence.
3. **The intake needs less new code.** NET-2 already does authentication,
   replay protection and per-hotkey limits.
4. **The commitment reader is the next step.** It is what lets
   `require_commitment` be turned on, so an admission is bound to an on-chain
   record rather than only to a transport signature. It needs the owner's
   bound values first.

**What the owner decides:**
- **Where the intake is exposed:** this host, under a §4 review scoped to the
  intake, or pods as OD-7(b) says.
- **The review:** scope and schedule for an intake review.
- **Chain bounds, when (a) follows:** the count per day, the window, the fee
  cap and the expiry.

**What does not change:**
- no chain write without its exact approved record;
- testnet 567 only;
- signing stays external: the miner signs in their own tooling;
- Carbon holds no key.

**Maturity.** This is an engineering assessment from code and records. It
qualifies nothing.
