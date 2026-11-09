"""Send diffs to AWS Bedrock for review."""

from __future__ import annotations

import json
from dataclasses import dataclass

import boto3

from .config import Config
from .diff import FileDiff


@dataclass
class Finding:
    file: str
    line: int | None
    severity: str
    dimension: str
    title: str
    description: str
    suggestion: str | None = None


REVIEW_SYSTEM = """You are a senior code reviewer. Review the provided diff for issues.

Focus on these dimensions: {dimensions}

For each issue found, respond with a JSON array of objects:
{{
  "file": "path/to/file",
  "line": <line number or null>,
  "severity": "critical|high|medium|low|info",
  "dimension": "bugs|security|performance|simplification|style",
  "title": "Short title",
  "description": "Clear explanation of the issue",
  "suggestion": "Suggested fix or null"
}}

Rules:
- Only report real issues, not style nitpicks unless style is requested
- Be specific — reference actual code from the diff
- Line numbers should reference the new file (+) lines where possible
- If no issues found, return an empty array: []
- Return ONLY the JSON array, no other text"""


def build_prompt(files: list[FileDiff]) -> str:
    parts = ["Review this diff:\n"]
    for f in files:
        parts.append(f"## {f.path} (+{f.additions}/-{f.deletions})\n")
        parts.append(f"```diff\n{f.diff}\n```\n")
    return "\n".join(parts)


def review_chunk(files: list[FileDiff], config: Config) -> list[Finding]:
    client = boto3.client("bedrock-runtime", region_name=config.region)

    system_prompt = REVIEW_SYSTEM.format(dimensions=", ".join(config.dimensions))
    user_prompt = build_prompt(files)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": config.max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    response = client.invoke_model(
        modelId=config.model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body).encode(),
    )

    result = json.loads(response["body"].read())
    text = result["content"][0]["text"].strip()

    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    raw_findings = json.loads(text[start:end])
    findings = []
    for item in raw_findings:
        finding = Finding(
            file=item.get("file", "unknown"),
            line=item.get("line"),
            severity=item.get("severity", "info"),
            dimension=item.get("dimension", "bugs"),
            title=item.get("title", ""),
            description=item.get("description", ""),
            suggestion=item.get("suggestion"),
        )
        if config.severity_passes(finding.severity):
            findings.append(finding)
    return findings


def review_diff(files: list[FileDiff], config: Config) -> list[Finding]:
    from .diff import chunk_diffs

    chunks = chunk_diffs(files, config.max_chunk_tokens)
    all_findings: list[Finding] = []

    for chunk in chunks:
        findings = review_chunk(chunk, config)
        all_findings.extend(findings)

    all_findings.sort(
        key=lambda f: (
            ["critical", "high", "medium", "low", "info"].index(f.severity)
            if f.severity in ["critical", "high", "medium", "low", "info"]
            else 99
        )
    )
    return all_findings
