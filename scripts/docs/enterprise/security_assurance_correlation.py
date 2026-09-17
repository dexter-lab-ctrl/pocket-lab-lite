#!/usr/bin/env python3
"""Deterministic Model <-> Assurance Evidence projection for Pocket Lab Lite."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from security_assurance_correlation_data import (
    ARCHITECTURE, REPORTS, SCENARIOS, SUITES, THREAT_MODEL, TOOLS, WALKTHROUGHS,
    build_model, current_hashes,
)

_current_hashes = current_hashes
from security_assurance_correlation_render import (
    stable,
    hub,
    model_and_evidence,
    walkthroughs,
    stride,
    owasp,
    correlation_page,
    scenario_model,
    how_to_read,
    threat_assurance,
    migration,
)

ROOT = Path(__file__).resolve().parents[3]
CORRELATION = Path("contracts/generated/documentation-enterprise/security-assurance-correlation.json")
HUB = Path("docs/generated/enterprise/hubs/security-assurance.md")
PAGES = Path("docs/generated/enterprise/hubs/security-assurance")
THREAT_ASSURANCE = Path("docs/generated/enterprise/threat-model/assurance-evidence.md")
OLD_REPORT_INDEX = Path("docs/generated/security-assurance/reports/index.md")

PRIVATE = re.compile(r"(?:(?<![A-Za-z0-9._-])/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)", re.I)
SECRET = re.compile(r"(?:BEGIN [A-Z ]*PRIVATE KEY|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,})", re.I)


def _safe_outputs(outputs: Mapping[Path, str]) -> None:
    for path, text in outputs.items():
        if PRIVATE.search(text) or SECRET.search(text):
            raise ValueError(f"unsafe generated Security Assurance projection: {path}")


def build_projection(root: Path = ROOT):
    model = build_model(root)
    outputs = {
        root / CORRELATION: stable(model),
        root / HUB: hub(model),
        root / PAGES / "model-and-evidence.md": model_and_evidence(model),
        root / PAGES / "scenario-walkthroughs.md": walkthroughs(model),
        root / PAGES / "stride-evidence.md": stride(model),
        root / PAGES / "owasp-evidence.md": owasp(model),
        root / PAGES / "model-assurance-evidence.md": correlation_page(model),
        root / PAGES / "scenario-model.md": scenario_model(model),
        root / PAGES / "how-to-read.md": how_to_read(model),
        root / THREAT_ASSURANCE: threat_assurance(model),
        root / OLD_REPORT_INDEX: migration(),
    }
    _safe_outputs(outputs)
    return outputs, model
