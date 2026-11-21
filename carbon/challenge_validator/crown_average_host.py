"""The crown average's validator-host-only half: it opens K_crown and turns the rule on (the crown multi-rebuild
average ruling, lead-records a322dea4).

`crown_average` is pure decision logic and takes the key as bytes; it never opens a file. THIS module reads the owner-only
key file and installs the rule, and it is imported by the receiver's startup alone. Nothing under the product process
(the Control Center and the MCP door) imports it, so the product process never holds a key
(`tests/invariants/test_product_process_holds_no_key.py` walks the product's import closure and finds none here).

The key file is the validator host's own K_crown, never a miner's key and never in a worker container.
"""

from __future__ import annotations

from pathlib import Path

from carbon.challenge_validator import crown_average, crown_common


def read_crown_key(name) -> bytes:
    """K_crown from a configured private file: an exact absolute regular file, owner-private, 32 to 4096 bytes (like the
    speed-sample key). It is held by the validator host only and never leaves it."""
    selected = Path(name) if type(name) is str else None
    if (
        selected is None
        or not selected.is_absolute()
        or selected.is_symlink()
        or not selected.is_file()
        or selected.resolve() != selected
        or (selected.stat().st_mode & 0o077)
        or not 32 <= selected.stat().st_size <= 4096
    ):
        raise crown_common.CrownAverageInvalid("crown_key_file_invalid")
    return selected.read_bytes()


def install(cfg):
    """Install the menu D draw key from a receiver's configuration and keep the crown average OFF.

    The ``menu_draw`` section (the host's K_crown file) installs the menu D draw key (`pool_menu.install_key`, purpose
    label ``d-menu-sample``); absent: off, and a menu version refuses to grade (``menu_draw_unavailable``, Carbon's gap).
    Its key-file checks stay (`read_crown_key`: hidden values, K_crown draws the menu rows).

    The ``crown_average`` section is no longer read (over-broad rules audit S7 C2 301): every receiver decides crowns on
    the official grades (`crown_official`, the default for every version since 14 Nov, installed by `serve`, which sets
    `crown_average.ACTIVE` to None anyway), so a malformed or unreadable section refused a start for a rule that is
    never on. A present section is ignored."""
    from carbon.scoring import pool_menu

    menu = cfg.get("menu_draw")
    if menu is None:
        pool_menu.install_key(None)
    else:
        if type(menu) is not dict or set(menu) != {"key_file"}:
            raise crown_common.CrownAverageInvalid("menu_draw_selection_invalid")
        pool_menu.install_key(read_crown_key(menu["key_file"]))
    crown_average.ACTIVE = None
