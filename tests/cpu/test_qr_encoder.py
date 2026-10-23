"""The Control Center's local QR encoder (scripts/dev/miner_launchpad/qr.js) makes codes a real decoder reads.

The decode check needs OpenCV and Node; without either it is skipped, never faked.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

QR = Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/qr.js"
TEXTS = [
    "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
    "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX",
    "a",
    "hello world",
    "x" * 53,
    "y" * 54,
    "w" * 106,
]
SCRIPT = """
const qr = require(process.argv[1]);
const texts = JSON.parse(process.argv[2]);
console.log(JSON.stringify(texts.map(t => { const e = qr.encode(t); return {t, version: e.version, rows: e.modules.map(r => r.map(x => x ? 1 : 0).join(""))}; })));
"""


def _encode():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed")
    out = subprocess.run(
        [node, "-e", SCRIPT, str(QR), json.dumps(TEXTS)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


def test_the_vendored_generator_is_the_pinned_mit_file_with_its_notice():
    vendored = QR.with_name("qrcode_generator.js").read_bytes()
    assert (
        hashlib.sha256(vendored).hexdigest()
        == "18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780"
    )
    assert b"Copyright (c) 2009 Kazuhiko Arase" in vendored
    assert b"MIT license" in vendored
    notice = QR.with_name("THIRD_PARTY.md").read_text(encoding="utf-8")
    assert "qrcode-generator" in notice and "1.4.4" in notice and "MIT" in notice


def test_the_encoder_picks_the_smallest_version_and_refuses_too_long_text():
    items = _encode()
    assert [item["version"] for item in items] == [3, 3, 1, 1, 3, 4, 5]
    assert all(len(item["rows"]) == 17 + 4 * item["version"] for item in items)
    node = shutil.which("node")
    refused = subprocess.run(
        [node, "-e", "require(process.argv[1]).encode('q'.repeat(107))", str(QR)],
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0 and "too long" in refused.stderr


def test_a_real_decoder_reads_every_code_back():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    for item in _encode():
        rows = [[int(c) for c in row] for row in item["rows"]]
        n, scale, quiet = len(rows), 12, 4
        image = np.full(((n + 2 * quiet) * scale,) * 2, 255, np.uint8)
        for r in range(n):
            for c in range(n):
                if rows[r][c]:
                    image[
                        (r + quiet) * scale : (r + quiet + 1) * scale,
                        (c + quiet) * scale : (c + quiet + 1) * scale,
                    ] = 0
        value, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        assert value == item["t"], item["t"]
