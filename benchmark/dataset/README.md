# Benchmark Dataset

This directory contains curated PR examples with **known bugs** used to measure
d1ff review quality (precision, recall, noise ratio).

## Directory Structure

Each dataset entry is a subdirectory named `<pr-id>/`:

```
dataset/
├── pr-001-sql-injection/
│   ├── metadata.json       # PR metadata + ground-truth known_bugs list
│   ├── diff.patch          # Full unified diff (GitHub API format)
│   └── files/              # Optional: full file contents for changed files
│       └── src/api/users.py
└── pr-002-hardcoded-secret/
    ├── metadata.json
    └── diff.patch
```

## `metadata.json` Schema

```json
{
  "pr_id": "pr-001-sql-injection",
  "repo": "example-org/example-repo",
  "title": "Human-readable PR title",
  "description": "Optional human notes about this PR",
  "known_bugs": [
    {
      "file": "src/api/users.py",
      "line": 42,
      "description": "SQL injection via unescaped user input in query string",
      "severity": "critical"
    }
  ]
}
```

### Field Descriptions

| Field | Type | Required | Description |
|---|---|---|---|
| `pr_id` | string | yes | Unique identifier matching the directory name |
| `repo` | string | yes | Source repository (owner/name) |
| `title` | string | yes | PR title |
| `description` | string | no | Human notes about the PR (not used by runner) |
| `known_bugs` | array | yes | Ground-truth bugs; may be empty for clean PRs |
| `known_bugs[].file` | string | yes | File path relative to repo root |
| `known_bugs[].line` | integer | yes | Line number of the bug in the file |
| `known_bugs[].description` | string | yes | Human description of the bug |
| `known_bugs[].severity` | string | no | `critical`, `high`, `medium`, or `low` |

## `diff.patch` Format

Standard unified diff format as returned by the GitHub API
(`application/vnd.github.v3.diff`).  Lines beginning with `+` are additions,
lines beginning with `-` are deletions.

## `files/` Directory

Optional.  When present, each file under `files/` mirrors the full content of
a changed file at its repo-relative path.  Example:

```
files/
└── src/
    └── api/
        └── users.py   ← full content of src/api/users.py after the PR
```

If `files/` is absent, the benchmark runner constructs `ReviewContext` with
`changed_files = []` (diff-only mode).

## Curation Process

1. **Find a real or synthetic PR** that contains at least one obvious, verifiable bug.
2. **Export the diff** via `gh pr diff <number> --repo <owner/repo>` and save as
   `diff.patch`.
3. **Record every known bug** in `metadata.json` under `known_bugs`, including the
   exact file path and line number where the bug appears **in the diff context** (i.e.
   the `+` line number, not the original file line number).
4. **Optionally capture full file contents** under `files/` for richer context.
5. **Add the entry directory** to this dataset and re-run
   `python benchmark/runner.py --dry-run` to confirm it loads correctly.

### Guidelines for Bug Selection

- Choose bugs that are **unambiguous** — a human reviewer would definitely flag them.
- Prefer bugs with **security impact**: injections, hardcoded secrets, path traversal.
- Include at least one **logic/off-by-one** error for recall testing.
- Avoid bugs that require deep domain knowledge to spot.
- Target a mix of languages (Python, JavaScript/TypeScript, Java, etc.).
