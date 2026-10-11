## 2026-10-08 — OWNER-SIGNER-TESTNET-AUTOCONFIRM-01: opt-in auto-confirm of commitments for allow-listed testnet 567 hotkeys

**Authority.** The owner, 2026-10-08.

- Relayed by the Test Lead session:

  > approve testnet auto-confirm for test hotkeys

  It covers Graphite's confirmation lane (hotkeys minerD to minerG) and the
  CANARY-01 canary hotkey (`carbon-canary`).
- Directly in the Launchpad Acceptance session:

  > I approve this action now

  and later:

  > Approve all

**What it amends.** OWNER-COMMITMENT-POSTER-01 D10 says that only the human
confirms, on the signer's TTY, and that an agent can never confirm. This
record amends D10 prospectively, and D7's "the miner's TTY confirmation" with
it, **for testnet 567 only, and only for hotkeys in an owner-written
allow-list.** Everywhere else D10 and D7 stand as written. Mainnet stays
under D5: nothing here touches it.

**The hotkeys.** The test wallets minerD, minerE, minerF and minerG, and
`carbon-canary`. The owner writes their public ss58 addresses into the
allow-list file; no address is recorded here.

**What is built (SIGNER-AUTOCONFIRM-01).** `carbon-miner-signer` gains one
opt-in flag, `--auto-confirm-commitments <allowlist-file>`. Off by default.
With it, the signer signs a commitment without the terminal prompt only when
all of these hold:

1. the request is the existing `commit` op and passes every existing bound:
   the one pinned `Commitments.set_commitment` call of a `sha256:<64 hex>`
   digest, the netuid, tip 0, the era cap and the recorded fee ceiling;
2. the chain genesis is testnet 567's,
   `0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105`,
   hard-coded in the signer. Any other genesis, mainnet especially, refuses
   the flag at start and the auto path on every request;
3. the signer's own hotkey is in the allow-list;
4. the D4 ledger check passes: at most one per hotkey per tempo.

Every auto-confirm is shown on the signer's terminal and appended to its
commitments ledger, with the digest, network, netuid, era and fee the manual
prompt shows, marked `AUTO-CONFIRMED (allow-listed testnet hotkey)`.

**The risk, stated.**

- The flag removes a person from commitments only. Message signing for
  receivers, the `--receiver` allow-list and every other signer path are
  unchanged.
- An unattended signer needs an unlocked hotkey. So these hotkeys must be
  test-only: their own coldkeys, test TAO, no stake, never mainnet.
- The genesis lock refuses everything else.

**Working decisions (delegated, recorded here).**

| # | Decision | Choice |
|---|---|---|
| W1 | A failed auto check: refuse, or fall back to the TTY prompt? | **Refuse**, with a closed code. An unattended signer has no terminal, so a prompt would only hang until it timed out. A request that fails an existing bound keeps its existing code (`NOT_A_COMMITMENT`, `WRONG_NETWORK`, `FEE_OVER_CEILING`, `ALREADY_COMMITTED_THIS_TEMPO`, ...). A request off testnet 567, or for an unlisted hotkey, is `AUTO_CONFIRM_NOT_ALLOWED`, a new closed code the Launchpad reports as itself. |
| W2 | When does an allow-list change take effect? | **Only after a restart.** The file is read once, at start. A signer never re-reads it, so a file swapped while it runs changes nothing. |
| W3 | What is refused at start? | A missing, symlinked, non-regular, other-user, or group- or world-accessible file (the D8 rule); a file over 4096 bytes; anything but exactly `{"schema": "carbon.signer.autoconfirm-allowlist.v1", "network": "testnet", "netuid": 567, "hotkeys": [1 to 16 distinct ss58]}`; an unpinned or non-testnet-567 commitment record; an `--expect` hotkey not listed (before the key is unlocked); a loaded hotkey not listed (before the signer serves). |
| W4 | What does the ledger row add? | Auto rows only add `"confirmation": "AUTO-CONFIRMED (allow-listed testnet hotkey)"` and `"network"`. Manual rows are unchanged. The ledger schema stays `v1`; the D4 check reads the same fields. |

**Not decided here.**
- Security acceptance of the signer change. It stays the owner's, and tests
  are not an audit.
- Any mainnet use. It is refused by construction.
- The allow-list's contents. They are the owner's to write.

**Maturity.** SPECIFIED by this record; IMPLEMENTED and TESTED in the PR
that carries it. Not security-qualified. Nothing here is LIVE.

**Merge.** It changes the signing path, so PR Head merges it only on the
owner's word in its own session.
