"""Per-category tally of what was obfuscated, for the UI/CLI summary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Report:
    """Counts of substitutions made, by category."""

    object_names: dict[str, int] = field(default_factory=dict)
    types: dict[str, int] = field(default_factory=dict)
    comments_removed: int = 0
    enc_redacted: int = 0
    cert_blocks_redacted: int = 0

    def total(self) -> int:
        return (
            sum(self.object_names.values())
            + sum(self.types.values())
            + self.comments_removed
            + self.enc_redacted
            + self.cert_blocks_redacted
        )

    def as_dict(self) -> dict:
        return {
            "object_names": {k: v for k, v in self.object_names.items() if v},
            "types": {k: v for k, v in self.types.items() if v},
            "comments_removed": self.comments_removed,
            "enc_redacted": self.enc_redacted,
            "cert_blocks_redacted": self.cert_blocks_redacted,
            "total": self.total(),
        }
