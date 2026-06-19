# FortiObfuscator

Obfuscate sensitive data in a **FortiGate / FortiOS** configuration file —
**entirely on your own machine**. No cloud, no uploads, no network calls.

Use it to safely share a config with vendor/TAC, in documentation, or in
training material without leaking secrets, IPs, hostnames, or object names.

The obfuscation is **consistent and structurally valid**: an object renamed to
`ADDR_1` is renamed *everywhere it is referenced* (policies, groups, VIPs …),
and every IP/MAC/FQDN maps the same way each time it appears — so the scrubbed
config still parses and analyses cleanly.

---

## What it obfuscates

**Types** (global)

| Type | Behaviour |
|---|---|
| IPv4 | All addresses (unicast/multicast/private/ranges) → consistent fakes. Subnet masks and `0.0.0.0` are preserved. |
| IPv6 | All addresses → consistent fakes (`2001:db8::/32`). |
| FQDN | `set fqdn` / `set wildcard-fqdn` values → fake domains (wildcard `*.` preserved). |
| MAC | All MAC addresses → consistent locally-administered fakes. |
| Password / PSK | `ENC <blob>` → `ENC 012345678`. |
| SSID | `set ssid` → `SSID_<n>`. |
| Comment | `set comment` / `set comments` lines removed. |
| Certificate / key | Multi-line `private-key` / cert PEM blocks → redacted. |

**Object names** (renamed consistently, default/reserved names kept as-is)

`Interface → INTERFACE_n` · `Zone → ZONE_n` · `Address → ADDR_n` ·
`Address Group → ADDRGRP_n` · `IP Pool → IPPOOL_n` · `VIP → VIP_n` ·
`VIP Group → VIPGRP_n` · `Service → SERV_n` · `Service Group → SERVGRP_n` ·
`VPN (phase1/2) → VPN_n` / `(phase1/2-interface) → VPN_INTF_n` ·
`Policy (set name) → POLICY_n`

Default names such as `port1`, `wan1`, `dmz`, `all`, `any`, `ALL` are never
changed.

Every category above is **individually toggleable** in both the web UI and the
CLI.

---

## Installation

Requires **Python 3.10+**. The core engine and CLI use only the standard
library; **Flask** is needed only for the optional web UI.

### 1. Get the code

```bash
git clone https://github.com/Sabissimo/fortiobfuscator.git
cd fortiobfuscator
```

### 2. (Recommended) Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies (only needed for the web UI)

```bash
pip install -r requirements.txt
```

> Using the CLI only? You can skip this step — the CLI has no dependencies.

---

## Usage

### Web UI (point-and-click)

```bash
python -m webapp.app
```

Open **http://127.0.0.1:5000** in your browser, choose a `.conf` file, tick the
categories you want, and click **Obfuscate & download**. Tick *"produce a
reversible mapping file"* to get a `.zip` containing the scrubbed config, the
`original → replacement` mapping, and a summary.

The server binds to `127.0.0.1` only; files are processed in memory and never
written to disk server-side.

### Command line

```bash
# Scrub everything, write to a file
python -m fortiobfuscator.cli config.conf -o config_obfuscated.conf

# Print a summary, and also save a reversible mapping (keep it local!)
python -m fortiobfuscator.cli config.conf -o out.conf -m map.json --summary

# Disable specific categories
python -m fortiobfuscator.cli config.conf -o out.conf --no-ipv6 --no-comment --no-policy

# Pipe via stdin/stdout
cat config.conf | python -m fortiobfuscator.cli - > out.conf
```

Run `python -m fortiobfuscator.cli --help` for every `--no-<category>` flag.

### As a library

```python
from fortiobfuscator import obfuscate, Options

result = obfuscate(open("config.conf").read(), Options.all_enabled(emit_mapping=True))
print(result.text)            # scrubbed config
print(result.report.as_dict())  # what changed
print(result.mapping)         # original -> replacement (if emit_mapping)
```

---

## About the mapping file

The optional mapping file makes the obfuscation **reversible** and lets you map
analysis results back to real values. **It reveals every original value** — keep
it strictly local and never share it alongside the scrubbed config.

---

## Documentation

- [CLAUDE.md](CLAUDE.md) — onboarding context to pick the project up cold
  (commands, mental model, invariants).
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the two-pass design in detail.
- [docs/EXTENDING.md](docs/EXTENDING.md) — how to add new categories / value
  types (mostly a data edit in `rules.py`).
- [CHANGELOG.md](CHANGELOG.md) — version history.

## Development & tests

```bash
pip install pytest
python -m pytest tests/ -q
```

---

## Project layout

```
fortiobfuscator/      core engine (stdlib only)
  rules.py            regexes, reserved names, category config
  mapping.py          consistent replacement stores
  parser.py           pass 1 — collect object names
  engine.py           pass 2 — apply substitutions  (entry: obfuscate)
  report.py           per-category summary
  cli.py              command-line front end
webapp/               optional local Flask UI
tests/                pytest suite + sample.conf fixture
```

---

## Security notes

- 100% local: no telemetry, no outbound requests, nothing uploaded.
- The web server listens on `127.0.0.1` only and processes uploads in memory.
- Always eyeball the output. FortiOS is large and version-variant; if your
  config has an exotic field this tool doesn't know about, review before
  sharing. Issues and PRs welcome.

## License

MIT — see [LICENSE](LICENSE).
