"""Tests for the FortiObfuscator core engine."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fortiobfuscator.engine import Options, obfuscate  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.conf")


@pytest.fixture(scope="module")
def sample_text() -> str:
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def scrubbed(sample_text: str):
    return obfuscate(sample_text, Options.all_enabled(emit_mapping=True))


# --------------------------------------------------------------------------- #
# Object names
# --------------------------------------------------------------------------- #


def test_custom_interface_renamed_everywhere(scrubbed):
    text = scrubbed.text
    assert "LAN_Internal" not in text
    # defined and referenced (zone, policy) all become the same token
    assert 'edit "INTERFACE_1"' in text or 'edit "INTERFACE_2"' in text
    repl = scrubbed.mapping["object_names"]["LAN_Internal"]
    assert repl.startswith("INTERFACE_")
    assert f'set interface "{repl}"' in text  # zone reference
    assert f'set srcintf "{repl}"' in text  # policy reference


def test_default_interface_names_preserved(scrubbed):
    assert 'edit "port1"' in scrubbed.text
    assert 'edit "wan1"' in scrubbed.text
    assert '"wan1"' in scrubbed.text  # still referenced by VIP/policy


def test_address_renamed_and_reserved_kept(scrubbed):
    text = scrubbed.text
    assert "Web_Server" not in text
    assert "Internal_Net" not in text
    assert 'edit "all"' in text  # reserved
    repl = scrubbed.mapping["object_names"]["Web_Server"]
    assert repl.startswith("ADDR_")
    # referenced in addrgrp member list
    assert f'"{repl}"' in text


def test_addrgrp_member_list_multi_token(scrubbed):
    web = scrubbed.mapping["object_names"]["Web_Server"]
    internal = scrubbed.mapping["object_names"]["Internal_Net"]
    assert f'set member "{web}" "{internal}"' in scrubbed.text


def test_service_reserved_all_preserved(scrubbed):
    assert 'edit "ALL"' in scrubbed.text
    assert "Custom_8080" not in scrubbed.text
    assert scrubbed.mapping["object_names"]["Custom_8080"].startswith("SERV_")


def test_vpn_interface_prefix(scrubbed):
    repl = scrubbed.mapping["object_names"]["HQ_to_Branch"]
    assert repl.startswith("VPN_INTF_")
    # phase2 phase1name reference updated
    assert f'set phase1name "{repl}"' in scrubbed.text


def test_policy_set_name_renamed(scrubbed):
    text = scrubbed.text
    assert "Allow_LAN_to_WAN" not in text
    assert scrubbed.mapping["object_names"]["Allow_LAN_to_WAN"].startswith("POLICY_")


def test_vip_and_group(scrubbed):
    vip = scrubbed.mapping["object_names"]["Web_VIP"]
    assert vip.startswith("VIP_")
    assert f'set member "{vip}"' in scrubbed.text  # vipgrp + policy ref


# --------------------------------------------------------------------------- #
# Value types
# --------------------------------------------------------------------------- #


def test_ipv4_substituted_and_consistent(scrubbed):
    text = scrubbed.text
    assert "203.0.113.10" not in text
    assert "198.51.100.5" not in text
    assert "10.10.10.0" not in text


def test_netmask_preserved(scrubbed):
    assert "255.255.255.0" in scrubbed.text
    assert "255.255.255.248" in scrubbed.text
    assert "255.255.255.255" in scrubbed.text


def test_mac_substituted(scrubbed):
    assert "00:0c:29:ab:cd:ef" not in scrubbed.text
    assert scrubbed.mapping["mac"]  # something was mapped


def test_enc_redacted(scrubbed):
    text = scrubbed.text
    assert "4hG8sK2lWmZ9qP0xV7nR3tB6yU1cD5fA" not in text
    assert "ENC 012345678" in text
    assert scrubbed.report.enc_redacted >= 3


def test_comments_removed(scrubbed):
    assert "permit outbound web" not in scrubbed.text
    assert scrubbed.report.comments_removed >= 1


def test_fqdn_substituted(scrubbed):
    text = scrubbed.text
    assert "updates.vendor.com" not in text
    assert "partner.example.org" not in text
    # wildcard prefix preserved
    assert any(line.strip().startswith('set wildcard-fqdn "*.') for line in text.splitlines())


def test_ssid_substituted(scrubbed):
    assert "CorpGuest-5G" not in scrubbed.text
    assert 'set ssid "SSID_1"' in scrubbed.text


def test_certificate_block_redacted(scrubbed):
    text = scrubbed.text
    assert "BEGIN ENCRYPTED PRIVATE KEY" not in text
    assert "aBcDeFgHiJkLmNoPqRsTuVwXyZ" not in text
    assert "-----BEGIN OBFUSCATED-----" in text
    assert scrubbed.report.cert_blocks_redacted == 1


def test_consistency_same_ip_same_replacement(sample_text):
    # Web_Server subnet 203.0.113.50 and VIP mappedip "203.0.113.50" must match
    res = obfuscate(sample_text, Options.all_enabled(emit_mapping=True))
    assert res.mapping["ipv4"]["203.0.113.50"]
    repl = res.mapping["ipv4"]["203.0.113.50"]
    assert res.text.count(repl) >= 2


# --------------------------------------------------------------------------- #
# Toggles
# --------------------------------------------------------------------------- #


def test_disable_ipv4_leaves_ips(sample_text):
    opts = Options.all_enabled()
    opts.types.discard("ipv4")
    res = obfuscate(sample_text, opts)
    assert "203.0.113.10" in res.text


def test_public_ips_only_keeps_private(sample_text):
    opts = Options.all_enabled()
    opts.public_ips_only = True
    res = obfuscate(sample_text, opts)
    text = res.text
    # private / local addresses preserved
    assert "10.10.10.1" in text
    assert "10.20.0.1" in text
    assert "10.10.10.0" in text
    # public addresses still obfuscated
    assert "203.0.113.10" not in text
    assert "198.51.100.5" not in text
    assert "198.51.100.200" not in text


def test_public_ips_only_default_off(sample_text):
    res = obfuscate(sample_text, Options.all_enabled())
    # default behaviour still scrubs private IPs
    assert "10.10.10.1" not in res.text


def test_disable_address_category_leaves_names(sample_text):
    opts = Options.all_enabled()
    opts.categories.discard("address")
    res = obfuscate(sample_text, opts)
    assert "Web_Server" in res.text


def test_mapping_round_trip_reverses(scrubbed, sample_text):
    """Applying the mapping in reverse restores original object names."""
    text = scrubbed.text
    for original, repl in scrubbed.mapping["object_names"].items():
        text = text.replace(f'"{repl}"', f'"{original}"')
    # every original object name should be back
    for original in scrubbed.mapping["object_names"]:
        assert original in text


def test_idempotent_structure(sample_text):
    """Block structure (config/end/edit/next counts) is preserved."""
    res = obfuscate(sample_text, Options.all_enabled())

    def counts(t: str):
        toks = [ln.strip().split()[0] for ln in t.splitlines() if ln.strip()]
        return (toks.count("config"), toks.count("end"), toks.count("next"))

    # comments removed change line count but not structure tokens
    assert counts(res.text) == counts(sample_text)
