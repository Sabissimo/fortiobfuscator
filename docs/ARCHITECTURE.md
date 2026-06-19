# Architecture

How FortiObfuscator turns a FortiGate config into a scrubbed one. For a quick
orientation read [../CLAUDE.md](../CLAUDE.md) first; this is the detailed view.

## Design goals

1. **Local & dependency-light.** The engine is pure standard library; only the
   optional web UI needs Flask. No data ever leaves the machine.
2. **Consistent.** The same source value always maps to the same replacement, so
   cross-references survive (an address renamed in its definition is renamed in
   every policy/group that uses it).
3. **Structurally valid.** Output still parses as FortiOS config: block
   structure is untouched, IPs stay valid IPs, masks are preserved, `ENC` fields
   keep the `ENC` keyword.
4. **Data-driven.** What to obfuscate is declared in `rules.py`; the engine is
   generic over those declarations, so new categories rarely touch engine logic.

## FortiGate config shape

A FortiOS config is a nested block structure:

```
config <path words...>
    edit "<object name>"          # or `edit <number>` for policies
        set <key> <value...>
        config <subsection>       # nested — e.g. secondaryip, ipv6
            edit ...
            next
        end
    next
end
```

Object **definitions** live as `edit "<name>"` directly under a `config` path
(e.g. `config firewall address`). Object **references** appear as quoted tokens
in `set` lines elsewhere (`set dstaddr "Web_Server"`,
`set member "A" "B"`). Names are always quoted; this is what makes safe,
collision-free replacement possible.

## Two-pass pipeline

`engine.obfuscate(text, options) -> Result`

### Pass 1 — collect object names  (`parser.collect_object_names`)

A stack of `config` paths is maintained:

- `config a b c` → push `("a","b","c")`
- `end` → pop
- the **innermost** frame (`stack[-1]`) is the current block

For each enabled `Category`, its `blocks` map an exact config-path tuple to a
replacement prefix. When `stack[-1]` matches a category block:

- normal categories: an `edit "<name>"` defines an object;
- `policy` (`by_set_name=True`): a `set name "<x>"` line defines the object.

Matching the **exact innermost path** means nested `edit`s (under
`config secondaryip`, `config ipv6`, …) are naturally ignored — they sit under a
deeper, non-matching path.

Reserved/default names (`Category.reserved`, `Category.reserved_patterns`) are
skipped. Each accepted name gets `PREFIX_<n>` with an independent per-prefix
counter. The result is a single `name_map: {original: replacement}` plus
per-category counts.

> One global `name_map` keyed by string keeps cross-references consistent.
> FortiOS object namespaces are near-disjoint, so cross-type collisions are
> effectively impossible in real configs.

### Pass 2 — substitute  (in `engine.obfuscate`)

The lines are rewritten one at a time. A compiled alternation regex
`"(name1|name2|…)"` replaces object-name tokens in O(1) lookups via `name_map`.
Value types use a `MappingStore` each.

**Order is fixed and deliberate:**

| # | Step | Why here |
|---|------|----------|
| 1 | Certificate / private-key block | Multi-line; consumes lines up to the closing `"`. Must run before per-line steps. |
| 2 | Comment removal | Drop whole `set comment[s]` line before doing any work on it. |
| 3 | `ENC` blob | Replace `ENC <blob>` → `ENC 012345678` before anything else scans the blob. |
| 4 | Object-name tokens | **Before IPs** — so an address *named* `10.0.0.0` becomes `ADDR_n`, not a mangled IP. |
| 5 | FQDN / wildcard-FQDN field | Targets `set fqdn` / `set wildcard-fqdn` values; preserves `*.`. |
| 6 | SSID field | `set ssid` → `SSID_n`. |
| 7 | MAC | Before IPv6 (a MAC is invalid IPv6 anyway, but order keeps intent clear). |
| 8 | IPv6 | Broad regex, validated with `ipaddress`; `::` and invalid matches skipped. |
| 9 | IPv4 | Last; skips subnet masks and `0.0.0.0` via `_is_netmask_or_zero`. |

## Consistency: `MappingStore` + minters

`mapping.MappingStore` holds a `{source: replacement}` dict and a counter.
`get(value, mint)` returns the existing replacement or mints a new one with
`mint(ordinal)`. Minters (`mapping.py`) produce deterministic, valid,
obviously-fake values:

| Kind | Range | Example |
|------|-------|---------|
| IPv4 | `100.64.0.0/10` (CGNAT) | `100.64.0.1` |
| IPv6 | `2001:db8::/32` (doc range) | `2001:db8::1` |
| MAC  | locally-administered | `02:00:00:00:00:01` |
| FQDN | — | `obfuscated1.example.com` |
| SSID | — | `SSID_1` |

Object names are minted in pass 1 with category prefixes (`ADDR_`, `VPN_INTF_`,
…). Subnet relationships are **not** preserved (per spec — each unique address
is mapped independently); structure and validity are.

## Toggling

`engine.Options` holds `types: set[str]` and `categories: set[str]` (enabled
keys) plus `emit_mapping`. Disabled categories are skipped in pass 1 (their names
never enter `name_map`, so they're never replaced); disabled types skip their
pass-2 step. The CLI derives these from `--no-<key>` flags; the web form derives
them from checkbox presence.

## Output & mapping file

`Result(text, report, mapping)`. When `emit_mapping` is set, `mapping` is a dict
of `name_map` + each value store's dict — JSON-serialisable, reversible, and
**sensitive** (it reveals originals). The web UI bundles scrubbed config +
mapping + summary into a `.zip`; the CLI writes the map with `-m`.

## Edge cases handled

- **Netmask vs address:** `set subnet <addr> <mask>` — only the address maps; the
  mask (and `0.0.0.0`, `255.255.255.255`) is preserved.
- **MAC vs IPv6:** a MAC matches the broad IPv6 regex but fails
  `ipaddress.IPv6Address` (6 groups, no `::`), so it's left for the MAC step.
- **Certificate references vs blobs:** `set certificate "Short_Name"` (a
  reference) is left alone; only PEM/`ENC` blobs (or always-blob fields
  `private-key`/`csr`) are redacted. See `rules.CERT_BLOB_FIELDS`.
- **CRLF/LF:** detected and preserved on output.

## Known limitations

- General free-text fields beyond `set comment[s]` (e.g. `set description`) are
  left intact by design.
- FortiOS is large and version-variant; exotic secret-bearing fields not in
  `rules.py` won't be caught. Always eyeball output before sharing. Adding a
  field is a one-line change in `rules.py` (see EXTENDING.md).
