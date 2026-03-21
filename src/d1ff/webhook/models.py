"""Pydantic models for GitHub webhook events."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class RepositoryInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    full_name: str
    private: bool


class AccountInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    login: str
    type: str  # "User" or "Organization"


class InstallationInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    account: AccountInfo


class WebhookEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    delivery_id: str
    installation_id: int
    payload: dict  # type: ignore[type-arg]


class InstallationPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str
    installation: InstallationInfo
    repositories: list[RepositoryInfo] | None = None


class LabelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str


class PullRequestInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    state: str  # "open", "closed"
    draft: bool
    user: dict[str, Any]  # login is available as user["login"]
    base: dict[str, Any]  # branch name at base["ref"]
    head: dict[str, Any]  # branch name at head["ref"]
    html_url: str
    labels: list[LabelInfo] = []


class PullRequestPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str  # "opened", "synchronize", "reopened", "closed", etc.
    pull_request: PullRequestInfo
    repository: RepositoryInfo
    installation: InstallationInfo


PR_REVIEW_ACTIONS: frozenset[str] = frozenset({"opened", "synchronize", "reopened"})


class IssueCommentSender(BaseModel):
    model_config = ConfigDict(frozen=True)

    login: str
    type: str  # "User", "Bot", "Organization"


class IssueInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    pull_request: dict[str, object] | None = None  # Present only if comment is on a PR


class CommentInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    body: str
    user: IssueCommentSender


class IssueCommentPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str  # "created", "edited", "deleted"
    issue: IssueInfo
    comment: CommentInfo
    repository: RepositoryInfo
    installation: InstallationInfo
    sender: IssueCommentSender


class ReviewCommentInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    body: str
    user: IssueCommentSender


class PullRequestReviewCommentPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str  # 'created' | 'edited' | 'deleted'
    comment: ReviewCommentInfo
    pull_request: PullRequestInfo
    repository: RepositoryInfo
    installation: InstallationInfo
