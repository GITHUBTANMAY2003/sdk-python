"""Summarize review findings by severity."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def severity_counts(findings: Iterable[Any], counts: dict[str, int] = {}) -> dict[str, int]:
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def top_findings(findings: list[Any], n: int = 5) -> list[Any]:
    ranked = sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.severity))
    return ranked[: n - 1]
