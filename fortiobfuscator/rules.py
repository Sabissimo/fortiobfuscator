"""Static rule definitions: regexes, reserved names, and object-name categories.

Everything here is data describing *what* to obfuscate. The matching/replacing
logic lives in :mod:`fortiobfuscator.engine`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Object-name categories
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Category:
    """A renameable object-name category.

    ``blocks`` maps an innermost ``config`` path (the words after ``config``) to
    the replacement prefix used for objects defined directly in that block.
    """

    key: str  # toggle key, e.g. "interface"
    label: str  # human label for the UI
    blocks: tuple[tuple[tuple[str, ...], str], ...]
    reserved: frozenset[str] = frozenset()
    reserved_patterns: tuple[re.Pattern[str], ...] = ()
    by_set_name: bool = False  # collect `set name "..."` instead of `edit "..."`

    def is_reserved(self, name: str) -> bool:
        if name in self.reserved:
            return True
        return any(p.match(name) for p in self.reserved_patterns)


# Default FortiGate interface names that must never be renamed.
_IFACE_RESERVED = frozenset(
    {
        "dmz",
        "internal",
        "modem",
        "ssl.root",
        "fortilink",
        "naf.root",
        "l2t.root",
        "vsys_ha",
        "vsys_fgfm",
        "any",
    }
)
_IFACE_PATTERNS = (
    re.compile(r"^port\d+$", re.IGNORECASE),
    re.compile(r"^wan\d+$", re.IGNORECASE),
    re.compile(r"^lan\d*$", re.IGNORECASE),
    re.compile(r"^mgmt\d*$", re.IGNORECASE),
    re.compile(r"^ha\d*$", re.IGNORECASE),
    re.compile(r"^npu\d+_vlink\d*$", re.IGNORECASE),
    re.compile(r"^emac_vlan", re.IGNORECASE),
)

_ADDR_RESERVED = frozenset({"all", "any", "none", "FABRIC_DEVICE"})
_SERVICE_RESERVED = frozenset({"ALL", "ANY", "all", "any", "webproxy"})


CATEGORIES: tuple[Category, ...] = (
    Category(
        key="interface",
        label="Interface",
        blocks=((("system", "interface"), "INTERFACE_"),),
        reserved=_IFACE_RESERVED,
        reserved_patterns=_IFACE_PATTERNS,
    ),
    Category(
        key="zone",
        label="Zone",
        blocks=((("system", "zone"), "ZONE_"),),
    ),
    Category(
        key="address",
        label="Address",
        blocks=(
            (("firewall", "address"), "ADDR_"),
            (("firewall", "address6"), "ADDR_"),
        ),
        reserved=_ADDR_RESERVED,
    ),
    Category(
        key="addrgrp",
        label="Address Group",
        blocks=(
            (("firewall", "addrgrp"), "ADDRGRP_"),
            (("firewall", "addrgrp6"), "ADDRGRP_"),
        ),
        reserved=_ADDR_RESERVED,
    ),
    Category(
        key="ippool",
        label="IP Pool",
        blocks=((("firewall", "ippool"), "IPPOOL_"),),
    ),
    Category(
        key="vip",
        label="VIP",
        blocks=((("firewall", "vip"), "VIP_"),),
    ),
    Category(
        key="vipgrp",
        label="VIP Group",
        blocks=((("firewall", "vipgrp"), "VIPGRP_"),),
    ),
    Category(
        key="service",
        label="Service",
        blocks=((("firewall", "service", "custom"), "SERV_"),),
        reserved=_SERVICE_RESERVED,
    ),
    Category(
        key="servicegrp",
        label="Service Group",
        blocks=((("firewall", "service", "group"), "SERVGRP_"),),
        reserved=_SERVICE_RESERVED,
    ),
    Category(
        key="vpn",
        label="VPN (IPsec phase1/2)",
        blocks=(
            (("vpn", "ipsec", "phase1"), "VPN_"),
            (("vpn", "ipsec", "phase2"), "VPN_"),
            (("vpn", "ipsec", "phase1-interface"), "VPN_INTF_"),
            (("vpn", "ipsec", "phase2-interface"), "VPN_INTF_"),
        ),
    ),
    Category(
        key="policy",
        label="Policy (set name)",
        blocks=((("firewall", "policy"), "POLICY_"),),
        by_set_name=True,
    ),
)

CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}


# --------------------------------------------------------------------------- #
# Value-type toggles (global substitutions)
# --------------------------------------------------------------------------- #

TYPE_TOGGLES: tuple[tuple[str, str], ...] = (
    ("ipv4", "IPv4 addresses"),
    ("ipv6", "IPv6 addresses"),
    ("fqdn", "FQDN / Wildcard-FQDN"),
    ("mac", "MAC addresses"),
    ("password", "Passwords / PSK (ENC)"),
    ("ssid", "Wireless SSID"),
    ("comment", "Comments (remove)"),
    ("certificate", "Certificates / private keys"),
)


# --------------------------------------------------------------------------- #
# Regexes
# --------------------------------------------------------------------------- #

# Config structure
RE_CONFIG = re.compile(r"^\s*config\s+(.+?)\s*$")
RE_EDIT = re.compile(r'^\s*edit\s+(?:"([^"]*)"|(\S+))\s*$')
RE_END = re.compile(r"^\s*end\s*$")
RE_NEXT = re.compile(r"^\s*next\s*$")
RE_SET_NAME = re.compile(r'^\s*set\s+name\s+"([^"]*)"\s*$')

# Comments
RE_COMMENT_LINE = re.compile(r"^\s*set\s+comments?\b")

# ENC secrets — keep the keyword, nuke the blob.
RE_ENC = re.compile(r"\bENC\s+\S+")

# FQDN / SSID fields
RE_FQDN_FIELD = re.compile(r'^(\s*set\s+(?:wildcard-)?fqdn\s+)"([^"]*)"(\s*)$')
RE_SSID_FIELD = re.compile(r'^(\s*set\s+ssid\s+)"([^"]*)"(\s*)$')

# MAC address (colon or dash separated)
RE_MAC = re.compile(r"\b([0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\2[0-9A-Fa-f]{2}){4})\b")

# IPv4 — broad; netmask/zero filtering happens in the engine.
RE_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")

# IPv6 — covers full, compressed (::) and embedded forms. Deliberately broad;
# refined by ``looks_like_ipv6`` in the engine to avoid false positives.
RE_IPV6 = re.compile(
    r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b"
    r"|\b(?:[0-9A-Fa-f]{1,4}:){1,7}:(?:[0-9A-Fa-f]{1,4})?\b"
    r"|::(?:[0-9A-Fa-f]{1,4}:){0,6}[0-9A-Fa-f]{1,4}\b"
)

# Multi-line PEM-style secret fields: `set private-key "-----BEGIN ...` ... `"`
# group(1)=prefix incl. `set <field> `, group(2)=field, group(3)=value remainder
RE_CERT_START = re.compile(
    r'^(\s*set\s+(private-key|certificate|ca|csr|ssl-certificate)\s+)"(.*)$'
)

# Fields whose value is always a secret blob (vs. a short name reference).
CERT_BLOB_FIELDS = frozenset({"private-key", "csr"})
