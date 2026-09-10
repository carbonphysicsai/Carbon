"""Closed synthetic A7/A8 fixture composition, reused offline and on localnet."""

import itertools
import time
import uuid
from dataclasses import replace
from pathlib import Path

from test_traineval_stub import (
    SCORE_PACK_ROOT,
    _environment,
    _fixture_registry,
    _limits,
    _provider,
    _service,
    _strategy,
)

from carbon.candidates.model import (
    CandidateCode,
    CandidateFailure,
    FixtureEvaluationContext,
)
from carbon.candidates.service import FixtureCandidateService
from carbon.candidates.store import CandidateJournal
from carbon.fees import FeePolicyKey, FixtureSubmissionPolicy, SubmissionService
from carbon.registry import ChallengeKey
from carbon.scoring import load_score_pack
from carbon.traineval import FixtureStubProfile
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import message


class PinnedRequestView:
    """One server-observed snapshot for a single in-process ingress exchange."""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def observe(self, *, minimum_finalized_block):
        assert self.snapshot.finalized_block >= minimum_finalized_block
        return self.snapshot


class Exam:
    def __init__(self, root, receipts, adapter, receiver, verifier, suffix=None):
        self.profile = FixtureStubProfile(
            localnet_fixture=None if suffix is None else "a5_fixture_net5_" + suffix
        )
        key = self.profile.challenge_key
        filename = (
            "a5_fixture_v1.json" if suffix is None else key.challenge_id + "_v1.json"
        )
        self.pack = load_score_pack(
            SCORE_PACK_ROOT, filename, self.profile.score_pack_pin()
        )
        registry = _fixture_registry(Path(root))
        if suffix:
            original = registry.load("a5_fixture", "fixture-1.0")
            registry.save(
                replace(
                    original,
                    challenge_id=key.challenge_id,
                    qualification=replace(
                        original.qualification, challenge_id=key.challenge_id
                    ),
                )
            )
        env = _environment()
        self.journal = CandidateJournal(
            receipts, FixtureEvaluationContext(self.pack.pack_pin, env), _limits()
        )
        identifiers = itertools.count(1)
        submissions = SubmissionService(
            _limits(),
            registry,
            FixtureSubmissionPolicy(
                FeePolicyKey("net5-synthetic"),
                1703,
                2,
                self.profile.generator_version_required,
                self.profile.generator_digest_required,
                self.profile.scoring_version,
                self.profile.scoring_digest,
                env,
            ),
            _uuid_factory=lambda: uuid.UUID(
                f"123e4567-e89b-42d3-a456-{next(identifiers):012x}"
            ),
        )
        self.service = FixtureCandidateService(
            self.journal,
            submissions,
            _service(
                profile=self.profile,
                score_pack=self.pack,
                provider=_provider(b"NET-5 conspicuous synthetic integration"),
            ),
        )
        self.receipts, self.adapter, self.receiver, self.verifier = (
            receipts,
            adapter,
            receiver,
            verifier,
        )
        self.sequence = 0

    async def commit(self, variant, signer, *, hotkey=None):
        self.sequence += 1
        snapshot = await self.adapter.observe(
            minimum_finalized_block=self.receipts.minimum_block()
        )
        key = self.profile.challenge_key
        body = message(
            self.receipts.context,
            snapshot.snapshot_id,
            key,
            session="net5",
            request=f"{key.challenge_id}:{self.sequence}",
            tool="submit",
            fields={
                "challenge_id": key.challenge_id,
                "challenge_version": key.version,
                "strategy": _strategy(
                    challenge_id=key.challenge_id,
                    parameters={"synthetic_variant": variant},
                ),
            },
        )
        now = time.time_ns()
        # The offline owner test supplies a signer double and synthetic clock.
        if hotkey is not None:
            now = snapshot.timestamp_ms * 1000000 + self.receipts.highest_receipt() + 1
        headers = signer(body, now, hotkey)
        gateway = AuthenticatedGateway(
            self.receipts.context,
            ChallengeKey(key.challenge_id, key.version),
            self.receiver,
            PinnedRequestView(snapshot),
            self.verifier,
            self.receipts,
            clock_ns=lambda: now,
        )
        receipt = (await gateway.receive(body, headers)).receipt
        return self.journal.commit(receipt.ref, body)

    def evaluate(self, ref):
        try:
            return self.service.evaluate(ref)
        except CandidateFailure as error:
            if error.code is not CandidateCode.NOT_ACCEPTED:
                raise
            assert self.journal.state(ref) == "REJECTED_SCIENCE"
            return None
