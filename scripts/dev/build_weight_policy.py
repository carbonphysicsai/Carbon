"""Build the next mainnet weight policy document from its base and the list of OPEN exams (owner G-LEAD-67 / 68; Lead 6357).

    python -I -B scripts/dev/build_weight_policy.py BASE SPEC.json [OUT_DIR]

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


def main(argv):
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
