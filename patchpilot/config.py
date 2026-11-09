"""Configuration loading and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULTS = {
    "model": "us.anthropic.claude-opus-4-6-v1",
    "region": "us-east-1",
    "max_tokens": 4096,
    "dimensions": ["bugs", "security", "performance", "simplification", "style"],
    "severity_threshold": "low",
    "max_chunk_tokens": 8000,
    "output": "terminal",
}

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


@dataclass
class Config:
    model: str = DEFAULTS["model"]
    region: str = DEFAULTS["region"]
    max_tokens: int = DEFAULTS["max_tokens"]
    dimensions: list[str] = field(default_factory=lambda: list(DEFAULTS["dimensions"]))
    severity_threshold: str = DEFAULTS["severity_threshold"]
    max_chunk_tokens: int = DEFAULTS["max_chunk_tokens"]
    output: str = DEFAULTS["output"]
    repo: str | None = None
    github_owner_repo: str | None = None

    def severity_passes(self, severity: str) -> bool:
        threshold_idx = SEVERITY_ORDER.index(self.severity_threshold)
        try:
            severity_idx = SEVERITY_ORDER.index(severity.lower())
        except ValueError:
            return True
        return severity_idx <= threshold_idx


def load_config(overrides: dict[str, Any] | None = None) -> Config:
    config_data: dict[str, Any] = {}

    for candidate in [Path(".patchpilot.yml"), Path(".patchpilot.yaml")]:
        if candidate.exists():
            with open(candidate) as f:
                config_data = yaml.safe_load(f) or {}
            break

    if overrides:
        config_data.update({k: v for k, v in overrides.items() if v is not None})

    env_model = os.environ.get("PATCHPILOT_MODEL")
    env_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if env_model:
        config_data.setdefault("model", env_model)
    if env_region:
        config_data.setdefault("region", env_region)

    return Config(**{k: v for k, v in config_data.items() if hasattr(Config, k)})
