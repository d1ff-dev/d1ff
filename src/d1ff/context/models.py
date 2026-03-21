"""Pydantic contracts for the review context pipeline (AD-9)."""

from pydantic import BaseModel, ConfigDict


class FileContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str  # Relative path in repo (e.g., "src/foo/bar.py")
    content: str  # Full file contents as string
    language: str | None = None  # Inferred from extension; None if unknown


class PRMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    author: str  # GitHub login of PR author (pull_request.user.login)
    base_branch: str  # pull_request.base.ref
    head_branch: str  # pull_request.head.ref
    html_url: str
    draft: bool


class ReviewContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    installation_id: int
    pr_metadata: PRMetadata
    diff: str  # Full unified diff from GitHub API
    changed_files: list[FileContext]  # Full contents of changed files
    related_files: list[FileContext] = []  # Populated by Story 3.3 (Tree-sitter)
    lines_changed: int = 0  # Added + deleted lines in diff (NFR3)
