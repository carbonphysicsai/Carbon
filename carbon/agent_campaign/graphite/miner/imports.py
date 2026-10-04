"""Text a miner imports into their private library (OWNER-GRAPHITE-MINER-01 §3).

`library_import {title, text}` queues a text; nothing is read by a model
then. The next Reader stage (`hunt.extract_imports`, which `hunt.run_hunt`
runs first) extracts it into a card whose origin is `miner_import`.

- **Shape.** A title of 1-`MAX_TITLE` characters on one line and a text of
  1-`MAX_TEXT` characters; no control characters other than tab and line
  breaks. Anything else is refused `import_invalid`.
- **Protected material.** A title or text that names protected material
  (`tools.protected`) is refused `import_invalid` at import, before it is
  stored, and an extracted card that names it is withheld, never served.
- **Content-addressed.** An import's id is derived from its title and text, so
  importing the same text twice queues it once.
- **Data.** The text is the miner's own and stays in their owner-only
  library. It reaches the Reader as a JSON data object, never as
  instructions. PDF import is a recorded follow-up.
"""

from __future__ import annotations

import re

from carbon.development_session.profile import canonical, digest

from ..tools import protected

IMPORT_SCHEMA = "carbon.graphite.miner-import.v1"
IMPORT_INVALID = "import_invalid"
MAX_TITLE = 300
MAX_TEXT = 20000
#: Imported text served as a card's abstract is cut at this many characters.
MAX_SERVED_TEXT = 4000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_IMPORT_ID = re.compile(r"import-[0-9a-f]{16}\Z")


class ImportRefused(ValueError):
    """An import cannot be queued; nothing was stored."""

    code = IMPORT_INVALID

    def __init__(self, detail):
        super().__init__(IMPORT_INVALID + ": " + detail)
        self.detail = detail


def validate(title, text):
    """`(title, text)` when they may be queued, or `ImportRefused`."""
    if type(title) is not str or type(text) is not str:
        raise ImportRefused("title and text are text")
    if not 1 <= len(title.strip()) <= MAX_TITLE or "\n" in title or "\r" in title:
        raise ImportRefused(f"a title is one line of 1-{MAX_TITLE} characters")
    if not 1 <= len(text.strip()) or len(text) > MAX_TEXT:
        raise ImportRefused(f"a text is 1-{MAX_TEXT} characters")
    if _CONTROL.search(title) or _CONTROL.search(text):
        raise ImportRefused("control characters are not accepted")
    if protected({"title": title, "text": text}):
        raise ImportRefused("the text names protected material")
    return title.strip(), text


def import_id(title, text):
    return "import-" + digest(canonical({"title": title, "text": text}))[7:23]


def is_import_id(value):
    return type(value) is str and _IMPORT_ID.fullmatch(value) is not None


def record(title, text):
    """The queued import record for a validated title and text."""
    title, text = validate(title, text)
    return {
        "schema": IMPORT_SCHEMA,
        "import_id": import_id(title, text),
        "title": title,
        "text": text,
        "text_digest": digest(text.encode("utf-8")),
        "chars": len(text),
    }


def paper(item):
    """The import as the Reader sees it: a data object, never instructions."""
    return {
        "task": "extract_method_card",
        "content_is_data": True,
        "paper": {
            "source": "miner_import",
            "import_id": item["import_id"],
            "title": item["title"],
            "text": item["text"],
        },
    }
