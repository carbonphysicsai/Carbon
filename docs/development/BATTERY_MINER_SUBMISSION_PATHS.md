# Battery: how a miner's submission reaches the validator

**Status (2026-09-30).** The owner chose the intake
(OWNER-BATTERY-INTAKE-01, `.agent/DECISIONS.md`): "mainnet intake will be
hosted by validator images, but we are testing now … intake has to be
wherever it needs to be for testnet testing. But ensure we have the design
right for the mainnet switch." The intake is now **built and tested**
(`carbon/battery/intake.py`, `carbon/battery/intake_client.py`,
`tests/cpu/test_battery_intake.py`). It binds loopback unless its
configuration names the owner's exposure record. **The owner approved that
exposure on 2026-10-02 (OWNER-INTAKE-EXPOSURE-01)**: testnet 567, the battery
Challenge, today's routes and limits, with TLS terminated in the intake. The
brief below the next section is the original
decision brief, kept as written.

## The decision, checked against Bittensor

**What the Bittensor documentation says** (read 2026-09-30 from
`https://www.bittensor.com/llms.txt`; docs.learnbittensor.org now redirects
there). The pinned SDK is `bittensor==11.1.0`.

- **v11 has no networking stack.** "v11 contains no miner/validator
  networking stack": Axon, Dendrite and Synapse are gone. A subnet runs its
  own HTTP server and client and authenticates with `btauth/1`
  (`bt.http_auth.sign` / `verify`). Source: the migration guide,
  "Axon, Dendrite, and Synapse are gone". The installed module's own
  docstring says the same (`bittensor/http_auth.py`).
- **Validators may be reachable.** The validating guide: "Publish your
  endpoint with `serve-axon` if your subnet's protocol requires validators to
  be reachable." The chain's `serve_axon` needs only a registered hotkey,
  with no validator-permit check (`pallets/subtensor/src/subnets/serving.rs`).
  The pinned SDK exposes `SubtensorModule.serve_axon` and `serve_axon_tls`.
- **The default direction is the other way.** In the mining guide validators
  find miners through the miners' on-chain axon info. No official page names
  a subnet where miners push to validators. So validator-hosted intake is
  **permitted and documented as an option, not the default.**
- **`btauth/1` does not check registration.** "Authentication says who;
  whether they may call you is your policy." Carbon's NET-2 journal does: a
  hotkey not in the validator's snapshot is `TRANSPORT_IDENTITY`.
- **Commitments are small.** At most 3 fields per commitment, `Raw` up to
  128 B, `BigRaw` up to 512 B, a hash field, and about 3,100 bytes per
  account per subnet per epoch (pallet source at the chain commit read, not
  re-read from netuid 567). A recipe is too large to put on chain; its
  SHA-256 fits in one hash field.

**So the owner's statement is consistent with Bittensor**, with one caveat:
it is the documented option, not the default pattern. The default pattern for
an artifact (third-party subnets 9 and 37, not official guidance) is "commit a
hash on chain, validators fetch the artifact from a store".

## The design, testnet now and mainnet later

| | Testnet now | Mainnet switch |
|---|---|---|
| Where the intake runs | this host, next to the one validator deployment | inside every validator image |
| Receiver | the testnet validator hotkey (config `receiver`) | each validator's own hotkey |
| How a miner finds it | the URL the owner publishes | the validator's on-chain axon (`serve_axon_tls`) |
| Authentication | `btauth/1` + NET-2 journal (registration, replay, per-hotkey rate) | the same |
| Binding across validators | none (one validator) | the OD-7(a) recipe-hash commitment, so every validator admits the same recipe at the same block |
| Exposure | loopback; public only with a recorded §4 exposure decision | each validator operator's own exposure |

**What makes the switch a configuration change, not a redesign:**
- **A request is bound to one validator.** `btauth/1` signs the receiver
  hotkey, so a signed submission cannot be replayed to another validator.
  At mainnet a miner signs one copy per validator.
- **No request causes a chain read.** One refresher per intake reads the
  metagraph every 12 s; a request must name one of the last five snapshots
  it observed (`snapshot_unknown` otherwise). This was the amplification risk
  in the original brief, and it is removed by construction.
- **Admission is asynchronous and durable.** A received submission is in the
  intake's inbox before the answer (202 with its submission id) is sent. One
  worker admits and advances it through the deployment's single daemon,
  under the deployment's single-writer lock. The id is the daemon's own
  (`daemon.submission_identity`), so it is known before admission runs.
- **The miner signs.** `intake_client` builds the exact bytes and sends
  bytes with headers the miner produced. It has no signing code; a test holds
  that, with the docstring's own signing example as its specimen.
- **Status is the miner's own.** `battery_status` returns the daemon's
  allow-listed outcome only to the hotkey that submitted; any other hotkey
  gets `not_found`, never "exists but not yours".

**What is still missing, and whose it is:**
- **The exposure decision (owner): recorded.** OWNER-INTAKE-EXPOSURE-01
  (2026-10-02). A public bind names it and terminates TLS in the intake, or
  the listener refuses (`intake_exposure_unrecorded`,
  `intake_exposure_needs_tls`). Exposing a host stays an operator action.
- **The commitment reader (Testnet lane, then owner bounds).** Needed at
  mainnet, where several validators must agree on what was submitted. It
  needs the owner's count per day, window, fee cap and expiry.
- **The Launchpad seam (Launchpad lane).** `campaign.py` still signs and
  evaluates in process. For a miner's own machine it posts to the intake
  with `intake_client` instead, and the miner's tooling signs.
- **Pre-authentication limits behind a proxy.** The per-peer bucket keys on
  the socket peer. Behind a TLS proxy every request shares one peer, so a
  proxied deployment terminates TLS in the intake (`tls_cert`/`tls_key`) or
  needs a trusted-proxy header rule first.

## Security status: implemented; exposure approved by the owner

The intake is implemented and tested. The owner approved its exposure on
2026-10-02 (OWNER-INTAKE-EXPOSURE-01), for the recorded scope only, with the
items below on file and not fixed. Tests hold the gate; they are not a
security audit. A public listener is AGENTS §13 work:
untrusted input, authentication and reachability. OD-3 as recorded approves
a security review of two images, the GPU validator reconstruction image and
the PyBaMM truth image. It does not cover a listener. The OD-7(b) row's
phrase "covered by the OD-3 security review" is therefore not read as
covering this intake. Exposure needs its own record, which the listener
checks for by name.

**Limits before authentication, held by tests.** Every request goes through
the peer's token bucket, then the global in-flight cap. Only then is a body
read, a message parsed or a signature checked.
`test_limits_apply_before_authentication` sends a validly signed submission
over each limit and asserts that the real verifier, wrapped in a counter, was
never called. Its specimen is the same signed request from a fresh peer,
which is verified and received.
`test_over_http_a_limited_request_has_no_body_read` holds the same ordering
over a real socket. Both tests fail when the limits are moved after the route.

**For the security review to examine** (known, not fixed here):
- `ThreadingHTTPServer` starts one thread per accepted connection before any
  limit applies. A slow client holds its thread for up to the 10 s socket
  timeout, so the number of connections is bounded by the operating system,
  not by the intake.
- The bucket table is cleared when it exceeds 4,096 peers. A party with many
  source addresses can reset every peer's bucket.
- Behind a proxy every request has one peer (above).
- The listener runs on the host that holds the validator's private root, seed
  journal, pool state and service key (next section).

## What the intake changes for a remote miner, and what it does not

**Today.** A battery submission is signed and evaluated in-process on the
host that holds the validator's private root, the seed journal, the pool
state and the service key (`campaign.py` through `deployment`). A miner on
another machine has no way to submit.

**What the intake changes.** The signature moves to the miner. A miner's own
tooling signs a `btauth/1` request bound to this validator's hotkey, and the
intake authenticates it against an observed metagraph snapshot, journals it
against replay, and answers with a submission id. The private root, seed
journal, pool state and service key never leave the host, and nothing in an
answer carries them. Status is allow-listed and readable only by the
submitting hotkey.

**What it does not change.**
- **Evaluation still runs on the same host**, under the same single daemon
  and lock. The intake carries submissions to it and adds no isolation
  between the listener and that private state. Exposing it puts an
  internet-reachable parser on that host, which is why the exposure is a
  security decision.
- **A listener without a client transport still leaves a miner unable to
  submit.** `intake_client` builds the bytes, but nothing a miner runs uses
  it yet. The Launchpad seam is still open (above). Until it lands, and until
  the exposure is recorded, a remote miner cannot submit.
- It binds no submission across validators. That is OD-7(a)'s commitment, at
  mainnet.

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

**Correction (2026-09-29), reported by Launchpad and checked against
main.** Two code facts widen the gap. Both paths need both of these.

1. **Submission signs in-process today.**
   - `carbon/battery/campaign.py:343-347` opens the miner's hotkey from its
     key file and password file inside the Control Center process.
   - `:625-627` signs `battery_submit` there, with
     `BittensorMessageSigner`.
   - No external-signing path exists. For a remote miner, a seam where the
     miner's own tooling signs has to be built.
2. **Submission evaluates in-process today,** on a host that holds the
   validator's secrets.
   - `campaign.py:628-632` calls `gateway.receive` and then the evaluation
     directly.
   - `carbon/battery/deployment.py:124-145` loads the validator's private
     root, seed journal, pool state, work directory and service key.
   - For a remote miner, that call must become a client transport to the
     intake, in addition to the listener.

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
- a miner client, replacing the in-process `gateway.receive` and evaluation
  in `campaign.py:628-632`;
- an external-signing seam, since submission signs in-process today;
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
- no path signs with a key Carbon holds. The *intended* design is that the
  miner signs in their own tooling. **Today's code does not do that yet**
  (below);
- Carbon holds no key.

**Maturity.** This is an engineering assessment from code and records. It
qualifies nothing.
