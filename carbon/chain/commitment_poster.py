"""The Launchpad's side of a miner's strategy commitment (OWNER-COMMITMENT-POSTER-01).

A validator that requires a commitment admits a submission only when the
hotkey's current on-chain commitment equals
``daemon.commitment_digest(challenge, contract_digest, strategy_hash)``
(``carbon.chain.commitments``). This module gets that commitment on chain, the
standard Bittensor way: the miner's own hotkey signs
``Commitments.set_commitment`` (D1). Miners may equally post it with their own
SDK code; a validator reads only the chain.

D2 is S-offline. The Launchpad reads the chain and broadcasts; the miner's
``carbon-miner-signer`` holds the key, rebuilds and checks the call, asks the
miner on its own terminal and signs. Carbon never holds the key and never
asks the signer to sign bytes it has not rebuilt.

The flow, in order (scope §4):

- L1 ``expected_digest``: the digest from public Carbon code, through the
  daemon's own function.
- L2 ``plan``: show it, and warn that it replaces the hotkey's current
  commitment (a queued submission for another recipe then fails
  ``commitment_required``).
- L3 read the current commitment at the finalized head; the same digest
  already there is not posted again.
- L4 prepare the unsigned extrinsic with the SDK and estimate its fee.
- L5 ask the signer; an agent sees ``human_action_required:
  confirm_commitment`` (D10), and only the miner's typing confirms.
- L6 check the returned call, verify the signature over the SDK's own
  payload, re-estimate the fee against the signer's ceiling, broadcast once,
  wait for finality and read the digest back.
- L7 ``commit_then_submit``: submit only after that. A validator that
  answers ``commitment_stale`` (D6: the commitment predates the hotkey's
  previous admission) gets an offer to recommit; ``post(digest,
  recommit=True)`` posts the same digest again, past the L3 skip. D4 still
  holds: the signer signs at most one commitment per tempo.

Never resent (scope B10): a request whose outcome is unknown is reconciled by
reading the chain until its mortal era has passed. Nothing here signs.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import json
import os
import re
import threading
from contextlib import aclosing
from enum import Enum
from importlib.metadata import version
from pathlib import Path

from .commitments import ChainCommitmentReader, CommitmentUnavailable
from .external_signer import SignerFailure
from .models import CARBON_NETUID, ChainFailure, FailureCode, hash256, uint
from .sdk import SDK_VERSION

SCHEMA = "carbon.miner.commitment-post.v1"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
#: D9: the SDK's default mortal era (bittensor/settings.py:22). The signer
#: refuses anything over its own recorded cap.
ERA_PERIOD = 128
#: How long a broadcast may take to reach finality before its outcome is
#: treated as unknown and reconciled by reading (engineering bound).
FINALITY_SECONDS = 180
#: States in which a signature may exist that the chain has not settled.
PENDING = frozenset({"REQUESTED", "BROADCAST", "AMBIGUOUS"})


class PostCode(str, Enum):
    COMMITTED = "commitment_committed"
    ALREADY_ON_CHAIN = "commitment_already_on_chain"
    BAD_DIGEST = "commitment_bad_digest"
    READER_UNAVAILABLE = "commitment_reader_unavailable"
    FEE_UNKNOWN = "commitment_fee_unknown"
    FEE_OVER_CEILING = "commitment_fee_over_ceiling"
    CALL_MISMATCH = "commitment_call_mismatch"
    SIGNATURE_INVALID = "commitment_signature_invalid"
    IN_FLIGHT = "commitment_in_flight"
    AMBIGUOUS = "commitment_ambiguous"
    FAILED = "commitment_failed"
    NOT_OBSERVED = "commitment_not_observed"


DONE = frozenset({PostCode.COMMITTED.value, PostCode.ALREADY_ON_CHAIN.value})
#: The validator's D6 refusal: the on-chain commitment is older than the
#: hotkey's previous admission (built by the Carbon Validator).
STALE = "commitment_stale"


def expected_digest(strategy, contract_digest):
    """L1: what this frozen strategy commits, from the daemon's own function."""
    from carbon.battery.daemon import commitment_digest
    from carbon.reconstruction.challenge_contracts import compile_submission

    admitted = compile_submission(strategy, contract_digest=contract_digest)
    return commitment_digest(
        strategy["challenge_id"],
        admitted.contract_digest,
        admitted.construction.strategy_hash,
    )


def _verify(payload, signature, hotkey):
    from bittensor.sp_core import verify

    return bool(verify(payload, signature, hotkey, 1))


class CommitmentPoster:
    """Posts one hotkey's commitments; one at a time, never resent.

    ``chain`` reads, prepares, estimates and broadcasts (``SdkCommitmentChain``
    or a test fake). ``sign(request)`` reaches the miner's signer
    (``external_signer.request_commitment``). ``state_dir`` keeps the one
    record that makes "never resend" survive a restart.
    """

    def __init__(
        self,
        *,
        hotkey,
        chain,
        sign,
        state_dir,
        netuid=CARBON_NETUID,
        verify=_verify,
        clock=None,
    ):
        self.hotkey, self.netuid = hotkey, netuid
        self.chain, self._sign, self._verify = chain, sign, verify
        self.path = Path(state_dir) / f"commitment-{hotkey}.json"
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
        self._lock = threading.Lock()

    # Records ---------------------------------------------------------------

    def record(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _write(self, **fields):
        row = {
            "schema": SCHEMA,
            "hotkey": self.hotkey,
            "netuid": self.netuid,
            **fields,
            "updated_at": self._clock().isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)
        return row

    def _result(self, code, digest, **extra):
        return {"schema": SCHEMA, "code": code.value, "digest": digest, **extra}

    # L2 --------------------------------------------------------------------

    def plan(self, digest, queued=()):
        """What a post would do, before anything is signed (L2, L3)."""
        if type(digest) is not str or not DIGEST.fullmatch(digest):
            return self._result(PostCode.BAD_DIGEST, digest)
        try:
            current = self.chain.read(self.hotkey)
        except CommitmentUnavailable:
            return self._result(PostCode.READER_UNAVAILABLE, digest)
        on_chain = None if current is None else current["digest"]
        others = sorted({d for d in queued if d != digest})
        return {
            "schema": SCHEMA,
            "digest": digest,
            "netuid": self.netuid,
            "current": on_chain,
            "needed": on_chain != digest,
            "warning": (
                "Posting replaces this hotkey's current commitment on the subnet. "
                "A queued submission for another recipe is then refused "
                "commitment_required until that recipe is committed again."
            ),
            "queued_other_digests": others,
        }

    # L3-L6 -----------------------------------------------------------------

    def post(self, digest, *, recommit=False):
        """Commit ``digest`` once. Returns a closed result; never resends.

        ``recommit`` posts a digest that is already the hotkey's commitment
        again, for a validator that refused it as ``commitment_stale``.
        """
        if type(digest) is not str or not DIGEST.fullmatch(digest):
            return self._result(PostCode.BAD_DIGEST, digest)
        if not self._lock.acquire(blocking=False):
            return self._result(PostCode.IN_FLIGHT, digest)
        try:
            return self._post(digest, recommit)
        finally:
            self._lock.release()

    def _post(self, digest, recommit=False):
        try:
            settled = self._reconcile(digest, recommit)
            if settled is not None:
                return settled
            current = self.chain.read(self.hotkey)
        except CommitmentUnavailable:
            return self._result(PostCode.READER_UNAVAILABLE, digest)
        if not recommit and current is not None and current["digest"] == digest:
            return self._result(
                PostCode.ALREADY_ON_CHAIN, digest, block=current["block"]
            )
        try:
            prepared = self.chain.prepare(self.hotkey, self.netuid, digest, ERA_PERIOD)
            fee = self.chain.estimate(self.hotkey, self.netuid, digest)
        except (ChainFailure, CommitmentUnavailable, OSError):
            return self._result(PostCode.READER_UNAVAILABLE, digest)
        if fee is None:
            return self._result(PostCode.FEE_UNKNOWN, digest)
        unsigned = prepared["unsigned"]
        era = unsigned["era"]
        self._write(
            digest=digest,
            state="REQUESTED",
            nonce=unsigned["nonce"],
            era_current=era["current"] if type(era) is dict else None,
            era_period=era["period"] if type(era) is dict else None,
        )
        request = {
            "netuid": self.netuid,
            "digest": digest,
            "unsigned": {
                key: unsigned[key]
                for key in (
                    "call_data",
                    "era",
                    "nonce",
                    "tip",
                    "genesis_hash",
                    "era_block_hash",
                    "spec_version",
                    "transaction_version",
                    "metadata_hash",
                    "included_in_extrinsic",
                    "included_in_signed_data",
                )
            },
            "fee": fee,
        }
        try:
            answer = self._sign(request)
        except SignerFailure as failure:
            # No signature reached Carbon; whatever the signer did, nothing
            # can be broadcast from here.
            self._write(digest=digest, state="REFUSED", code=str(failure))
            return {"schema": SCHEMA, "code": str(failure), "digest": digest}
        payload = bytes.fromhex(prepared["payload"].removeprefix("0x"))
        call = bytes.fromhex(unsigned["call_data"].removeprefix("0x"))
        refusal = None
        if answer["call"] != call:
            refusal = PostCode.CALL_MISMATCH
        elif not self._verify(payload, answer["signature"], self.hotkey):
            refusal = PostCode.SIGNATURE_INVALID
        else:
            try:
                again = self.chain.estimate(self.hotkey, self.netuid, digest)
            except (ChainFailure, CommitmentUnavailable, OSError):
                again = None
            if again is None:
                refusal = PostCode.FEE_UNKNOWN
            elif (
                again["partial_fee_rao"] + again["deposit_rao"]
                > answer["fee_ceiling_rao"]
            ):
                refusal = PostCode.FEE_OVER_CEILING
        if refusal is not None:
            # The signature dies here, unsent, and with it its era.
            self._write(digest=digest, state="NOT_SENT", code=refusal.value)
            return self._result(refusal, digest)
        self._write(
            digest=digest,
            state="BROADCAST",
            nonce=unsigned["nonce"],
            era_current=era["current"],
            era_period=era["period"],
        )
        try:
            outcome = self.chain.broadcast(prepared, answer["signature"])
        except Exception:  # noqa: BLE001 -- any transport failure is unknown
            outcome = {"outcome": "UNKNOWN"}
        return self._settle(digest, outcome, era)

    def _settle(self, digest, outcome, era):
        kind = outcome.get("outcome")
        if kind == "FAILED":
            self._write(digest=digest, state="FAILED", error=outcome.get("error"))
            return self._result(PostCode.FAILED, digest, error=outcome.get("error"))
        if kind != "FINALIZED":
            self._write(
                digest=digest,
                state="AMBIGUOUS",
                era_current=era["current"],
                era_period=era["period"],
            )
            return self._result(PostCode.AMBIGUOUS, digest)
        try:
            current = self.chain.read(self.hotkey)
        except CommitmentUnavailable:
            current = None
        block = outcome.get("block")
        if (
            current is None
            or current["digest"] != digest
            or (type(block) is int and current["block"] < block)
        ):
            self._write(digest=digest, state="NOT_OBSERVED", block=block)
            return self._result(PostCode.NOT_OBSERVED, digest)
        self._write(
            digest=digest,
            state="COMMITTED",
            block=current["block"],
            fee_rao=outcome.get("fee_rao"),
        )
        return self._result(
            PostCode.COMMITTED,
            digest,
            block=current["block"],
            fee_rao=outcome.get("fee_rao"),
        )

    def _reconcile(self, digest, recommit=False):
        """Settle an earlier request whose outcome is not yet known.

        Returns a result to answer now, or None to go on. Never resends: a
        live signature's era must pass before another request is made.
        """
        row = self.record()
        if row is None or row.get("state") not in PENDING:
            return None
        current = self.chain.read(self.hotkey)
        posted_at = row.get("era_current")
        if (
            current is not None
            and current["digest"] == row["digest"]
            and (
                not recommit
                or type(posted_at) is not int
                or current["block"] >= posted_at
            )
        ):
            self._write(digest=row["digest"], state="COMMITTED", block=current["block"])
            if row["digest"] == digest:
                return self._result(PostCode.COMMITTED, digest, block=current["block"])
            return None
        start, period = row.get("era_current"), row.get("era_period")
        if type(start) is int and type(period) is int:
            try:
                head = self.chain.finalized_block()
            except (ChainFailure, OSError):
                raise CommitmentUnavailable("finalized_head_unavailable") from None
            if head > start + period:
                self._write(digest=row["digest"], state="EXPIRED")
                return None
        return self._result(PostCode.AMBIGUOUS, digest, pending=row["digest"])

    # Agents (D10) -----------------------------------------------------------

    def start(self, digest):
        """Begin a post in the background and tell an agent what the human does.

        The agent can request; only the miner, typing on the signer's
        terminal, can confirm. The agent learns the outcome from ``status``.
        """
        if type(digest) is not str or not DIGEST.fullmatch(digest):
            return self._result(PostCode.BAD_DIGEST, digest)
        if self._lock.locked():
            return self._result(PostCode.IN_FLIGHT, digest)
        threading.Thread(target=self.post, args=(digest,), daemon=True).start()
        return {
            "result": "human_action_required",
            "step": "commit",
            "action": "confirm_commitment",
            "digest": digest,
            "confirm_with": digest[-8:],
            "instruction": (
                "Ask the miner to confirm this commitment in their signer's "
                "terminal by typing the last 8 characters of the digest. The "
                "agent cannot confirm it. Then check status."
            ),
            "for_miner": (
                "Your signer is asking you to post this commitment. Check the "
                "digest, network and fee it shows, then type the last 8 "
                "characters of the digest there to post it."
            ),
            "then": "status",
        }

    def status(self):
        row = self.record()
        return {
            "schema": SCHEMA,
            "in_flight": self._lock.locked(),
            "last": row,
        }


def commit_then_submit(poster, digest, submit, *, recommit=False):
    """L7: submit only once the digest is the hotkey's finalized commitment.

    ``submit()`` returns the intake's answer, or raises an exception whose
    ``code`` is the intake's refusal. A ``commitment_stale`` refusal is not
    retried here: it comes back with an offer to recommit, which the miner
    (or their agent, D10) accepts by calling again with ``recommit=True``.
    """
    outcome = poster.post(digest, recommit=recommit)
    if outcome["code"] not in DONE:
        return {"submitted": False, "commitment": outcome}
    try:
        answer = submit()
    except Exception as refused:
        if getattr(refused, "code", None) != STALE:
            raise
        return {
            "submitted": False,
            "commitment": outcome,
            "code": STALE,
            "offer": {
                "action": "recommit",
                "digest": digest,
                "call": "commit_then_submit(..., recommit=True)",
                "note": (
                    "The validator counts a commitment only if it was posted "
                    "after this hotkey's previous admitted submission. "
                    "Recommitting asks the miner to confirm in the signer's "
                    "terminal; at most one commitment per tempo."
                ),
            },
        }
    return {"submitted": True, "commitment": outcome, "submission": answer}


class _PublicAccount:
    """The public half the SDK's fee query needs (it signs with zeros)."""

    crypto_type = 1

    def __init__(self, address):
        from bittensor.sp_core import ss58_decode

        self.ss58_address = address
        self.public_key = bytes.fromhex(str(ss58_decode(address)).removeprefix("0x"))


def _info(digest):
    """The pinned ``CommitmentInfo``: one ``Raw71`` field of the digest's ASCII."""
    data = digest.encode("ascii")
    return {"fields": [{f"Raw{len(data)}": "0x" + data.hex()}]}


class SdkCommitmentChain:
    """The chain side through the pinned SDK (``bittensor==11.1.0``).

    Every session checks the endpoint's genesis against the context first.
    Unit tests replace this class; the localnet round trip exercises it.
    """

    def __init__(self, context, *, reader=None):
        self.context = context
        self.reader = reader or ChainCommitmentReader(context)

    def _run(self, work, timeout=None):
        async def session():
            if version("bittensor") != SDK_VERSION:
                raise ChainFailure(FailureCode.UNSUPPORTED)
            import bittensor as bt

            substrate = bt.RpcSubstrate(
                self.context.endpoint,
                fallback_endpoints=[],
                archive_endpoints=[],
                retry_forever=False,
            )
            try:
                await substrate.connect()
                if hash256(await substrate.block_hash(0)) != self.context.genesis_hash:
                    raise ChainFailure(FailureCode.IDENTITY)
                job = work(substrate)
                return await (
                    job if timeout is None else asyncio.wait_for(job, timeout)
                )
            finally:
                await substrate.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, session()).result()

    def read(self, hotkey):
        return self.reader.read(hotkey)

    @staticmethod
    async def _compose(substrate, netuid, digest):
        from bittensor._generated import calls

        return await substrate.compose(
            calls.Commitments.set_commitment(netuid=netuid, info=_info(digest))
        )

    def prepare(self, hotkey, netuid, digest, period):
        async def work(substrate):
            call = await self._compose(substrate, netuid, digest)
            unsigned = await substrate.prepare(
                call, address=hotkey, crypto_type=1, period=period, tip=0
            )
            data = unsigned.to_dict()
            return {"unsigned": data, "payload": data["payload"]}

        return self._run(work)

    def estimate(self, hotkey, netuid, digest):
        """``{"partial_fee_rao", "deposit_rao"}``, or None when either is
        unknown. The deposit is the pallet's initial plus one field's."""

        async def work(substrate):
            call = await self._compose(substrate, netuid, digest)
            fee = await substrate.estimate_fee(call, _PublicAccount(hotkey))
            initial = await substrate.constant("Commitments", "InitialDeposit")
            field = await substrate.constant("Commitments", "FieldDeposit")
            if type(initial) is not int or type(field) is not int:
                return None
            return {"partial_fee_rao": int(fee.rao), "deposit_rao": initial + field}

        return self._run(work)

    def broadcast(self, prepared, signature):
        """Submit once and wait for finality. ``FINALIZED`` and ``FAILED``
        (included with a dispatch error) are settled; anything else is
        ``UNKNOWN`` and is reconciled by reading, never resent."""
        from bittensor._transport.contract import UnsignedExtrinsic

        unsigned = UnsignedExtrinsic.from_dict(prepared["unsigned"])

        async def work(substrate):
            result = await substrate.submit_signature(
                unsigned,
                signature,
                wait_for_inclusion=True,
                wait_for_finalization=True,
            )
            block = None
            if result.extrinsic_id:
                block = int(result.extrinsic_id.split("-", 1)[0])
            fee = None if result.fee is None else int(result.fee.rao)
            if result.success:
                return {"outcome": "FINALIZED", "block": block, "fee_rao": fee}
            if result.block_hash is not None:
                message = result.error.message if result.error else result.message
                return {"outcome": "FAILED", "block": block, "error": message}
            return {"outcome": "UNKNOWN"}

        return self._run(work, FINALITY_SECONDS)

    def finalized_block(self):
        async def work(substrate):
            import bittensor as bt

            client = bt.Client(self.context.endpoint, substrate=substrate)
            async with aclosing(client.blocks(finalized=True)) as headers:
                header = await anext(headers)
            return uint(header.number)

        return self._run(work)


def main(argv=None):
    """``python -m carbon.chain.commitment_poster``: one post on testnet 567.

    For the miner, in their own terminal, with ``carbon-miner-signer``
    running for the same hotkey in another. It reads and broadcasts; the
    signer asks the miner before it signs. Mainnet is not offered (D5).
    """
    import argparse

    from carbon.development_testnet.operator import DEFAULT_ENDPOINT, TESTNET_GENESIS

    from .external_signer import connect_signer, request_commitment
    from .models import ChainContext

    parser = argparse.ArgumentParser(prog="python -m carbon.chain.commitment_poster")
    parser.add_argument("--hotkey", required=True, help="the miner's hotkey ss58")
    parser.add_argument("--digest", required=True, help="sha256:<64 hex>")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.home() / ".carbon" / "commitments",
        help="where the never-resend record is kept",
    )
    parser.add_argument("--plan", action="store_true", help="show, post nothing")
    parser.add_argument(
        "--recommit",
        action="store_true",
        help="post again a digest a validator refused as commitment_stale",
    )
    args = parser.parse_args(argv)
    context = ChainContext(
        "testnet", DEFAULT_ENDPOINT, "opentensor", TESTNET_GENESIS, CARBON_NETUID
    )
    chain = SdkCommitmentChain(context)
    poster = CommitmentPoster(
        hotkey=args.hotkey,
        chain=chain,
        sign=lambda request: request_commitment(connect_signer(args.hotkey), request),
        state_dir=args.state_dir,
    )
    plan = poster.plan(args.digest)
    print(json.dumps(plan, indent=2, sort_keys=True), flush=True)
    if args.plan or "code" in plan:
        return 0 if args.plan else 1
    print("Confirm in your signer's terminal.", flush=True)
    result = poster.post(args.digest, recommit=args.recommit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["code"] in DONE else 1


if __name__ == "__main__":
    raise SystemExit(main())
