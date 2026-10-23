"""A catalog backbone that imports timm builds its layers from scratch (Validator,
2026-10-23, GPU lock scope): no pretrained weight, no hub download.

timm drags huggingface_hub and an HTTP client into the pinned GPU image. They stay
inert dependencies under the sandbox's --network none; this holds the other side:
no catalog bundle source asks timm (or anything else) for a pretrained model or a
hub file. Static, over every bundle's source archive.
"""

from __future__ import annotations

import re
import tarfile
from pathlib import Path

import pytest

BUNDLES = Path(__file__).resolve().parents[2] / "carbon/backbone_catalog/bundles"
#: Calls that fetch a pretrained model or a file from a hub or a URL.
FORBIDDEN = re.compile(
    r"pretrained\s*=\s*True|create_model\(|from_pretrained\(|hf_hub_download|"
    r"snapshot_download|huggingface_hub|load_state_dict_from_url|urlretrieve|urlopen|"
    r"requests\.(get|post)|httpx\."
)


def _timm_sources():
    found = []
    for archive in sorted(BUNDLES.glob("*/source.tar.gz")):
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                if not member.isfile() or not member.name.endswith(".py"):
                    continue
                text = bundle.extractfile(member).read().decode("utf-8", "replace")
                if re.search(r"^\s*(import|from)\s+timm\b", text, flags=re.MULTILINE):
                    found.append((archive.parent.name, member.name, text))
    return found


SOURCES = _timm_sources()


def test_the_catalog_has_timm_using_backbones():
    assert SOURCES, "the scan found no timm import, so it checks nothing"


@pytest.mark.parametrize(
    ("entry", "member", "text"),
    SOURCES,
    ids=[f"{entry}:{member}" for entry, member, _ in SOURCES],
)
def test_a_timm_using_source_asks_for_no_pretrained_model_and_no_hub_file(
    entry, member, text
):
    hits = FORBIDDEN.findall(text)
    assert not hits, (entry, member, hits)
    assert not re.search(
        r"^\s*(import|from)\s+(huggingface_hub|requests|httpx)",
        text,
        flags=re.MULTILINE,
    )
