# patchpilot

Local AI code reviewer powered by AWS Bedrock. Your code never leaves your machine.

Think **CodeRabbit**, but running locally with your own AWS credentials.

## Features

- **Local-only** — diffs are sent to your AWS Bedrock account, not a third-party SaaS
- **Git-native** — review staged changes, branches, commits, or GitHub PRs
- **Multi-dimensional** — checks for bugs, security issues, performance, simplification, and style
- **Smart chunking** — handles large diffs by splitting per-file and staying within context limits
- **Multiple outputs** — rich terminal display, JSON for CI, or post directly as GitHub PR comments
- **Configurable** — model, focus areas, severity threshold via CLI flags or `.patchpilot.yml`

## Install

```bash
pip install -e .
```

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Access to Claude models on AWS Bedrock
- `gh` CLI installed (only for PR features)

## Usage

```bash
# Review unstaged changes
patchpilot review

# Review staged changes
patchpilot review --staged

# Review a branch diff
patchpilot review --branch main

# Review a GitHub PR
patchpilot review --pr 42 --repo owner/repo

# Output as JSON (for CI)
patchpilot review --output json

# Post review as PR comments
patchpilot comment 42 --repo owner/repo

# Use a specific model
patchpilot review --model anthropic.claude-sonnet-5-5

# Focus on specific dimensions
patchpilot review --dimensions "bugs,security"

# Only show high+ severity
patchpilot review --severity high
```

## Configuration

Create `.patchpilot.yml` in your repo root:

```yaml
model: us.anthropic.claude-opus-4-6-v1
region: us-east-1
dimensions:
  - bugs
  - security
  - performance
severity_threshold: low
max_chunk_tokens: 8000
```

Environment variables:
- `PATCHPILOT_MODEL` — override model
- `AWS_REGION` — AWS region
- `AWS_DEFAULT_REGION` — fallback region

## Output Examples

### Terminal
```
┌─────────────────────────── Code Review ───────────────────────────┐
│ Sev      │ Type       │ Location        │ Issue                   │
├──────────┼────────────┼─────────────────┼─────────────────────────┤
│ !!HIGH   │ security   │ app.py:45       │ SQL injection via       │
│          │            │                 │ unsanitized user input  │
├──────────┼────────────┼─────────────────┼─────────────────────────┤
│ ~ MEDIUM │ bugs       │ utils.py:12     │ Off-by-one in loop      │
│          │            │                 │ boundary                │
└──────────┴────────────┴─────────────────┴─────────────────────────┘

  2 findings: high: 1, medium: 1
```

### JSON
```json
[
  {
    "file": "app.py",
    "line": 45,
    "severity": "high",
    "dimension": "security",
    "title": "SQL injection",
    "description": "User input passed directly to query string",
    "suggestion": "Use parameterized queries"
  }
]
```

## How It Works

1. Extracts the git diff (local or from a GitHub PR via `gh`)
2. Parses into per-file chunks, splits large diffs to stay within token limits
3. Sends each chunk to Claude on AWS Bedrock with a structured review prompt
4. Collects findings, filters by severity, sorts by priority
5. Outputs to terminal, JSON, or posts as GitHub PR comments

## License

MIT
