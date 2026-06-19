"""Pass 1: walk the config structure and collect object names to rename.

A stack of ``config`` paths is maintained so that an ``edit`` (or, for policies,
a ``set name``) is attributed to the *innermost* enclosing ``config`` block.
Exact path matching means nested blocks (``config secondaryip``, ``config
ipv6`` ...) are naturally ignored.
"""

from __future__ import annotations

from .rules import CATEGORIES, RE_CONFIG, RE_EDIT, RE_END, RE_SET_NAME, Category


def collect_object_names(
    lines: list[str], enabled: set[str]
) -> tuple[dict[str, str], dict[str, int]]:
    """Return ``(name_map, counts)``.

    ``name_map`` maps every original object name to its ``PREFIX_<n>``
    replacement; ``counts`` maps each category key to how many names it renamed.
    Only categories whose key is in ``enabled`` are collected.
    """
    # path tuple -> (category, prefix), for enabled categories only
    block_lookup: dict[tuple[str, ...], tuple[Category, str]] = {}
    for cat in CATEGORIES:
        if cat.key not in enabled:
            continue
        for path, prefix in cat.blocks:
            block_lookup[path] = (cat, prefix)

    name_map: dict[str, str] = {}
    counts: dict[str, int] = {cat.key: 0 for cat in CATEGORIES}
    prefix_counters: dict[str, int] = {}

    stack: list[tuple[str, ...]] = []

    def assign(cat: Category, prefix: str, name: str) -> None:
        if not name or cat.is_reserved(name) or name in name_map:
            return
        prefix_counters[prefix] = prefix_counters.get(prefix, 0) + 1
        name_map[name] = f"{prefix}{prefix_counters[prefix]}"
        counts[cat.key] += 1

    for line in lines:
        m = RE_CONFIG.match(line)
        if m:
            stack.append(tuple(m.group(1).split()))
            continue
        if RE_END.match(line):
            if stack:
                stack.pop()
            continue

        if not stack:
            continue
        current = block_lookup.get(stack[-1])
        if current is None:
            continue
        cat, prefix = current

        if cat.by_set_name:
            ms = RE_SET_NAME.match(line)
            if ms:
                assign(cat, prefix, ms.group(1))
        else:
            me = RE_EDIT.match(line)
            if me:
                # group(1) = quoted name, group(2) = bare token (numeric ids etc.)
                name = me.group(1)
                if name is not None:
                    assign(cat, prefix, name)

    return name_map, counts
