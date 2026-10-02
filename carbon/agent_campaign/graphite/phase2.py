"""GRAPHITE-01 phase 2 runner: fetch, triage, snapshot, list and check cards.

    python -m carbon.agent_campaign.graphite.phase2 fetch    --root DIR [--max-records N]
    python -m carbon.agent_campaign.graphite.phase2 triage   --root DIR --grant GRANT.json \
        (--credential-file PATH | --credential-env ENGY_API_KEY) [--run-id ID] [--max-calls N]
    python -m carbon.agent_campaign.graphite.phase2 triage   --root DIR --dry-run
    python -m carbon.agent_campaign.graphite.phase2 snapshot --root DIR [--dry-run]
    python -m carbon.agent_campaign.graphite.phase2 cards    --root DIR [--unchecked] [--dry-run]
    python -m carbon.agent_campaign.graphite.phase2 check    --root DIR --card ID \
        --checker NAME --verdict CORRECT|EXTRACTION_ERROR|NOT_RELEVANT [--note TEXT]

`DIR` is a private directory outside the repository; nothing here writes
under `docs/`. `fetch` reads the public arXiv API and needs no key.

`triage` is the only paid step. It refuses without an exact, unexpired
spending grant for provider `graphite` (a grant with any `HUMAN_INPUT` value
is refused) and without a credential:

- `--credential-file PATH`: a file holding the Engy key;
- `--credential-env ENGY_API_KEY`: the runner copies the variable's value
  into a 0600 file in a fresh 0700 temporary directory, passes that file's
  path as the credential reference, and deletes it on exit. The key is never
  printed or logged. `CHUTES_API_KEY` is recognised and refused: the Chutes
  adapter is approved (OWNER-GRAPHITE-02) but not yet wired into Graphite.

`--dry-run` runs the same pipeline with a scripted model and a synthetic,
in-memory grant, writing only under `DIR/dry-run`. It sends nothing and
spends nothing; its cards say they are dry-run cards.

`check` records a person's check of one card. It runs only on an interactive
terminal and asks the person to type the card id back.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..grant import GrantError, SpendingGrant
from . import literature_fetch, method_cards, triage
from .model import LiveModel, ModelAccessRefused, ScriptedModel, text
from .provider import PROVIDER

#: The environment variables the runner reads a key from, by adapter family.
CREDENTIAL_ENV = {"ENGY_API_KEY": "engy", "CHUTES_API_KEY": "chutes"}
SNAPSHOT_LABEL = "graphite-phase2-" + literature_fetch.QUERY_SET.version
DRY_RUN_GRANT = {
    "schema": "carbon.agent-campaign.spending-grant.v1",
    "grant_id": "graphite-dry-run-synthetic",
    "provider": PROVIDER,
    "account": "dry-run-no-account",
    "granted_by": "nobody-dry-run",
    "expires_at": "2099-01-01T00:00:00Z",
    "currency": "USD",
    "monetary_ceiling": "1000.00",
    "cleanup_allowance": "0",
    "worst_case_run_cost": "1.00",
    "permitted_runs": 1000,
    "max_concurrency": 1,
    "max_runtime_s": 86400,
    "max_submissions": 1,
}
#: The scripted dry-run reply: well-formed, and plainly not an extraction.
DRY_RUN_REPLY = {
    "relevant": True,
    "method_name": "DRY RUN: not extracted",
    "family": "dry run",
    "construction_claims": [],
    "required_inputs": [],
    "reported_evidence": [],
    "data_regime": "not stated (dry run)",
    "cost": "not stated (dry run)",
    "code_available": False,
    "applicability": "none (dry run; no model read this abstract)",
}


class RunnerRefused(SystemExit):
    def __init__(self, code):
        print(json.dumps({"status": "REFUSED", "reason_code": code}))
        super().__init__(2)


def _root(value):
    root = Path(value).expanduser().resolve()
    repository = Path(__file__).resolve().parents[3]
    if root == repository or repository in root.parents:
        raise RunnerRefused("root_must_be_outside_the_repository")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def load_grant(path):
    try:
        document = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise RunnerRefused("grant_unreadable") from None
    try:
        return SpendingGrant.from_document(document)
    except GrantError as error:
        raise RunnerRefused("grant_refused: " + str(error)) from None


@contextmanager
def credential_file(*, path=None, env=None, environ=os.environ):
    """A credential file reference. From `env`, a 0600 copy removed on exit."""
    if (path is None) == (env is None):
        raise RunnerRefused("one_of_credential_file_or_credential_env_required")
    if path is not None:
        candidate = Path(path)
        if not candidate.is_file():
            raise RunnerRefused("credential_file_missing")
        yield str(candidate)
        return
    if env not in CREDENTIAL_ENV:
        raise RunnerRefused("credential_env_not_recognised")
    if CREDENTIAL_ENV[env] != "engy":
        raise RunnerRefused("chutes_adapter_not_wired_into_graphite_yet")
    value = environ.get(env)
    if not value or not value.strip():
        raise RunnerRefused("credential_env_empty")
    directory = tempfile.mkdtemp(prefix="graphite-credential-")
    try:
        os.chmod(directory, 0o700)
        target = Path(directory) / "key"
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(value.strip())
        yield str(target)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _stores(root, dry_run=False):
    raw = literature_fetch.RawStore(root / "raw")
    backfill_root = root / ("dry-run" if dry_run else "backfill")
    return raw, backfill_root


def fetch(args):
    root = _root(args.root)
    raw, _ = _stores(root)
    client = literature_fetch.ArxivClient()
    try:
        summary = literature_fetch.backfill(
            client,
            raw,
            max_records=args.max_records,
            pages_per_query=args.pages_per_query,
            page_size=args.page_size,
        )
    except literature_fetch.FetchFailed as error:
        summary = {
            "status": error.status,
            "code": error.code,
            "http_status": error.http_status,
            "records": len(raw.addresses()),
        }
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if summary.get("status") != literature_fetch.FAILED_INFRA else 3


def run_triage(args, environ=os.environ):
    root = _root(args.root)
    raw, backfill_root = _stores(root, args.dry_run)
    if args.dry_run:
        if args.grant or args.credential_file or args.credential_env:
            raise RunnerRefused("dry_run_takes_no_grant_or_credential")
        grant = SpendingGrant.from_document(DRY_RUN_GRANT)
        pending = len(
            [
                a
                for a in raw.addresses()
                if not method_cards.CardStore(backfill_root / "cards").done(
                    raw.record(a), a
                )
            ]
        )
        model = ScriptedModel([text(json.dumps(DRY_RUN_REPLY))] * pending)
        backfill = triage.Backfill(
            root=backfill_root,
            raw=raw,
            grant=grant,
            model=model,
            max_calls=args.max_calls,
        )
        summary = backfill.run(args.run_id or "dry-run")
        print(json.dumps({**summary, "dry_run": True}, indent=1, sort_keys=True))
        return 0
    if not args.grant:
        raise RunnerRefused("grant_required")
    grant = load_grant(args.grant)
    with credential_file(
        path=args.credential_file, env=args.credential_env, environ=environ
    ) as reference:
        try:
            model = LiveModel(grant=grant, credential_file=reference, provider=PROVIDER)
            backfill = triage.Backfill(
                root=backfill_root,
                raw=raw,
                grant=grant,
                model=model,
                adapter_id=args.adapter,
                max_calls=args.max_calls,
            )
            summary = backfill.run(args.run_id or "backfill-1")
        except (ModelAccessRefused, triage.BackfillRefused) as error:
            raise RunnerRefused(error.code) from None
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if summary["status"] == "COMPLETED" else 4


def make_snapshot(args):
    root = _root(args.root)
    raw, backfill_root = _stores(root, args.dry_run)
    store = method_cards.CardStore(backfill_root / "cards")
    index, document = method_cards.snapshot(
        store,
        raw,
        label=SNAPSHOT_LABEL + ("-dry-run" if args.dry_run else ""),
        query_set_digest=literature_fetch.QUERY_SET.digest,
    )
    address = method_cards.write_snapshot(store, document)
    print(
        json.dumps(
            {
                "snapshot": address,
                "index_snapshot_digest": index.snapshot_digest,
                "cards": len(index.cards),
                "withheld_protected": len(document["withheld_protected"]),
                "excluded": len(document["excluded"]),
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0


def list_cards(args):
    root = _root(args.root)
    _, backfill_root = _stores(root, args.dry_run)
    store = method_cards.CardStore(backfill_root / "cards")
    print(json.dumps(store.listing(unchecked_only=args.unchecked), indent=1))
    return 0


def check(args, stdin=sys.stdin, confirm=input):
    if not stdin.isatty():
        raise RunnerRefused("human_check_needs_an_interactive_terminal")
    root = _root(args.root)
    _, backfill_root = _stores(root)
    store = method_cards.CardStore(backfill_root / "cards")
    card = store.card(args.card)
    if card is None:
        raise RunnerRefused("unknown_card")
    print(json.dumps(card, indent=1, sort_keys=True))
    try:
        entry = method_cards.record_human_check(
            store,
            args.card,
            checker=args.checker,
            verdict=args.verdict,
            note=args.note,
            confirm=confirm,
        )
    except method_cards.CheckRefused as error:
        raise RunnerRefused(error.code) from None
    print(json.dumps(entry, indent=1, sort_keys=True))
    return 0


def parser():
    top = argparse.ArgumentParser(prog="graphite-phase2")
    commands = top.add_subparsers(dest="command", required=True)
    one = commands.add_parser("fetch")
    one.add_argument("--root", required=True)
    one.add_argument("--max-records", type=int, default=3000)
    one.add_argument("--pages-per-query", type=int, default=None)
    one.add_argument("--page-size", type=int, default=literature_fetch.PAGE_SIZE)
    one.set_defaults(handler=fetch)
    two = commands.add_parser("triage")
    two.add_argument("--root", required=True)
    two.add_argument("--grant")
    two.add_argument("--credential-file")
    two.add_argument("--credential-env", choices=sorted(CREDENTIAL_ENV))
    two.add_argument("--adapter", default="engy-anthropic")
    two.add_argument("--run-id")
    two.add_argument("--max-calls", type=int, default=triage.MAX_CALLS_PER_RUN)
    two.add_argument("--dry-run", action="store_true")
    two.set_defaults(handler=run_triage)
    three = commands.add_parser("snapshot")
    three.add_argument("--root", required=True)
    three.add_argument("--dry-run", action="store_true")
    three.set_defaults(handler=make_snapshot)
    four = commands.add_parser("cards")
    four.add_argument("--root", required=True)
    four.add_argument("--unchecked", action="store_true")
    four.add_argument("--dry-run", action="store_true")
    four.set_defaults(handler=list_cards)
    five = commands.add_parser("check")
    five.add_argument("--root", required=True)
    five.add_argument("--card", required=True)
    five.add_argument("--checker", required=True)
    five.add_argument("--verdict", required=True, choices=method_cards.VERDICTS)
    five.add_argument("--note", default="")
    five.set_defaults(handler=check)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
