"""Git diff extraction and chunking."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class FileDiff:
    path: str
    diff: str
    additions: int = 0
    deletions: int = 0


def run_git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def get_diff(
    staged: bool = False,
    branch: str | None = None,
    commit: str | None = None,
    cwd: str | None = None,
) -> str:
    if branch:
        base = run_git("merge-base", branch, "HEAD", cwd=cwd).strip()
        return run_git("diff", base, "HEAD", cwd=cwd)
    if commit:
        return run_git("diff", commit, cwd=cwd)
    if staged:
        return run_git("diff", "--cached", cwd=cwd)
    return run_git("diff", cwd=cwd)


def get_pr_diff(pr_number: int, repo: str | None = None) -> str:
    cmd = ["gh", "pr", "diff", str(pr_number)]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get PR diff: {result.stderr.strip()}")
    return result.stdout


def parse_diff(raw: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current_path = None
    current_lines: list[str] = []
    adds = 0
    dels = 0

    for line in raw.splitlines(keepends=True):
        if line.startswith("diff --git"):
            if current_path and current_lines:
                files.append(FileDiff(
                    path=current_path,
                    diff="".join(current_lines),
                    additions=adds,
                    deletions=dels,
                ))
            parts = line.split()
            current_path = parts[-1].lstrip("b/") if len(parts) >= 4 else "unknown"
            current_lines = [line]
            adds = 0
            dels = 0
        else:
            current_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                adds += 1
            elif line.startswith("-") and not line.startswith("---"):
                dels += 1

    if current_path and current_lines:
        files.append(FileDiff(
            path=current_path,
            diff="".join(current_lines),
            additions=adds,
            deletions=dels,
        ))

    return files


def estimate_tokens(text: str) -> int:
    return len(text) // 3


def chunk_diffs(files: list[FileDiff], max_tokens: int) -> list[list[FileDiff]]:
    chunks: list[list[FileDiff]] = []
    current_chunk: list[FileDiff] = []
    current_tokens = 0

    for f in files:
        file_tokens = estimate_tokens(f.diff)
        if file_tokens > max_tokens:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
            chunks.append([f])
            continue

        if current_tokens + file_tokens > max_tokens:
            chunks.append(current_chunk)
            current_chunk = [f]
            current_tokens = file_tokens
        else:
            current_chunk.append(f)
            current_tokens += file_tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
