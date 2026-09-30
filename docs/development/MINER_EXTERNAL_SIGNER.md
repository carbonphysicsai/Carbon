# The miner's signer: Carbon never holds your hotkey

Every request a Carbon campaign sends to the validator is signed with your
registered hotkey. Carbon does not do that signing. You run a small signer
process, `carbon-miner-signer`, that holds your hotkey. Carbon sends it the exact
bytes to sign and gets back a signature. The same ssh-agent pattern applies:
one process holds the key, and the process doing the work never sees it.

This is the only way Carbon signs, for every miner and for the owner's own host.
The earlier path, where Carbon read the key file and a password file itself, is
gone. A runner profile that still names `miner_password_file` is refused with
`miner_password_file_retired_start_signer`.

**Maturity:** implemented and tested. **Not security-qualified.** This change
touches hotkey authentication (AGENTS.md §13) and needs a dedicated security
review before anyone treats it as audited.

## What you do

First time, from your Carbon checkout:

```bash
uv sync --locked --group chain          # the signer needs only the Bittensor SDK
```

Every session, in a terminal you leave open:

```bash
uv run --locked --group chain python -m carbon_miner_signer \
  --wallet YOUR_WALLET --hotkey YOUR_HOTKEY
```

(`carbon-miner-signer` is the same command once the package is installed.) If
your hotkey file is encrypted, the Bittensor SDK asks for its password **in this
terminal**. The password goes to the SDK in your signer process and nowhere
else. The signer prints the hotkey it holds and the socket it listens on. After
that, each request it signs appears as one line: the receiver and a prefix of
the body hash.

Then use the Control Center or `carbon-mcp` as usual. There is nothing to paste
and nothing to configure. Carbon finds the signer at the path it derives from
your public hotkey, `~/.carbon/signer/<hotkey>.sock`. Ctrl-C stops signing.

Options: `--key-file PATH` instead of `--wallet/--hotkey`; `--expect SS58`
refuses to start if the file holds a different hotkey; `--receiver SS58`
(repeatable) signs only for those validator hotkeys; `--socket PATH` sets a
non-default path, which the profile's optional `signer_socket` then names.

## When it cannot sign

Each condition has its own code, and the Control Center and MCP door show the
correction beside it. Admission asks the signer before admitting any work, so a
missing signer is reported immediately rather than midway through a campaign.

| Code | Meaning |
|---|---|
| `signer_not_running` | Nothing listens on the socket. Start the signer. |
| `signer_wrong_hotkey` | The signer holds a different hotkey than the registered miner. |
| `signer_refused` (+ reason) | The signer declined: `NOT_A_CARBON_REQUEST`, `WRONG_SENDER`, `STALE_NONCE`, `RECEIVER_NOT_ALLOWED`, `MALFORMED_REQUEST`. |
| `signer_timeout` | The signer did not answer in time (HTTP 503; the others are 409). |
| `signer_invalid_signature` | A signature came back that does not verify for the hotkey. It is discarded. |
| `signer_protocol` | Something other than the signer answered on the socket. |

A signer failure before any request of an operation was signed is a refusal:
nothing was sent. If an earlier request of the same operation had already been
signed, that request may have been delivered, so the operation goes to
reconciliation and is never reported as "nothing happened". On the MCP door,
`dispatch_may_have_occurred` follows the same rule.

## The boundary

| Direction | What crosses |
|---|---|
| Carbon → signer | `{"op":"identity"}`, or `{"op":"sign","payload":<btauth/1 bytes>}` |
| signer → Carbon | the public hotkey and key type, a 64-byte signature, or one closed refusal reason |

The payload is the SDK's normative `btauth/1` string
(`bittensor.http_auth.build_payload`). It contains the protocol, scheme, `POST`,
`/carbon/v1/mcp`, the sha256 of the exact body bytes, the nonce, the sender and
the receiver. The validator rebuilds it from the same inputs. Carbon verifies
every returned signature against the public hotkey before using it.

The signer signs **only** that shape: `POST /carbon/v1/mcp`, sent by its own
hotkey, bound to a named receiver, with a nonce within 30 s of now. It never
signs a chain extrinsic or an arbitrary message. The socket's directory is
`0700` and the socket is `0600`. On Linux the signer also checks that the
connecting process belongs to the same user.

## How the absence is proven

`tests/invariants/test_product_process_holds_no_key.py` walks the transitive
import closure of both product entry points (`scripts/dev/miner_launchpad`,
`carbon/miner_mcp`) and scans each module's syntax tree. It asserts that no
module opens a key file, reads a password, imports a keyfile or wallet API,
constructs a keypair, or imports the signer package. The scan is shown catching
each rule in a deliberate violation, and catching the real key opening in
`carbon_miner_signer`. It is also shown reaching every module that used to open
the key. `BittensorMessageSigner` accepts only an `ExternalSigner`, which only
`connect_signer` can construct, so a valid raw keypair is refused by type.

One named exception: `carbon.chain.sdk_weights.open_operator_wallet` opens the
**operator's validator** wallet for weight publication. It is importable only
because the single-host deployment shares the chain package. No product entry
point calls it, and it is never a miner's key.

## Known limits (for the security review)

- Like ssh-agent, any process running as your user can ask the signer to sign a
  Carbon-shaped request. `--receiver` narrows what it will sign.
- Without `--receiver`, the signer signs for any validator hotkey.
- The SDK may read a `BT_PW_*` environment variable if you set one. That is the
  SDK's feature in your signer's environment, not a Carbon input.
- On non-Linux hosts the `0700` directory is the only boundary; there is no
  peer-uid check.
- Submission still evaluates in-process on the validator host (#431). That is
  the OD-7 submission-path decision, not this boundary. The seam is
  `carbon/battery/campaign.py`, where the signed headers are handed to
  `gateway.receive`. A future intake transport replaces that call and receives
  the same signed body and headers unchanged.
