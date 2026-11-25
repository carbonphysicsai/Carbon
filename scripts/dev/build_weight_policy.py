"""Build the next mainnet weight policy document from its base and the list of OPEN exams (owner G-LEAD-67 / 68; Lead 6357).

    python -I -B scripts/dev/build_weight_policy.py BASE SPEC.json [OUT_DIR]
    python -I -B scripts/dev/build_weight_policy.py --from-registry BASE VERSION [REGISTRY.json]

The pay list is a digest-pinned file, GENERATED here and never read from a registry at run time: who is paid changes
only by a new policy version with its own review and owner authorization. SPEC.json, exactly:

- ``version``: the new version's name (never a registered one);
- ``membership_note``: what changed and on whose words;
- ``open``: the Challenges that are open, in order; each is paid an equal share (one 100 %, two 50/50, three thirds);
- ``qualified_sealed``: for EVERY open Challenge ``{"record_sha256", "evaluation_pack_digests"}``, as the loader reads it.

Everything else (network, netuid, authority, decay, burn UID, cadence, baselines, self-improvement factor) is the base's,
byte for byte; a Challenge new to the list has no baseline. Refused: an open Challenge no registry names, one with no
qualification, one listed twice, a qualification for a Challenge that is not open, and dropping a pack the base
qualifies for a Challenge that stays open (its king would stop being payable: the hand-over between two exam versions
needs both packs). A missing digest is refused, never filled.

It writes ``<version>.json`` and prints the registry line to add. It signs, applies and authorizes nothing.

``--from-registry`` (owner G-LEAD-100, the rule in `RULE`) is a DRY RUN: it makes the same document from the exam registry's
``launch`` rows (`spec_from_rows`), prints it with what would change, and writes nothing. A Challenge is paid while at least
one of its versions is launched (two launched versions of one Challenge are ONE share). Refused, never guessed: a base
Challenge with no ``launch`` row; a base Challenge whose every version is retired, because what its king is paid meanwhile is
the owner's word (NOT given: `retired_king_undecided`); a pack the base qualifies that no launched version names
(`live_pack_dropped`); launched versions of one Challenge that name different owner records; a refused row; a row of an
unregistered version. Each document still needs the owner's yes before it is registered or pointed to.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY_DIR = ROOT / "carbon" / "rewards" / "weight_policies"
SPEC_FIELDS = {"version", "membership_note", "open", "qualified_sealed"}


#: The owner's rule (G-LEAD-100, 2026-11-25, approved as shown to the owner).
RULE = (
    "Weights: every launched exam in the exam registry is paid an equal share; an exam joins at its launch and leaves when "
    "it is retired; each change is a new policy file that I approve before it goes live."
)


class PolicyRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def digest(document):
    """The registry's digest of a policy document (`winner_decay.load_policy`)."""
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def render(document):
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build(base, spec, *, directory=POLICY_DIR, registered=None):
    """The new policy document (a dict), or `PolicyRefused`."""
    from carbon.rewards import winner_decay

    if registered is None:
        from carbon.challenge_validator.exam_cap import registered_challenges

        registered = registered_challenges()
    directory = Path(directory)
    winner_decay.load_policy(base, directory)  # refuses an altered base
    document = json.loads((directory / f"{base}.json").read_bytes())
    versions = json.loads((directory / "registry.json").read_bytes())["versions"]
    if type(spec) is not dict or set(spec) != SPEC_FIELDS:
        raise PolicyRefused("spec_fields")
    version, note, opened = spec["version"], spec["membership_note"], spec["open"]
    if type(version) is not str or not version or version in versions:
        raise PolicyRefused("version_already_registered")
    if type(note) is not str or not note.strip():
        raise PolicyRefused("membership_note_missing")
    if type(opened) is not list or not opened or len(set(opened)) != len(opened):
        raise PolicyRefused("open_list")
    if set(opened) - set(registered):
        raise PolicyRefused("open_challenge_unregistered")
    qualified = spec["qualified_sealed"]
    if not winner_decay._qualified_ok(qualified, opened):
        raise PolicyRefused("qualified_sealed_malformed")
    if set(qualified) != set(opened):
        raise PolicyRefused("open_challenge_not_qualified")
    for challenge, before in document.get(winner_decay.QUALIFIED_SEALED, {}).items():
        kept = qualified.get(challenge, {}).get("evaluation_pack_digests", ())
        if challenge in opened and not set(before["evaluation_pack_digests"]) <= set(
            kept
        ):
            raise PolicyRefused("live_pack_dropped")
    baselines = document["baselines"]
    document.update(
        version=version,
        membership_note=note,
        challenges=opened,
        baselines={challenge: baselines.get(challenge) for challenge in opened},
        qualified_sealed=qualified,
    )
    return document


def spec_from_rows(base_document, rows, *, version, membership_note):
    """The ``SPEC.json`` the exam registry's launch rows state, as a pure function of them.

    ``rows``: ``{(challenge id, version): launch}``. The base's Challenges keep their order; those that join follow, by id.
    """
    launched, retired = {}, set()
    for (challenge, _version), launch in sorted(rows.items()):
        if launch["state"] == "launched":
            launched.setdefault(challenge, []).append(launch["qualified_sealed"])
        else:
            retired.add(challenge)
    before = base_document["challenges"]
    for challenge in before:
        if challenge not in launched:
            code = (
                "retired_king_undecided"
                if challenge in retired
                else "base_challenge_has_no_launch_row"
            )
            raise PolicyRefused(f"{code}:{challenge}")
    if not launched:
        raise PolicyRefused("no_launched_exam")
    qualified = {}
    for challenge, blocks in launched.items():
        records = {block["record_sha256"] for block in blocks}
        if len(records) != 1:
            raise PolicyRefused(f"launched_records_differ:{challenge}")
        packs = [p for block in blocks for p in block["evaluation_pack_digests"]]
        qualified[challenge] = {
            "record_sha256": records.pop(),
            "evaluation_pack_digests": list(dict.fromkeys(packs)),
        }
    return {
        "version": version,
        "membership_note": membership_note,
        "open": [*before, *sorted(set(launched) - set(before))],
        "qualified_sealed": qualified,
    }


def launch_rows(registry=None):
    """The exam registry's launch rows, or `PolicyRefused`: a refused row, or a row no registered version answers for, is
    never read as an exam that is not launched. ``registry``: another registry file (a proposal), added to this process
    only."""
    from carbon.challenge_registry import exam_registry

    if registry is not None:
        try:
            exam_registry.install(registry)
        except exam_registry.ExamRegistryRefused as failure:
            raise PolicyRefused(f"exam_registry_refused:{failure}") from failure
    for name in sorted(exam_registry.refused()):
        raise PolicyRefused(f"exam_row_refused:{name}")
    named = {
        key for key, (row, _digest) in exam_registry._ROWS.items() if "launch" in row
    }
    rows = {
        key: exam_registry.field(*key, "launch") for key in exam_registry.keys("launch")
    }
    for key in sorted(named - set(rows)):
        raise PolicyRefused(f"launched_version_unregistered:{' '.join(key)}")
    return rows


def dry_run(base, version, *, rows, directory=POLICY_DIR, registered=None):
    """The document the rows would make and what it changes, as a printable dict. Nothing is written."""
    from carbon.rewards.core import Q12

    before = json.loads((Path(directory) / f"{base}.json").read_bytes())
    note = f"Built from the exam registry's launch rows on {base} (owner G-LEAD-100): {RULE}"
    spec = spec_from_rows(before, rows, version=version, membership_note=note)
    document = build(base, spec, directory=directory, registered=registered)
    share = Q12 // len(document["challenges"])
    return {
        "dry_run": "nothing is written, registered, signed or pointed to; the owner approves each policy file",
        "base": base,
        "rows": {" ".join(key): value["state"] for key, value in sorted(rows.items())},
        "joins": [c for c in document["challenges"] if c not in before["challenges"]],
        "share_q12_before": Q12 // len(before["challenges"]),
        "share_q12": share,
        "burned_dust_q12": Q12 - share * len(document["challenges"]),
        "undecided": "a retired exam's king's pay until the owner says: a base exam with no launched version refuses",
        "digest": digest(document),
        "document": document,
    }


def main(argv):
    if argv[0] == "--from-registry":
        rows = launch_rows(argv[3] if len(argv) > 3 else None)
        print(json.dumps(dry_run(argv[1], argv[2], rows=rows), indent=2))
        return
    base, spec = argv[0], json.loads(Path(argv[1]).read_bytes())
    out = Path(argv[2]) if len(argv) > 2 else POLICY_DIR
    document = build(base, spec)
    path = out / f"{document['version']}.json"
    if path.exists():
        raise PolicyRefused("policy_file_exists")
    path.write_bytes(render(document))
    print(json.dumps({document["version"]: digest(document)}))


if __name__ == "__main__":
    main(sys.argv[1:])
