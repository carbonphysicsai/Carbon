# SOURCE-UPLOAD-APPEND-01 (19 Nov 2026)

**Context.** Live 116 submit outage, 19 Nov 2026. Graph source chunks are at most 8 KiB. Each chunk stored the whole
partial upload again as a new content-addressed workspace object and never removed the one it replaced, so later
chunks read, hashed and storage-scanned a growing pile of superseded copies.

**Decision (door-code, Validator-2 content Y on the five pre-ruled conditions).** A partial upload is one append-only
owner-private file, `<campaign>/workspace-partials/<sha256(owner)>/upload-<id>`. Its length is the received count. The
storage check runs before a chunk is accepted with the same amount as before (whole partial + chunk + 64 KiB). The
complete file is verified and published as before. A partial the earlier layout wrote (a workspace row) is continued.

**Miner-visible relaxation (V2 ruling).** A chunk sent from an earlier offset whose already-held bytes equal its first
bytes is now ACCEPTED, and only its new bytes are appended (before: `IDEMPOTENCY_CONFLICT`). This is also how a chunk
torn by a crash completes on retry. A chunk that differs in any held byte still refuses with `IDEMPOTENCY_CONFLICT`.
The file never shrinks; a refused chunk changes nothing. Every other refusal code is unchanged.

**Not changed.** Storage limits and their refusal (`LedgerRefusal`, `retained_bytes`). Superseded partial objects
already written before this change stay on disk until a separate cleanup decision.
