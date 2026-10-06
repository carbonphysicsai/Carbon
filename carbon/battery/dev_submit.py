"""Graphite's narrow door to a hidden deployment on another host (VALIDATOR-19
slice 0; the owner, 2026-10-06).

Hidden material (cases, references, tuning sets) lives on a separate host
that no agent session can reach. Agent accounts on the operator's PC are in
the `docker` group and can run `wsl.exe -u root`, so same-host accounts
cannot isolate it. Graphite reaches that host only through this door:
- **Request.** One JSON request names the run, the role (`constructor` or
  `baseline`), the strategy and the contract digest. It is signed with
  Graphite's submitter key: ed25519, a key file on Graphite's side whose
  public key the host pins.
- **Answer.** The deployment's own sealed miner outcome, through
  `deployment.evaluate` and `hidden_score.HiddenPool`, exactly as in process.
  The operator record is written on the host, under its service account, and
  never returned.
- **Identity.** The host derives the identity itself, `graphite-dev:<run>:<role>`.
  The receipt block is the host's own finalized block, so the caller supplies
  neither.
- **Who it serves.** Only a deployment that opted in (`development_only`) and
  names its `service_account`, and only while running as that account.

**What the key allows.** Holding the submitter key lets a caller submit and
read sealed outcomes, which is what a mainnet miner can do. It never reads a
case, reference, prediction, score or operator record.

**Freshness.** A request is accepted within 60 s of its issue time and once
only: its nonce is recorded in an owner-only append-only file.

**Exposure.** The door binds loopback unless the configuration names the
owner's recorded exposure decision and terminates TLS, using the intake's own
rule (`intake.require_exposure`).

Security-sensitive (AGENTS.md §13). DEVELOPMENT only: no weight, settlement
or miner path reads this module's results.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import stat
import sys
import time
from pathlib import Path

SCHEMA = "carbon.battery.dev-submit.v1"
CONFIG_SCHEMA = "carbon.battery.dev-submit-config.v1"
DOMAIN = b"carbon.battery.dev-submit.v1\x00"
PATH = "/carbon/v1/dev/battery"
MAX_SKEW_S = 60
MAX_BODY = 64 * 1024
ROLES = ("constructor", "baseline")
RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,96}")
_REQUEST_KEYS = frozenset(
    {"schema", "run_id", "role", "strategy", "contract_digest", "issued_at", "nonce"}
)


class DevSubmitRefused(ValueError):
    """A typed refusal; its code names no hidden material."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _owner_only_file(path):
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise DevSubmitRefused("dev_submit_file_not_owner_only")
    return path


# -- the submitter key (Graphite's side) ----------------------------------------------------


class SubmitterKey:
    """Graphite's ed25519 submitter key. Its private bytes never print."""

    __slots__ = ("_key", "public_key")

    def __init__(self, raw):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        key = Ed25519PrivateKey.from_private_bytes(raw)
        object.__setattr__(self, "_key", key)
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        object.__setattr__(self, "public_key", public.hex())

    def __setattr__(self, name, value):
        raise AttributeError("a submitter key is immutable")

    def __repr__(self):
        return "SubmitterKey(<redacted>)"

    @staticmethod
    def create(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(32))
        return SubmitterKey.load(path)

    @staticmethod
    def load(path):
        raw = _owner_only_file(path).read_bytes()
        if len(raw) != 32:
            raise DevSubmitRefused("dev_submit_key_malformed")
        return SubmitterKey(raw)

    def sign(self, body):
        return self._key.sign(DOMAIN + _canonical(body)).hex()


def request(
    key, *, run_id, role, strategy, contract_digest, now=None, score_variant=None
):
    """One signed request, ready to POST. `score_variant` names the run's
    registered development score variant, which the host applies to the
    hidden score operator-side; it is left out without one."""
    body = {
        "schema": SCHEMA,
        "run_id": run_id,
        "role": role,
        "strategy": strategy,
        "contract_digest": contract_digest,
        "issued_at": int(time.time() if now is None else now),
        "nonce": os.urandom(16).hex(),
    }
    if score_variant is not None:
        body["score_variant"] = score_variant
    return {"body": body, "signature": key.sign(body)}


def verify(signed, public_key_hex, *, now=None):
    """The request body, when its signature is the pinned key's and it is
    fresh and well formed; refused by code otherwise."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if type(signed) is not dict or set(signed) != {"body", "signature"}:
        raise DevSubmitRefused("dev_submit_malformed")
    body = signed["body"]
    if type(body) is not dict or set(body) - {"score_variant"} != _REQUEST_KEYS:
        raise DevSubmitRefused("dev_submit_malformed")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(signed["signature"]), DOMAIN + _canonical(body)
        )
    except (InvalidSignature, ValueError, TypeError):
        raise DevSubmitRefused("dev_submit_signature") from None
    if (
        body["schema"] != SCHEMA
        or type(body["run_id"]) is not str
        or not RUN_ID.fullmatch(body["run_id"])
        or body["role"] not in ROLES
        or type(body["strategy"]) is not dict
        or type(body["contract_digest"]) is not str
        or type(body["issued_at"]) is not int
        or type(body["nonce"]) is not str
        or not re.fullmatch(r"[0-9a-f]{32}", body["nonce"])
        or type(body.get("score_variant", "")) is not str
    ):
        raise DevSubmitRefused("dev_submit_malformed")
    if abs((time.time() if now is None else now) - body["issued_at"]) > MAX_SKEW_S:
        raise DevSubmitRefused("dev_submit_stale")
    return body


# -- the host's side ------------------------------------------------------------------------


def running_account():
    import pwd

    return pwd.getpwuid(os.geteuid()).pw_name


def require_service_account(deployment_config, *, account=None):
    """The hidden deployment's state is touched only by its service account
    (slice 0's guard): refused when it names none, or another one."""
    named = deployment_config.get("service_account")
    if type(named) is not str or not named:
        raise DevSubmitRefused("dev_submit_needs_a_service_account")
    if (running_account() if account is None else account) != named:
        raise DevSubmitRefused("dev_submit_wrong_account")


class DevSubmitService:
    """The host's side: verify, then submit through `HiddenPool`.

    `target` is the started `BatteryValidator`; `clock()` is the host's own
    finalized block. Operator records go under `operator_dir/<run>/`, which
    is owner-only.
    """

    def __init__(
        self, target, *, public_key, clock, nonce_file, operator_dir, now=None
    ):
        if not getattr(target, "development_only", False):
            raise DevSubmitRefused("dev_submit_needs_a_development_only_deployment")
        self.target, self.public_key, self.clock = target, public_key, clock
        self.nonce_file, self.now = Path(nonce_file), now
        self.operator_dir = Path(operator_dir)
        self.operator_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.lstat(self.operator_dir).st_mode & 0o077:
            raise DevSubmitRefused("dev_submit_file_not_owner_only")

    def _spend_nonce(self, nonce):
        seen = set()
        if self.nonce_file.exists():
            seen = set(_owner_only_file(self.nonce_file).read_text().split())
        if nonce in seen:
            raise DevSubmitRefused("dev_submit_replay")
        fd = os.open(self.nonce_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as handle:
            handle.write(nonce + "\n")

    def _variant(self, contract_digest):
        from carbon.reconstruction import capability_registry as registry

        if not registry.is_development_variant(contract_digest):
            return None
        from carbon.reconstruction import development_variants as dv

        try:
            return dv.registered(contract_digest)
        except dv.VariantRefused:
            raise DevSubmitRefused("dev_submit_variant_unregistered") from None

    def _score_variant(self, version):
        """The run's development score variant, resolved from this host's own
        registry (`score_variant.resolve`), or None."""
        if version is None:
            return None
        from carbon.agent_campaign.graphite import score_variant as sv
        from carbon.challenge_validator.scoring import scoring_for

        try:
            return sv.resolve(
                version, scoring_for(self.target.identities()["challenge"]["id"])
            )
        except sv.ScoreVariantRefused as refused:
            raise DevSubmitRefused(refused.code) from None

    def handle(self, signed):
        """The sealed view for one signed request. Never an operator record."""
        from carbon.agent_campaign.graphite.hidden_score import (
            HiddenPool,
            HiddenPoolRefused,
        )

        now = self.now() if callable(self.now) else None
        body = verify(signed, self.public_key, now=now)
        self._spend_nonce(body["nonce"])
        try:
            pool = HiddenPool(
                self.target,
                run_id=body["run_id"],
                clock=self.clock,
                variant=self._variant(body["contract_digest"]),
                score_variant=self._score_variant(body.get("score_variant")),
            )
        except HiddenPoolRefused as refused:
            raise DevSubmitRefused(refused.code) from None
        if body["contract_digest"] != pool.contract_digest:
            raise DevSubmitRefused("dev_submit_contract_not_served")
        kind = "baseline" if body["role"] == "baseline" else "proposal"
        view, operator = pool.submit(kind, body["strategy"])
        if operator is not None:
            folder = self.operator_dir / body["run_id"]
            folder.mkdir(mode=0o700, exist_ok=True)
            path = folder / (operator["submission_id"] + ".json")
            if not path.exists():
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(_canonical({**operator, "role": body["role"]}))
        return view

    def report(self, run_id):
        """The run's hidden-pool report, on the host (operator only)."""
        from carbon.agent_campaign.graphite.hidden_score import report

        folder = self.operator_dir / run_id
        records = [
            json.loads(_owner_only_file(p).read_bytes())
            for p in sorted(folder.glob("*.json"))
        ]
        return report(records)


# -- Graphite's side: a HiddenPool that reaches the host ------------------------------------


class RemoteHiddenPool:
    """`HiddenPool`'s submit, across the wire. It returns only the host's
    sealed view; the operator record stays on the host (None here)."""

    def __init__(
        self,
        url,
        key,
        *,
        run_id,
        challenge_id,
        contract_digest,
        variant=None,
        ca=None,
        post=None,
        score_variant=None,
    ):
        """`ca` pins the host's own certificate (a public file, copied from
        the host): only that certificate is trusted, and its subject
        alternative name must match the URL's host. Without it the system's
        trust store decides, so a self-signed host is refused."""
        if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
            raise DevSubmitRefused("dev_submit_needs_tls")
        if type(key) is not SubmitterKey:
            raise DevSubmitRefused("dev_submit_key_required")
        self.url, self.key, self.run_id = url.rstrip("/") + PATH, key, run_id
        self.challenge_id, self.contract_digest = challenge_id, contract_digest
        self.variant = variant
        self.score_variant = score_variant
        if post is None:
            context = None
            if ca is not None:
                try:
                    context = ssl.create_default_context(cafile=str(ca))
                except (OSError, ssl.SSLError):
                    raise DevSubmitRefused("dev_submit_ca_unreadable") from None

            def post(url, body):
                return _post(url, body, context=context)

        self._post = post

    def submit(self, kind, strategy):
        from carbon.agent_campaign.graphite.hidden_score import _view

        signed = request(
            self.key,
            run_id=self.run_id,
            role="baseline" if kind == "baseline" else "constructor",
            strategy=strategy,
            contract_digest=(
                self.contract_digest if self.variant is None else self.variant.digest
            ),
            score_variant=self.score_variant,
        )
        try:
            answer = self._post(self.url, _canonical(signed))
        except (OSError, ValueError):
            return _view("UNAVAILABLE", code="dev_submit_unreachable"), None
        if type(answer) is not dict or "view" not in answer:
            code = "dev_submit_answer"
            if type(answer) is dict:
                code = str(answer.get("refused", code))
            return _view("UNAVAILABLE", code=code), None
        return answer["view"], None


def _post(url, body, *, context=None, timeout=600.0):
    import urllib.request

    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return json.loads(response.read(MAX_BODY))
    except urllib.error.HTTPError as failure:
        return json.loads(failure.read(MAX_BODY) or b"{}")


# -- the host's HTTP door -------------------------------------------------------------------


def serve(service, config, *, repository):
    """Serve `PATH` until stopped."""
    make_server(service, config, repository=repository).serve_forever()


def make_server(service, config, *, repository):
    """The door's server, not yet serving. Loopback unless the owner's
    exposure record and TLS are configured (`intake.require_exposure`)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from .intake import require_exposure, tls_context

    require_exposure(config, repository=repository)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # never log a peer, path or body
            return

        def _answer(self, status, value):
            body = _canonical(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != PATH:
                return self._answer(404, {"refused": "not_found"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                return self._answer(413, {"refused": "dev_submit_body"})
            try:
                signed = json.loads(self.rfile.read(length))
                return self._answer(200, {"view": service.handle(signed)})
            except DevSubmitRefused as refused:
                return self._answer(400, {"refused": refused.code})
            except ValueError:
                return self._answer(400, {"refused": "dev_submit_malformed"})

    server = ThreadingHTTPServer((config["host"], config["port"]), Handler)
    context = tls_context(config)
    if context is not None:
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.dev_submit")
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen", help="Graphite's side: create the submitter key")
    keygen.add_argument("--out", required=True)
    run = sub.add_parser("serve", help="the host's side: serve the door")
    run.add_argument("--config", required=True)
    rep = sub.add_parser("report", help="the host's side: a run's hidden report")
    rep.add_argument("--config", required=True)
    rep.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            key = SubmitterKey.create(args.out)
            print(json.dumps({"public_key": key.public_key}))
            return 0
        service, config = _from_config(args.config)
        if args.command == "report":
            print(json.dumps(service.report(args.run), sort_keys=True, indent=1))
            return 0
        serve(service, config, repository=Path(__file__).resolve().parents[2])
    except DevSubmitRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    return 0


def _from_config(path):
    """The door's owner-only configuration: the deployment config, the pinned
    submitter public key, the nonce file, the operator directory, and the
    bind (host, port, exposure_record, tls_cert, tls_key)."""
    from carbon.agent_campaign.graphite.phase3 import finalized_block_clock
    from carbon.chain.models import ChainContext
    from carbon.development_testnet.operator import DEFAULT_ENDPOINT, TESTNET_GENESIS

    from . import deployment

    config = json.loads(_owner_only_file(path).read_bytes())
    if type(config) is not dict or config.get("schema") != CONFIG_SCHEMA:
        raise DevSubmitRefused("dev_submit_config_schema")
    config.setdefault("host", "127.0.0.1")
    config.setdefault("port", 8468)
    deployment_config = deployment.load_config(config["deployment"])
    require_service_account(deployment_config)
    target = deployment.validator(
        Path(config["deployment"]), repository=Path(__file__).resolve().parents[2]
    )
    clock = finalized_block_clock(
        ChainContext(
            "testnet", DEFAULT_ENDPOINT, "bittensor-official-test", TESTNET_GENESIS, 567
        )
    )
    service = DevSubmitService(
        target,
        public_key=config["submitter_public_key"],
        clock=clock,
        nonce_file=config["nonce_file"],
        operator_dir=config["operator_dir"],
    )
    return service, config


__all__ = [
    "DevSubmitRefused",
    "DevSubmitService",
    "RemoteHiddenPool",
    "SubmitterKey",
    "request",
    "require_service_account",
    "verify",
]


if __name__ == "__main__":
    sys.exit(main())
