"""Strict parsing of a submitted strategy, before any adapter sees it.

Python's `json` accepts what a submitted strategy must not carry: `NaN` and
`Infinity` tokens, duplicate keys (the last silently wins), numbers that
overflow to infinity, unbounded integers and nesting deep enough to exhaust
the parser. Each is refused here by a typed code. A refusal never echoes the
submitted content.

Every limit here is an engineering admission limit, not a scientific value.
"""

from __future__ import annotations

import json
import math

#: Containers may nest this deep. Strategies are shallow declarative records.
MAX_DEPTH = 32
#: Integers must fit a signed 64-bit value.
INT_LIMIT = 2**63
_BOM = "﻿"


class MalformedStrategy(ValueError):
    """A strategy refused before dispatch; `code` names why."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _text(raw, max_bytes):
    if type(raw) is bytes:
        if len(raw) > max_bytes:
            raise MalformedStrategy("oversized_submission")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise MalformedStrategy("strategy_not_utf8") from None
    elif type(raw) is str:
        try:
            size = len(raw.encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            raise MalformedStrategy("strategy_not_utf8") from None
        if size > max_bytes:
            raise MalformedStrategy("oversized_submission")
        text = raw
    else:
        raise MalformedStrategy("strategy_not_json")
    if text.startswith(_BOM):
        raise MalformedStrategy("strategy_bom")
    return text


def _depth(text):
    """The deepest container nesting, ignoring brackets inside strings."""
    depth = deepest = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            deepest = max(deepest, depth)
            if deepest > MAX_DEPTH:
                return deepest
        elif char in "]}":
            depth -= 1
    return deepest


def _constant(_name):
    raise MalformedStrategy("non_finite_value")


def _float(token):
    value = float(token)
    if not math.isfinite(value):
        raise MalformedStrategy("non_finite_value")
    return value


def _int(token):
    # Bound the digits before converting, so a huge literal costs nothing.
    if len(token.lstrip("-")) > 19:
        raise MalformedStrategy("integer_out_of_range")
    value = int(token)
    if not -INT_LIMIT <= value < INT_LIMIT:
        raise MalformedStrategy("integer_out_of_range")
    return value


def _pairs(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise MalformedStrategy("duplicate_key")
    return dict(pairs)


def _encodable(value):
    """Refuse strings (keys or values) holding lone surrogates from escapes."""
    stack = [value]
    while stack:
        item = stack.pop()
        if type(item) is str:
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                raise MalformedStrategy("strategy_not_utf8") from None
        elif type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)


def parse_strategy(raw, *, max_bytes):
    """The strategy object in `raw` (str or bytes), or `MalformedStrategy`."""
    text = _text(raw, max_bytes)
    if _depth(text) > MAX_DEPTH:
        raise MalformedStrategy("strategy_nesting_too_deep")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
            parse_int=_int,
        )
    except MalformedStrategy:
        raise
    except (ValueError, RecursionError):
        raise MalformedStrategy("strategy_not_json") from None
    if type(value) is not dict:
        raise MalformedStrategy("strategy_not_object")
    _encodable(value)
    return value


__all__ = ["MAX_DEPTH", "MalformedStrategy", "parse_strategy"]
