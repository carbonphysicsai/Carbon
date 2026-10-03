"""The miner's wiring guide, read from this checkout and served locally.

`docs/development/MINER_REMOTE_SETUP.md` is the one source. Setup's "Where's
your GPU?" cards show its per-provider sections inline, and the Control
Center renders the whole guide from the controller (LINKONLY-D10), so the
page fetches nothing from the internet and cannot drift from the document.

The parser reads exactly the Markdown the guide uses: headings, paragraphs,
nested lists, a table, bold, inline code and links. It returns data the page
renders as text, never HTML. A link keeps only its label, and an anchor when
it points within the guide; nothing points off the machine.
"""

from __future__ import annotations

import re
from pathlib import Path

SCHEMA = "carbon.control-center.guide.v1"
REPO = Path(__file__).resolve().parents[3]
#: The guides the controller serves, by name. These are the only paths read.
GUIDES = {"remote-setup": "docs/development/MINER_REMOTE_SETUP.md"}

_HEADING = re.compile(r"(#{1,6}) +(.+?)\s*$")
_ITEM = re.compile(r"( *)(?:[-*]|(\d+)\.) +(.*)$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE_OR_LINK = re.compile(r"`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)")
_RULE = re.compile(r"\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{0,}:?\s*\|?")


def _span(text, strong, *, code=False, anchor=None):
    span = {"text": text}
    if strong:
        span["strong"] = True
    if code:
        span["code"] = True
    if anchor:
        span["anchor"] = anchor
    return span


def _spans(text, strong):
    out, at = [], 0
    for match in _CODE_OR_LINK.finditer(text):
        out.append(_span(text[at : match.start()], strong))
        if match.group(1) is not None:
            out.append(_span(match.group(1), strong, code=True))
        else:
            href = match.group(3)
            anchor = href[1:] if href.startswith("#") else None
            out.append(_span(match.group(2), strong, anchor=anchor))
        at = match.end()
    out.append(_span(text[at:], strong))
    return out


def segments(text: str) -> list[dict]:
    """One line of Markdown as text spans: plain, strong, code or an anchor."""
    out, at = [], 0
    for bold in _BOLD.finditer(text):
        out += _spans(text[at : bold.start()], False)
        out += _spans(bold.group(1), True)
        at = bold.end()
    out += _spans(text[at:], False)
    return [span for span in out if span["text"]]


def plain(spans: list[dict]) -> str:
    return "".join(span["text"] for span in spans)


def slug(text: str) -> str:
    """The heading's anchor as GitHub writes it."""
    words = re.sub(r"[^\w\- ]", "", plain(segments(text)).lower())
    return words.replace(" ", "-")


def _list(lines, i):
    entries = []
    while i < len(lines) and lines[i].strip() and not _HEADING.match(lines[i]):
        item = _ITEM.match(lines[i])
        if item:
            entries.append([len(item.group(1)), item.group(2) is not None, item[3]])
        elif entries:
            entries[-1][2] += " " + lines[i].strip()
        i += 1
    root = {"ordered": entries[0][1], "items": []}
    stack = [(-1, root)]
    for indent, ordered, text in entries:
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if not parent["items"]:
            parent["ordered"] = ordered
        node = {"text": segments(text.strip()), "ordered": False, "items": []}
        parent["items"].append(node)
        stack.append((indent, node))
    return {"type": "list", "ordered": root["ordered"], "items": root["items"]}, i


def blocks(markdown: str) -> list[dict]:
    """The guide as blocks: heading, paragraph, list (nested) and table."""
    lines = markdown.splitlines()
    out, paragraph, i = [], [], 0

    def flush():
        if paragraph:
            out.append({"type": "paragraph", "text": segments(" ".join(paragraph))})
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line)
        if not line.strip():
            flush()
            i += 1
        elif heading:
            flush()
            text = heading.group(2)
            out.append(
                {
                    "type": "heading",
                    "level": len(heading.group(1)),
                    "text": segments(text),
                    "anchor": slug(text),
                }
            )
            i += 1
        elif line.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = lines[i].strip()
                if not _RULE.fullmatch(row):
                    cells = row.strip("|").split("|")
                    rows.append([segments(cell.strip()) for cell in cells])
                i += 1
            out.append({"type": "table", "header": rows[0], "rows": rows[1:]})
        elif _ITEM.match(line):
            flush()
            block, i = _list(lines, i)
            out.append(block)
        else:
            paragraph.append(line.strip())
            i += 1
    flush()
    return out


def section(parsed: list[dict], title: str, *, nested: bool = True):
    """The blocks under the heading titled `title`, up to the next heading of
    its level or above (any heading, when `nested` is false); None when the
    guide has no such heading."""
    found, level, out = False, None, []
    for block in parsed:
        if block["type"] == "heading":
            if found and (not nested or block["level"] <= level):
                break
            if not found and plain(block["text"]) == title:
                found, level = True, block["level"]
                continue
        if found:
            out.append(block)
    return out if found else None


def document(name: str = "remote-setup", repo: Path = REPO) -> dict:
    """A guide by name, parsed; `available` is false when this checkout lacks
    the file. Only the paths in `GUIDES` are ever read."""
    source = GUIDES[name]
    try:
        text = (Path(repo) / source).read_text(encoding="utf-8")
    except OSError:
        return {
            "schema": SCHEMA,
            "name": name,
            "source": source,
            "available": False,
            "title": None,
            "blocks": [],
        }
    parsed = blocks(text)
    first = parsed[0] if parsed else None
    title = plain(first["text"]) if first and first["type"] == "heading" else name
    return {
        "schema": SCHEMA,
        "name": name,
        "source": source,
        "available": True,
        "title": title,
        "blocks": parsed[1:] if first and first["type"] == "heading" else parsed,
    }
