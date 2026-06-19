# Extending FortiObfuscator

Most changes are data edits in `fortiobfuscator/rules.py`. The engine is generic
over those declarations, so new categories/types automatically appear in **both**
the CLI (`--no-<key>`) and the web UI (checkboxes) with no extra wiring.

Always add a matching test in `tests/test_engine.py` and extend
`tests/fixtures/sample.conf` if the case isn't represented.

---

## 1. Add a new object-name category

Example: rename `config firewall schedule` objects to `SCHED_<n>`.

Add a `Category` to `rules.CATEGORIES`:

```python
Category(
    key="schedule",                 # CLI flag --no-schedule, form field cat_schedule
    label="Schedule",               # shown in the web UI
    blocks=((("firewall", "schedule", "recurring"), "SCHED_"),
            (("firewall", "schedule", "onetime"),  "SCHED_")),
    reserved=frozenset({"always"}), # default names never to rename
),
```

That's it. `parser.collect_object_names` picks it up, `engine` includes it in
`ALL_CATEGORY_KEYS`, and references are replaced wherever the quoted name appears.

Notes:
- `blocks` keys are the **exact words after `config`** (the innermost block).
- Multiple paths can share one prefix (see `address`/`address6`, the VPN phases).
- For objects keyed by `set name` instead of `edit "<name>"` (like policies),
  set `by_set_name=True`.
- Use `reserved` for exact names and `reserved_patterns` for regexes (see the
  interface `port\d+` / `wan\d+` patterns).

---

## 2. Add a new value type (global substitution)

Example: obfuscate email addresses consistently.

1. **Toggle** — add to `rules.TYPE_TOGGLES`:
   ```python
   ("email", "Email addresses"),
   ```

2. **Regex** — in `rules.py`:
   ```python
   RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
   ```

3. **Minter** — in `mapping.py`:
   ```python
   def email_replacement(n: int) -> str:
       return f"user{n}@example.com"
   ```

4. **Pass-2 step** — in `engine.obfuscate`, create a store and a step. Place it
   in the ordered block respecting the rules (e.g. before IP steps if values can
   contain dotted numbers):
   ```python
   email_store = mp.MappingStore("email")
   ...
   if options.type_on("email"):
       def _sub(m):
           bump("email")
           return email_store.get(m.group(0).lower(), mp.email_replacement)
       line = rules.RE_EMAIL.sub(_sub, line)
   ```

5. **Mapping export** — add `"email": email_store.as_dict()` to the
   `result.mapping` dict (so it's reversible).

6. **Test** — add a case + a sample line in the fixture.

---

## 3. Redact an additional secret field

If a field carries a secret but isn't an `ENC` blob, either:

- add its keyword to the comment/secret handling, or
- for PEM-style multi-line blobs, add the field to `RE_CERT_START` (and
  `CERT_BLOB_FIELDS` if its value is *always* a blob rather than a short
  reference).

---

## Checklist before committing

- [ ] `python -m pytest tests/ -q` is green.
- [ ] New behaviour has a test against `tests/fixtures/sample.conf`.
- [ ] No third-party imports added to `fortiobfuscator/` (stdlib only).
- [ ] If reversibility matters, the new mapping is included in `result.mapping`.
- [ ] Tried it end-to-end via CLI and/or `python -m webapp.app`.
