"""CLI entry point."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from .config import load_config
from .diff import get_diff, get_pr_diff, parse_diff
from .output import output_findings
from .reviewer import review_diff

console = Console()


@click.group()
@click.version_option(package_name="patchpilot")
def main() -> None:
    """patchpilot — Local AI code reviewer powered by AWS Bedrock."""


@main.command()
@click.option("--pr", "pr_number", type=int, help="Review a GitHub PR by number.")
@click.option("--branch", help="Review diff of current branch vs target branch.")
@click.option("--commit", help="Review diff against a specific commit.")
@click.option("--staged", is_flag=True, help="Review only staged changes.")
@click.option("--model", help="Bedrock model ID to use.")
@click.option("--region", help="AWS region.")
@click.option("--dimensions", help="Comma-separated review dimensions.")
@click.option("--severity", help="Minimum severity threshold (critical/high/medium/low/info).")
@click.option("--output", "output_fmt", type=click.Choice(["terminal", "json"]), help="Output format.")
@click.option("--repo", help="GitHub owner/repo for PR operations.")
def review(
    pr_number: int | None,
    branch: str | None,
    commit: str | None,
    staged: bool,
    model: str | None,
    region: str | None,
    dimensions: str | None,
    severity: str | None,
    output_fmt: str | None,
    repo: str | None,
) -> None:
    """Review code changes for issues."""
    overrides = {}
    if model:
        overrides["model"] = model
    if region:
        overrides["region"] = region
    if dimensions:
        overrides["dimensions"] = [d.strip() for d in dimensions.split(",")]
    if severity:
        overrides["severity_threshold"] = severity
    if output_fmt:
        overrides["output"] = output_fmt
    if repo:
        overrides["github_owner_repo"] = repo

    config = load_config(overrides)

    with console.status("[bold cyan]Getting diff..."):
        if pr_number:
            raw_diff = get_pr_diff(pr_number, repo=config.github_owner_repo)
        else:
            raw_diff = get_diff(staged=staged, branch=branch, commit=commit)

    if not raw_diff.strip():
        console.print("[yellow]No changes to review.[/yellow]")
        return

    files = parse_diff(raw_diff)
    console.print(f"[dim]Reviewing {len(files)} file(s)...[/dim]")

    with console.status("[bold cyan]Analyzing with {model}...".format(model=config.model)):
        findings = review_diff(files, config)

    output_findings(findings, fmt=config.output)


@main.command()
@click.argument("pr_number", type=int)
@click.option("--model", help="Bedrock model ID to use.")
@click.option("--region", help="AWS region.")
@click.option("--dimensions", help="Comma-separated review dimensions.")
@click.option("--severity", help="Minimum severity threshold.")
@click.option("--repo", required=True, help="GitHub owner/repo (e.g. user/repo).")
def comment(
    pr_number: int,
    model: str | None,
    region: str | None,
    dimensions: str | None,
    severity: str | None,
    repo: str,
) -> None:
    """Review a PR and post findings as GitHub comments."""
    overrides = {"github_owner_repo": repo}
    if model:
        overrides["model"] = model
    if region:
        overrides["region"] = region
    if dimensions:
        overrides["dimensions"] = [d.strip() for d in dimensions.split(",")]
    if severity:
        overrides["severity_threshold"] = severity

    config = load_config(overrides)

    with console.status("[bold cyan]Getting PR diff..."):
        raw_diff = get_pr_diff(pr_number, repo=repo)

    if not raw_diff.strip():
        console.print("[yellow]PR has no changes to review.[/yellow]")
        return

    files = parse_diff(raw_diff)
    console.print(f"[dim]Reviewing {len(files)} file(s)...[/dim]")

    with console.status("[bold cyan]Analyzing with {model}...".format(model=config.model)):
        findings = review_diff(files, config)

    if not findings:
        console.print("[green]No issues found — nothing to post.[/green]")
        return

    console.print(f"Found {len(findings)} issue(s). Posting to PR #{pr_number}...")
    output_findings(findings, fmt="github", pr_number=pr_number, repo=repo)
