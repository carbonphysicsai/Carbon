"""The analysis image's identity binds the builder file's own bytes (`research_image.runtime_document`,
``builder_digest``), so ANY edit to carbon/development_session/research_image.py makes every installed analysis image
refuse at receiver start ('analysis runtime source binding differs', `verify_image`). Live 116, 23 Nov 2026: a timeout
constant change (009a65fd) took the door down at an apply and was rolled back. This pin makes such an edit a visible,
planned change: whoever edits the file updates the sha below in the SAME head, with a rebuild plan for every door's and
miner's analysis image in its row.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from carbon.development_session import research_image

#: research_image.py as the live 116 analysis image was built against (main 6cfdf94b).
PINNED_SHA256 = "cd066365b0bcf35e555e14ea8b0f30442e41eb3116741d24312c33f0c66f4c2c"


def test_the_builder_bytes_that_every_analysis_image_binds_are_pinned():
    body = Path(research_image.__file__).read_bytes()
    assert hashlib.sha256(body).hexdigest() == PINNED_SHA256, (
        "research_image.py changed: every installed analysis image will refuse at start; "
        "update PINNED_SHA256 only together with a rebuild plan"
    )
    assert research_image.runtime_document("sha256:" + "0" * 64)["builder_digest"]
