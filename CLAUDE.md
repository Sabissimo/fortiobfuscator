# CLAUDE.md — FortiObfuscator

Context for anyone (human or AI) picking this project up cold. Read this first,
then [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the deep dive.

## What this is

A **local, Python-based** tool that obfuscates sensitive data in a FortiGate /
FortiOS configuration file so it can be shared safely (vendor/TAC, docs,
training). Everything runs offline — **no network calls, nothing uploaded**.

Core guarantee: obfuscation is **consistent and structure-preserving**. An
object renamed `ADDR_1` is renamed everywhere it's referenced; each IP/MAC/FQDN
maps identically every time it appears. The scrubbed config still parses.

## Repo layout

```
fortiobfuscator/      core engine — STDLIB ONLY, no third-party imports
  rules.py            data: regexes, reserved names, Category definitions, TYPE_TOGGLES
  mapping.py          MappingStore (consistent value→replacement) + minter funcs
  parser.py           PASS 1 — collect_object_names(): stack walk of config tree
  engine.py           PASS 2 — obfuscate(): the public entry point; Options/Result
  report.py           Report dataclass (per-category counts)
  cli.py              argparse front end
webapp/               optional local Flask UI (only thing needing Flask)
  app.py              routes: GET / , POST /obfuscate ; binds 127.0.0.1
  templates/index.html, static/style.css
tests/
  test_engine.py      21 pytest cases
  fixtures/sample.conf  synthetic config exercising every category
docs/                 ARCHITECTURE.md, EXTENDING.md
```

## Commands

```bash
# Tests (install pytest first: pip install pytest)
python -m pytest tests/ -q

# CLI
python -m fortiobfuscator.cli tests/fixtures/sample.conf -o out.conf -m map.json --summary
python -m fortiobfuscator.cli --help          # lists every --no-<category> flag

# Web UI  (pip install -r requirements.txt)
python -m webapp.app                            # → http://127.0.0.1:5000

# Library
python -c "from fortiobfuscator import obfuscate, Options; print(obfuscate(open('tests/fixtures/sample.conf').read(), Options.all_enabled()).text)"
```

## Mental model (how a run works)

`engine.obfuscate(text, options)` does two passes:

1. **Pass 1 — `parser.collect_object_names(lines, enabled_categories)`**
   Walks lines keeping a stack of `config …` paths. When the *innermost* config
   block exactly matches a `Category.blocks` path, the `edit "<name>"` (or, for
   policy, `set name "<x>"`) defines an object → assign `PREFIX_<n>`, skipping
   reserved/default names. Returns `name_map` (original→replacement) + counts.

2. **Pass 2 — line-by-line rewrite in `engine.obfuscate`**, in this fixed order
   (order matters — see ARCHITECTURE):
   `certificate (multi-line) → comment removal → ENC → object-name tokens →
   FQDN → SSID → MAC → IPv6 → IPv4`.

Consistency comes from `MappingStore` (one per value kind) — first sight of a
value mints a deterministic replacement; repeats reuse it. All stores +
`name_map` are exported as the optional JSON mapping file when
`Options.emit_mapping` is set.

## Key invariants / gotchas

- **Core stays stdlib-only.** Do not add third-party imports to
  `fortiobfuscator/`. Flask lives only in `webapp/`.
- **Object names are matched as quoted tokens** `"<name>"` — never bare. This is
  why multi-member lines (`set member "A" "B"`) and references all work, and why
  substring collisions don't happen.
- **Name replacement runs before IP replacement** so an address *named* after an
  IP (e.g. `edit "10.0.0.0"`) is handled as a name, not split by the IP regex.
- **IPv4 substitution skips subnet masks and `0.0.0.0`** via
  `engine._is_netmask_or_zero`. Don't "fix" this — masks must survive.
- **`Options.public_ips_only`** keeps local addresses (RFC1918, loopback,
  link-local, ULA — see `engine._is_local_ipv4/_is_local_ipv6`) and scrubs only
  public IPs. "Local" is defined by explicit network lists, narrower than
  `ipaddress.is_private` (which also flags documentation ranges).
- **IPv6 regex is deliberately broad** and validated with `ipaddress`. A MAC has
  6 colon-groups → invalid IPv6 → skipped, so MACs are never mis-typed as IPv6.
- **Reserved/default names** (e.g. `port1`, `wan1`, `all`, `ALL`) live in
  `rules.py` per `Category` (`reserved` / `reserved_patterns`).
- **`ENC` handling keeps the keyword**: `ENC <blob>` → `ENC 012345678`.
- **Comments**: only `set comment` / `set comments` lines are dropped.
  `set description` is intentionally left intact (out of original spec).
- **Windows/Unix newlines**: `engine._detect_newline` preserves CRLF vs LF.
- **Replacement value ranges** (in `mapping.py`): IPv4 → `100.64.0.0/10`,
  IPv6 → `2001:db8::/32`, MAC → `02:00:00:xx:xx:xx`. All valid + obviously fake.

## How to extend

Adding a new object-name category or value type is almost entirely data-driven —
see [docs/EXTENDING.md](docs/EXTENDING.md). Short version: add a `Category` to
`rules.CATEGORIES` (it auto-appears in CLI flags + web UI), or add a regex +
`MappingStore` + a step in pass 2 for a new value type.

## Conventions

- Python 3.10+, type hints, `from __future__ import annotations`.
- Match the existing terse, commented style; keep `rules.py` purely declarative.
- Every new behaviour gets a test in `tests/test_engine.py` against
  `fixtures/sample.conf` (extend the fixture if needed).
- Run `python -m pytest tests/ -q` before committing.

## Status

v1.0.0 — all 21 tests passing; CLI + web UI verified end-to-end.
Repo: https://github.com/Sabissimo/fortiobfuscator
