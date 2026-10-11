"""Shared checks for the registered evidence entrypoints (EVIDENCE-ENTRYPOINTS-01).

Every entrypoint refuses before any solve unless:
- the plan or manifest file's sha256 equals the registered value, and
- the pinned solver image is present locally, identified by its digest
  (repository digest or image id), never by a mutable tag.

Refusals are typed (`Refused.code`) and exit 2; infrastructure failures exit 1.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class Refused(Exception):
    """A typed refusal before any solve."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_plan(path, expected_sha256):
    path = Path(path) if Path(path).is_absolute() else ROOT / path
    if not path.exists():
        raise Refused("PLAN_MISSING", str(path))
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise Refused(
            "PLAN_SHA256_MISMATCH", f"{path.name}: {actual} != {expected_sha256}"
        )
    return path


def image_identity(ref, inspect=None):
    """(image id, repository digests) of a local image, or None if absent."""
    run = inspect or (
        lambda r: subprocess.run(
            ["docker", "image", "inspect", r],
            capture_output=True,
            text=True,
            check=False,
        )
    )
    done = run(ref)
    if done.returncode != 0:
        return None
    data = json.loads(done.stdout)[0]
    return data.get("Id"), [
        d.split("@", 1)[1] for d in data.get("RepoDigests") or [] if "@" in d
    ]


def require_image(ref, digest, inspect=None):
    """Refuse unless the local image is the pinned one (digest = sha256:...)."""
    found = image_identity(ref, inspect)
    if found is None:
        raise Refused("IMAGE_ABSENT", ref)
    image_id, repo_digests = found
    if digest != image_id and digest not in repo_digests:
        raise Refused(
            "IMAGE_DIGEST_MISMATCH",
            f"{ref}: id {image_id}, repo digests {repo_digests}",
        )
    return ref


def read_jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]


def write_jsonl(path, rows):
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    Path(path).write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()
