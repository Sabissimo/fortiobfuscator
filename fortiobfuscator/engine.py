"""Pass 2: apply the obfuscation rules and produce the scrubbed config.

Public entry point: :func:`obfuscate`.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

from . import mapping as mp
from . import rules
from .parser import collect_object_names
from .report import Report

ALL_TYPE_KEYS = frozenset(k for k, _ in rules.TYPE_TOGGLES)
ALL_CATEGORY_KEYS = frozenset(c.key for c in rules.CATEGORIES)


@dataclass
class Options:
    """Which rules are enabled. Empty sets disable everything in that group."""

    types: set[str] = field(default_factory=lambda: set(ALL_TYPE_KEYS))
    categories: set[str] = field(default_factory=lambda: set(ALL_CATEGORY_KEYS))
    emit_mapping: bool = False

    @classmethod
    def all_enabled(cls, emit_mapping: bool = False) -> "Options":
        return cls(set(ALL_TYPE_KEYS), set(ALL_CATEGORY_KEYS), emit_mapping)

    def type_on(self, key: str) -> bool:
        return key in self.types

    def cat_on(self, key: str) -> bool:
        return key in self.categories


@dataclass
class Result:
    text: str
    report: Report
    mapping: dict | None = None  # populated only when emit_mapping is set


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_netmask_or_zero(addr: str) -> bool:
    """True for 0.0.0.0 and any valid contiguous subnet mask (incl. /32)."""
    try:
        value = int(ipaddress.IPv4Address(addr))
    except ipaddress.AddressValueError:
        return False
    if value == 0:
        return True
    inverted = value ^ 0xFFFFFFFF
    return (inverted & (inverted + 1)) == 0


def _detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #


def obfuscate(text: str, options: Options | None = None) -> Result:
    options = options or Options.all_enabled()
    newline = _detect_newline(text)
    lines = [ln.rstrip("\r") for ln in text.split("\n")]

    report = Report()

    # --- Pass 1: collect object names to rename ---------------------------- #
    name_map, counts = collect_object_names(lines, options.categories)
    report.object_names = {k: v for k, v in counts.items() if v}

    name_re: re.Pattern[str] | None = None
    if name_map:
        alternation = "|".join(
            re.escape(n) for n in sorted(name_map, key=len, reverse=True)
        )
        name_re = re.compile(f'"({alternation})"')

    # --- Consistent value stores ------------------------------------------- #
    ipv4_store = mp.MappingStore("ipv4")
    ipv6_store = mp.MappingStore("ipv6")
    mac_store = mp.MappingStore("mac")
    fqdn_store = mp.MappingStore("fqdn")
    ssid_store = mp.MappingStore("ssid")
    type_counts: dict[str, int] = {}

    def bump(key: str, n: int = 1) -> None:
        type_counts[key] = type_counts.get(key, 0) + n

    def repl_names(line: str) -> str:
        return name_re.sub(lambda m: f'"{name_map[m.group(1)]}"', line)

    def repl_mac(line: str) -> str:
        def sub(m: re.Match[str]) -> str:
            bump("mac")
            return mac_store.get(m.group(1).lower(), mp.mac_replacement)

        return rules.RE_MAC.sub(sub, line)

    def repl_ipv6(line: str) -> str:
        def sub(m: re.Match[str]) -> str:
            token = m.group(0)
            try:
                addr = ipaddress.IPv6Address(token)
            except ipaddress.AddressValueError:
                return token  # not a real IPv6 (e.g. a MAC) — leave alone
            if int(addr) == 0:  # :: (unspecified)
                return token
            bump("ipv6")
            return ipv6_store.get(token, mp.ipv6_replacement)

        return rules.RE_IPV6.sub(sub, line)

    def repl_ipv4(line: str) -> str:
        def sub(m: re.Match[str]) -> str:
            token = m.group(0)
            if _is_netmask_or_zero(token):
                return token
            bump("ipv4")
            return ipv4_store.get(token, mp.ipv4_replacement)

        return rules.RE_IPV4.sub(sub, line)

    # --- Pass 2: line-by-line rewrite -------------------------------------- #
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 1. Certificates / private keys (possibly multi-line) -------------- #
        if options.type_on("certificate"):
            mc = rules.RE_CERT_START.match(line)
            if mc:
                prefix, fieldname, rest = mc.group(1), mc.group(2), mc.group(3)
                stripped = rest.lstrip()
                is_blob = (
                    fieldname in rules.CERT_BLOB_FIELDS
                    or stripped.startswith("-----")
                    or stripped[:4].upper() == "ENC "
                )
                if is_blob:
                    out.append(f'{prefix}"-----BEGIN OBFUSCATED-----"')
                    report.cert_blocks_redacted += 1
                    # consume to the closing quote
                    if not (rest.rstrip().endswith('"') and rest.strip() != '"'):
                        i += 1
                        while i < n and not lines[i].rstrip().endswith('"'):
                            i += 1
                    i += 1
                    continue

        # 2. Comments — drop the whole line --------------------------------- #
        if options.type_on("comment") and rules.RE_COMMENT_LINE.match(line):
            report.comments_removed += 1
            i += 1
            continue

        # 3. ENC secrets ---------------------------------------------------- #
        if options.type_on("password"):
            line, c = rules.RE_ENC.subn("ENC 012345678", line)
            report.enc_redacted += c

        # 4. Object-name references (quoted tokens) ------------------------- #
        if name_re is not None:
            line = repl_names(line)

        # 5. FQDN / wildcard-FQDN field values ------------------------------ #
        if options.type_on("fqdn"):
            mf = rules.RE_FQDN_FIELD.match(line)
            if mf:
                head, value, tail = mf.group(1), mf.group(2), mf.group(3)
                wildcard = value.startswith("*.")
                bare = value[2:] if wildcard else value
                repl = fqdn_store.get(bare, mp.fqdn_replacement)
                if wildcard:
                    repl = "*." + repl
                bump("fqdn")
                line = f'{head}"{repl}"{tail}'

        # 6. SSID ----------------------------------------------------------- #
        if options.type_on("ssid"):
            ms = rules.RE_SSID_FIELD.match(line)
            if ms:
                head, value, tail = ms.group(1), ms.group(2), ms.group(3)
                bump("ssid")
                line = f'{head}"{ssid_store.get(value, mp.ssid_replacement)}"{tail}'

        # 7. MAC, IPv6, IPv4 ------------------------------------------------ #
        if options.type_on("mac"):
            line = repl_mac(line)
        if options.type_on("ipv6"):
            line = repl_ipv6(line)
        if options.type_on("ipv4"):
            line = repl_ipv4(line)

        out.append(line)
        i += 1

    report.types = type_counts

    result = Result(text=newline.join(out), report=report)

    if options.emit_mapping:
        result.mapping = {
            "object_names": name_map,
            "ipv4": ipv4_store.as_dict(),
            "ipv6": ipv6_store.as_dict(),
            "mac": mac_store.as_dict(),
            "fqdn": fqdn_store.as_dict(),
            "ssid": ssid_store.as_dict(),
        }

    return result
