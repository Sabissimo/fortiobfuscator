"""Consistent, deterministic replacement stores.

Each :class:`MappingStore` remembers the replacement minted for a given source
value so that repeated occurrences map identically (preserving cross-references
in the config). Stores are JSON-exportable for the optional mapping file.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field


@dataclass
class MappingStore:
    """Maps source values to deterministic replacements, one kind at a time."""

    kind: str
    _map: dict[str, str] = field(default_factory=dict)
    _counter: int = 0

    def __contains__(self, value: str) -> bool:
        return value in self._map

    def get(self, value: str, mint) -> str:
        """Return the replacement for ``value``, minting one via ``mint(n)``.

        ``mint`` receives the 1-based ordinal for newly-seen values.
        """
        existing = self._map.get(value)
        if existing is not None:
            return existing
        self._counter += 1
        replacement = mint(self._counter)
        self._map[value] = replacement
        return replacement

    def put(self, value: str, replacement: str) -> None:
        """Record an explicit mapping (used for object names with fixed prefixes)."""
        self._map.setdefault(value, replacement)

    @property
    def count(self) -> int:
        return len(self._map)

    def as_dict(self) -> dict[str, str]:
        return dict(self._map)


# --------------------------------------------------------------------------- #
# Minters — deterministic, valid, obviously-fake replacement values
# --------------------------------------------------------------------------- #


def ipv4_replacement(n: int) -> str:
    """Map ordinal -> a valid address inside 100.64.0.0/10 (CGNAT/shared space).

    Large enough (~4M hosts) for any realistic config and clearly not a real
    public or LAN address.
    """
    base = int(ipaddress.IPv4Address("100.64.0.0"))
    return str(ipaddress.IPv4Address(base + n))


def ipv6_replacement(n: int) -> str:
    """Map ordinal -> an address inside the documentation prefix 2001:db8::/32."""
    base = int(ipaddress.IPv6Address("2001:db8::"))
    return str(ipaddress.IPv6Address(base + n))


def mac_replacement(n: int) -> str:
    """Map ordinal -> a locally-administered unicast MAC (02:00:00:xx:xx:xx)."""
    suffix = n & 0xFFFFFF
    return "02:00:00:%02x:%02x:%02x" % (
        (suffix >> 16) & 0xFF,
        (suffix >> 8) & 0xFF,
        suffix & 0xFF,
    )


def fqdn_replacement(n: int) -> str:
    return f"obfuscated{n}.example.com"


def ssid_replacement(n: int) -> str:
    return f"SSID_{n}"
