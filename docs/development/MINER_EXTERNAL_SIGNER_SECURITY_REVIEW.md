# External signer: brief for the external security reviewer (#445)

**Status.** Implemented and tested. NOT security-qualified. The owner decided on
1 October 2026 that #445 merges only after an external security review. This
brief is written for that reviewer by the change's author. It describes the
trust boundary, the threat model, what the tests prove and do not prove, the
one exception, and where the author would attack first.

## 1. What changed

Before #445, `carbon.chain.auth.open_external_hotkey` did the following inside
Carbon's product process, the Control Center and the MCP door:
- read the miner's hotkey file;
- read a password file;
- decrypted the key;
- signed requests.

The name said "external", and the behaviour was not.

After #445:

- **The key holder is a separate program.** The miner runs `carbon-miner-signer`
  (package `carbon_miner_signer`, about 370 lines, imports nothing from
  `carbon`). It loads the hotkey once, and the Bittensor SDK asks for the
  password in that program's own terminal.
- **Carbon reaches it over one Unix socket.** The socket is
  `~/.carbon/signer/<hotkey>.sock`, a `0600` socket in a `0700` directory.
  Carbon sends the exact bytes it wants signed and verifies the returned
  signature against the public hotkey before using it
  (`carbon/chain/external_signer.py`).
- **The protocol is the SDK's own.** The signed bytes are `btauth/1`, the
  Bittensor SDK's `bittensor.http_auth` payload. Carbon plugs the signer into
  the SDK's documented custom-`Signer` hook. Nothing about the wire format is
  Carbon's invention.
- **One path, by type.** `BittensorMessageSigner` accepts only an
  `ExternalSigner`, and only `connect_signer` builds one. A valid raw keypair
  is a `TypeError`. The owner's CLI entry points sign the same way miners do.
- **Retired field refused.** A runner profile naming `miner_password_file` is
  refused with `miner_password_file_retired_start_signer`.

## 2. The trust boundary, and what crosses it

| Direction | What crosses | What never crosses |
|---|---|---|
| Carbon → signer | `{"op":"identity"}`, or `{"op":"sign","payload":<btauth/1 bytes>}`, at most 4096 bytes | the request body (only its sha256 is inside the payload), any path, any credential |
| Signer → Carbon | the hotkey ss58 and crypto type; a signature; or one closed refusal code | key material, seed, mnemonic, password, any free text |

The signer signs a payload only if **all** of the following hold
(`carbon_miner_signer/signer.py:refusal_for`):
- exactly 8 ASCII lines, protocol `btauth/1`;
- the signer's own scheme;
- method `POST` and path `/carbon/v1/mcp`;
- a 64-hex body hash;
- sender equal to its own hotkey;
- a nonce no more than 30 s old and no more than 5 s in the future. Carbon's
  verifier is stricter: 10 s back and 2 s ahead, with a persistent nonce store;
- a bound receiver (never `-`), within the `--receiver` allow-list when one is
  given.

The signer prints one line per signature to its own terminal, naming the
receiver and the first 16 hex digits of the body hash.

## 3. Threat model

### Protected against

- **Key exposure through Carbon's code.** A bug, a malicious change or a
  compromised dependency in Carbon's product process cannot read the hotkey,
  its password or its seed. The process never holds them. This matters
  because that process hosts an LLM-driven research agent, and miners run it
  on their personal machines.
- **Signing anything that is not a Carbon request.** Chain extrinsics, other
  paths, other methods, other senders, unbound receivers and stale or future
  nonces are each refused with a closed code. The pressure test and the
  interop run confirm this.
- **Other users on the host.** The `0700` directory and `0600` socket keep
  them out. On Linux the signer also checks `SO_PEERCRED` and refuses a peer
  with a different uid.
- **Research containers.** Research code runs in Docker with:
  - `--network none` and `--read-only`;
  - uid 65532 and `--cap-drop`;
  - pid, memory and CPU limits;
  - a single read-only `/input` bind mount.

  It cannot reach the socket.
- **Replay and redirection.** The signature covers method, path, body hash,
  nonce, sender and receiver. The verifier refuses a replayed nonce, a
  tampered body and a different receiver. The stock SDK verifier, with no
  Carbon code involved, refuses the same three.

### NOT protected against

- **A signing oracle for same-user processes.** While the signer runs, any
  process with the miner's uid can obtain a signature for any correctly shaped
  Carbon request. The signer sees only the body's hash, so it cannot tell a
  legitimate `battery_submit` from a malicious one. This is the ssh-agent
  model, and it is the main residual risk.
- **An unencrypted hotkey.** The Bittensor SDK writes hotkeys unencrypted by
  default. If the miner's hotkey file is unencrypted, any same-user process
  can read it directly. The signer then keeps the key out of Carbon's process
  only, not away from the user's other software.
- **A compromised signer host or a compromised SDK.** The signer trusts the
  installed `bittensor` package to load and use the key.
- **Non-Linux hosts.** There is no peer-uid check, so the `0700` directory is
  the only boundary.
- **Unbound receivers.** Without `--receiver`, the signer signs for any
  validator hotkey. The fixed path limits this to servers speaking Carbon's
  protocol.
- **The miner's own `BT_PW_*` environment variable.** If set, the password
  lives in the signer's environment. That is the miner's choice.
- **The coldkey.** It is out of scope: the signer is for the hotkey. Pointed
  at a coldkey file, it would refuse every request as `signer_wrong_hotkey`,
  because the address would not match the registered hotkey. It does not
  detect "this is a coldkey" as such.

## 4. What the absence proof covers, and what it does not

`tests/invariants/test_product_process_holds_no_key.py` walks the transitive
import closure of the two product entry points (`scripts/dev/miner_launchpad`,
`carbon/miner_mcp`), including imports made lazily inside functions. It parses
every module in that closure and finds:
- key-file opens (`Keyfile`, `get_keypair`, `Wallet`, ...);
- keypair construction (`create_from_*`);
- password reads (`password=`, `password_file`, `miner_password_file`,
  `getpass`);
- imports of `bittensor.keyfiles`, `bittensor.wallet` or the signer package.

Specimens show the scan failing:
- each rule is caught in a deliberate violation;
- the signer package's real key opening is caught;
- every module that used to open the key is inside the closure;
- a key open and a password prompt planted two lazy imports deep behind a
  product entry point fail the same assertion the product test makes.

**It does not prove:**

- **That the signer cannot be tricked into signing something.** Section 3's
  signing oracle is a design property, not a scan result.
  `tests/cpu/test_external_signer.py` and the pressure test exercise the
  refusals; no test can show that every accepted request was intended.
- **Behaviour at run time.** The scan is static. It cannot see dynamic imports
  (`importlib`, `__import__`), attribute names built from strings, or a key
  read through a generic `open()` on a path the scanner's name list does not
  recognise.
- **Anything about third-party code.** The scan covers repository modules
  only. `bittensor` itself contains wallet code; the scan shows Carbon's
  product code does not call into it for keys.
- **That the signer is correct.** That is what the signer tests, the pressure
  test and this review are for.

## 5. The one permitted exception

```
("carbon/chain/sdk_weights.py", "open_operator_wallet", "Wallet")
```

This is the single hole in "Carbon holds no key", named here so the reviewer
does not have to find it.

- **What it opens.** `open_operator_wallet` opens the **owner's** validator
  publisher wallet, used for weight publication under OD-4a. It never opens a
  miner's key.
- **Why the scan sees it.** It sits inside the product's import closure only
  because the product reads the operator's chain configuration from the same
  package, on the single-host deployment where validator and Launchpad share a
  host (#431 / OD-7).
- **What the tests show.** The scanner finds it, so the permit is not covering
  nothing. No product entry point file mentions it.
- **What the tests do not show.** "No entry point mentions it" is a text check
  on the entry files, not a call-graph proof. A transitive caller would not be
  caught by that check.
- **What would close it.** Moving `open_operator_wallet` out of the product
  closure, for example into a validator-only module the product cannot import.
  That would make the exception unnecessary. It is not done in #445.

## 6. Where the author would attack first

In order:

1. **The same-user signing oracle.** Run any process as the miner and ask the
   socket to sign a `battery_submit` the miner never intended. It will
   succeed. Mitigations to weigh:
   - per-request confirmation in the signer's terminal (like `ssh-add -c`),
     perhaps only for submissions;
   - showing the tool name, not just the body hash, by moving more of the
     request into the signed payload or a side channel the signer displays;
   - a short-lived session the miner arms.
2. **An unencrypted hotkey file.** Check whether the signer warns when the key
   file is not encrypted. Today it does not.
3. **`refusal_for` parsing.** Look for line-splitting edge cases, the 8-line
   check, case and Unicode in ss58 strings, and nonce integer overflow (the
   nonce is capped at 20 digits; Carbon's store requires `< 2**63`).
4. **Socket lifecycle.** Probe symlink and race windows on `bind` (the
   pressure test covers a symlinked path, a symlinked directory and a live
   socket takeover), and behaviour under SIGKILL and restart.
5. **The permitted exception's reachability** (section 5).
6. **The 30 s signer window against the verifier's 10 s.** A wider signer
   window is harmless while the verifier's nonce store holds, but it is worth
   confirming the store is persistent on every receiving deployment.

## 7. Evidence

- Invariant scan: `tests/invariants/test_product_process_holds_no_key.py`
  (9 tests).
- Real signer over a real socket, including the CLI under a pty with an
  encrypted key file: `tests/cpu/test_external_signer.py`.
- Refusal versus reconciliation, admission codes and the retired field:
  `tests/cpu/test_launchpad_signer_dispatch_honesty.py`.
- Pressure test results (hostile input, impostor signers, filesystem, load):
  in the #445 description.
- **Interop run, 1 October 2026.** A fresh random hotkey, encrypted, was held
  only by the real `carbon-miner-signer`, with the password typed into its
  pty. The signature on a Carbon request was:
  - accepted by the stock `bittensor.http_auth.verify` with no Carbon code;
  - verified as a bare sr25519 signature over `http_auth.build_payload`;
  - refused on replay (`ReplayedRequest`);
  - refused for a tampered body (`BadSignature`);
  - refused for another receiver (`WrongReceiver`).

  The signer refused chain-transaction-shaped bytes (`signer_refused`), and
  the password never appeared on its screen.
- **Not yet done.** No end-to-end run used the owner's real registered testnet
  hotkey on netuid 567. It needs the owner to start the signer with that key.

## 8. Compatibility with Bittensor subnet practice

- **Key handling.** Most subnet miners load the wallet in-process. The subnet
  template does `bt.wallet(config)`. No subnet surveyed (October 2026) uses a
  separate hotkey-signing agent; that is absence of evidence, not proof.
- **What it costs the miner.** One extra process, and typing the password in
  its terminal once per session.
- **Chain transactions.** Anything that must be signed with the hotkey on
  chain is done by the miner with their own Bittensor tooling, the same as
  registration. One such transaction is approved in principle but not built:
  OD-7(a) recipe-hash commitments. If it is ever built, the miner posts the
  commitment themselves. The signer will not sign extrinsics, by design.
  **Superseded for one extrinsic by OWNER-COMMITMENT-POSTER-01 (D1):** see
  §9. This paragraph is kept as the reviewed state it was.

## 9. Amendment: the commitment op (COMMITMENT-POSTER-01), NOT YET REVIEWED

OWNER-COMMITMENT-POSTER-01 (D1, D2, D8, D10) gives the signer exactly one
chain extrinsic, `Commitments.set_commitment`, and checks the key file at
every start. This amendment describes the change; it is **not** a security
acceptance, which stays the owner's, and tests are not an audit.

- **What it signs.** Only a payload it rebuilds itself
  (`carbon_miner_signer/commitment.py`): the call from `(netuid, digest)` and
  the signed extensions from structured fields, under the pins in
  `commitment_record.json`. The Launchpad's bytes must equal that
  reconstruction or the request is refused.
- **Who confirms.** Only the miner, typing the digest's last 8 characters on
  the signer's controlling terminal (`/dev/tty`). No socket field can
  confirm; a request carrying one is malformed.
- **Network.** None. The Launchpad reads the chain and broadcasts (S-offline).
- **Bounds.** Netuid and genesis fixed at start; tip 0; a mortal era of at
  most the recorded cap; a fee ceiling (HUMAN_INPUT until measured); one
  commitment per tempo in an append-only ledger beside the socket; one
  request at a time.
- **Start.** A key file that is a symlink, another user's, or readable or
  writable by group or others is refused before it is opened, with
  `chmod 600 <file>`.
- **Open for the review.** The prompt reads `/dev/tty` from a connection
  thread while the signer keeps serving `btauth/1` requests; a local process
  of the same user could print to that terminal. The digest's last 8
  characters bind what is typed to what is signed, but the review should
  judge the terminal as the trust root.
