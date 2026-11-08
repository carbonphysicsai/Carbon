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

from carbon.challenge_validator import crown_average


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
        raise crown_average.CrownAverageInvalid("crown_key_file_invalid")
    return selected.read_bytes()


def install(cfg):
    """Turn the rule on (or off) from a receiver's configuration: the ``crown_average`` section names the private key
    file. Absent: off. The ``menu_draw`` section (the same host's K_crown file) installs the menu D draw key
    (`pool_menu.install_key`, purpose label ``d-menu-sample``); absent: off, and a menu version refuses to grade
    (``menu_draw_unavailable``, Carbon's gap)."""
    from carbon.scoring import pool_menu

    menu = cfg.get("menu_draw")
    if menu is None:
        pool_menu.install_key(None)
    else:
        if type(menu) is not dict or set(menu) != {"key_file"}:
            raise crown_average.CrownAverageInvalid("menu_draw_selection_invalid")
        pool_menu.install_key(read_crown_key(menu["key_file"]))
    section = cfg.get("crown_average")
    if section is None:
        crown_average.ACTIVE = None
        return
    if type(section) is not dict or set(section) != {"key_file"}:
        raise crown_average.CrownAverageInvalid("crown_average_selection_invalid")
    crown_average.ACTIVE = crown_average.Active(
        crown_average.load_rule(), read_crown_key(section["key_file"])
    )
