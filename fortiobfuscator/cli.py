"""Command-line front end over the obfuscation core.

Example:
    python -m fortiobfuscator.cli config.conf -o scrubbed.conf --mapping map.json
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import ALL_CATEGORY_KEYS, ALL_TYPE_KEYS, Options, obfuscate
from .rules import CATEGORIES, TYPE_TOGGLES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fortiobfuscator",
        description="Obfuscate sensitive data in a FortiGate configuration file (locally).",
    )
    p.add_argument("input", help="path to the FortiGate .conf file ('-' for stdin)")
    p.add_argument(
        "-o", "--output", help="output path (default: stdout)", default=None
    )
    p.add_argument(
        "-m",
        "--mapping",
        metavar="PATH",
        help="also write the original->replacement JSON map here (sensitive — keep local)",
    )

    # Per-type / per-category disable flags.
    for key, label in TYPE_TOGGLES:
        p.add_argument(
            f"--no-{key}",
            dest=f"no_{key}",
            action="store_true",
            help=f"do not obfuscate {label}",
        )
    for cat in CATEGORIES:
        p.add_argument(
            f"--no-{cat.key}",
            dest=f"no_{cat.key}",
            action="store_true",
            help=f"do not rename {cat.label} object names",
        )
    p.add_argument(
        "--public-ips-only",
        dest="public_ips_only",
        action="store_true",
        help="obfuscate only external (public) IPs; keep private/local addresses (RFC1918, loopback, link-local, ULA)",
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help="print a substitution summary to stderr",
    )
    return p


def options_from_args(args: argparse.Namespace) -> Options:
    types = {k for k in ALL_TYPE_KEYS if not getattr(args, f"no_{k}", False)}
    cats = {k for k in ALL_CATEGORY_KEYS if not getattr(args, f"no_{k}", False)}
    return Options(
        types=types,
        categories=cats,
        emit_mapping=bool(args.mapping),
        public_ips_only=bool(getattr(args, "public_ips_only", False)),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

    result = obfuscate(text, options_from_args(args))

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(result.text)
    else:
        sys.stdout.write(result.text)

    if args.mapping and result.mapping is not None:
        with open(args.mapping, "w", encoding="utf-8") as fh:
            json.dump(result.mapping, fh, indent=2, sort_keys=True)

    if args.summary:
        json.dump(result.report.as_dict(), sys.stderr, indent=2)
        sys.stderr.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
