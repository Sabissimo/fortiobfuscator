# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-06-19

### Added
- **"External IPs only" option** (`Options.public_ips_only`): obfuscate only
  public IPs and keep local/LAN addresses (RFC1918, loopback, link-local, ULA).
  Exposed as the `--public-ips-only` CLI flag and an "external IPs only" checkbox
  in the web UI. "Local" is defined by explicit network lists, narrower than
  `ipaddress.is_private` (which also flags documentation ranges).

## [1.0.0] — 2026-06-19

Initial release.

### Added
- **Core engine** (`fortiobfuscator/`, standard library only): two-pass,
  consistent, structure-preserving obfuscation of FortiGate configs.
- **Type substitutions**: IPv4, IPv6, FQDN / wildcard-FQDN, MAC, `ENC`
  passwords/PSKs (`ENC 012345678`), wireless SSID, comment removal, and
  multi-line certificate / private-key blocks.
- **Object-name renaming** across 11 categories — interface, zone, address,
  address group, IP pool, VIP, VIP group, service, service group, VPN
  (`VPN_`/`VPN_INTF_`), policy — with default/reserved names preserved.
- **Per-category toggles** in both interfaces; **optional reversible mapping
  file**.
- **CLI** (`python -m fortiobfuscator.cli`) with `--no-<category>` flags,
  `--summary`, stdin/stdout support, and `-m/--mapping`.
- **Local Flask web UI** (`python -m webapp.app`, bound to `127.0.0.1`,
  in-memory) with a `.zip` bundle (config + mapping + summary).
- **Test suite**: 21 pytest cases against a representative sample config.
- **Docs**: README, CLAUDE.md, docs/ARCHITECTURE.md, docs/EXTENDING.md.
