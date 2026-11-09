"""Output formatters — terminal, JSON, GitHub PR comments."""

from __future__ import annotations

import json
import subprocess
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .reviewer import Finding

console = Console()

SEVERITY_COLORS = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}

SEVERITY_ICONS = {
    "critical": "!!",
    "high": "! ",
    "medium": "~ ",
    "low": "- ",
    "info": "  ",
}


def format_terminal(findings: list[Finding]) -> None:
    if not findings:
        console.print(Panel("[green]No issues found.[/green]", title="patchpilot"))
        return

    table = Table(title="Code Review", show_lines=True)
    table.add_column("Sev", width=8)
    table.add_column("Type", width=14)
    table.add_column("Location", width=30)
    table.add_column("Issue", min_width=40)

    for f in findings:
        color = SEVERITY_COLORS.get(f.severity, "white")
        icon = SEVERITY_ICONS.get(f.severity, "  ")
        sev = Text(f"{icon}{f.severity.upper()}", style=color)
        loc = f"{f.file}"
        if f.line:
            loc += f":{f.line}"

        detail = f"[bold]{f.title}[/bold]\n{f.description}"
        if f.suggestion:
            detail += f"\n[green]Fix: {f.suggestion}[/green]"

        table.add_row(sev, f.dimension, loc, detail)

    console.print(table)

    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary_parts = [f"[{SEVERITY_COLORS.get(s, 'white')}]{s}: {c}[/]" for s, c in counts.items()]
    console.print(f"\n  {len(findings)} findings: {', '.join(summary_parts)}")


def format_json(findings: list[Finding]) -> str:
    data = [
        {
            "file": f.file,
            "line": f.line,
            "severity": f.severity,
            "dimension": f.dimension,
            "title": f.title,
            "description": f.description,
            "suggestion": f.suggestion,
        }
        for f in findings
    ]
    return json.dumps(data, indent=2)


def post_pr_comments(
    findings: list[Finding],
    pr_number: int,
    repo: str | None = None,
) -> int:
    if not findings:
        console.print("[green]No findings to post.[/green]")
        return 0

    posted = 0
    for f in findings:
        body = f"**{SEVERITY_ICONS.get(f.severity, '')}{f.severity.upper()}** | {f.dimension}\n\n"
        body += f"**{f.title}**\n\n{f.description}"
        if f.suggestion:
            body += f"\n\n**Suggestion:** {f.suggestion}"

        if f.line and f.file:
            cmd = [
                "gh", "api",
                f"repos/{repo}/pulls/{pr_number}/comments" if repo
                else f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
                "--method", "POST",
                "-f", f"body={body}",
                "-f", f"path={f.file}",
                "-f", "subject_type=line",
                "-F", f"line={f.line}",
                "-f", "side=RIGHT",
            ]

            diff_cmd = ["gh", "pr", "diff", str(pr_number)]
            if repo:
                diff_cmd.extend(["--repo", repo])
            diff_result = subprocess.run(diff_cmd, capture_output=True, text=True)
            if diff_result.returncode != 0:
                continue

            commit_cmd = ["gh", "pr", "view", str(pr_number), "--json", "headRefOid", "-q", ".headRefOid"]
            if repo:
                commit_cmd.extend(["--repo", repo])
            commit_result = subprocess.run(commit_cmd, capture_output=True, text=True)
            if commit_result.returncode != 0:
                continue
            commit_sha = commit_result.stdout.strip()

            api_path = f"repos/{repo}/pulls/{pr_number}/comments" if repo else ""
            if not api_path:
                console.print(f"[yellow]Skipping inline comment (no repo specified): {f.title}[/yellow]")
                continue

            result = subprocess.run(
                [
                    "gh", "api", api_path,
                    "--method", "POST",
                    "-f", f"body={body}",
                    "-f", f"path={f.file}",
                    "-f", f"commit_id={commit_sha}",
                    "-F", f"line={f.line}",
                    "-f", "side=RIGHT",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                posted += 1
            else:
                console.print(f"[yellow]Failed to post comment on {f.file}:{f.line}: {result.stderr.strip()}[/yellow]")
        else:
            api_path = f"repos/{repo}/issues/{pr_number}/comments" if repo else ""
            if not api_path:
                console.print(f"[yellow]Skipping comment (no repo specified): {f.title}[/yellow]")
                continue

            result = subprocess.run(
                ["gh", "api", api_path, "--method", "POST", "-f", f"body={body}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                posted += 1

    console.print(f"\n[green]Posted {posted}/{len(findings)} comments to PR #{pr_number}[/green]")
    return posted


def output_findings(
    findings: list[Finding],
    fmt: str = "terminal",
    pr_number: int | None = None,
    repo: str | None = None,
) -> None:
    if fmt == "json":
        print(format_json(findings))
    elif fmt == "github" and pr_number:
        post_pr_comments(findings, pr_number, repo)
    else:
        format_terminal(findings)
