"""Module-specific exceptions for context collection."""


class ContextCollectionError(Exception):
    """Raised when GitHub API context collection fails after retry."""

    def __init__(self, stage: str, message: str, pr_number: int | None = None) -> None:
        self.stage = stage
        self.pr_number = pr_number
        super().__init__(f"[{stage}] {message}")
