"""Shared event types streamed over /investigate (SSE).

Keeping these in one place so the web console (phase 6) and the server agree
on what fields each event type carries. All events serialise to a JSON object
shape: ``{"type": str, ...}``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(kw_only=True)
class StepEvent:
    """A narration line the agent emitted as plain text."""

    step: int
    text: str
    type: str = "step"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class ToolCallEvent:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    type: str = "tool_call"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class ToolResultEvent:
    name: str
    result_preview: str = ""
    type: str = "tool_result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class RollbackStagedEvent:
    """The agent has opened the postmortem issue + draft rollback MR.

    The ``rollback_id`` lets the UI hand it back to /approve later.
    """

    rollback_id: str
    issue_url: str
    mr_url: str
    mr_iid: int
    project_id: str
    suspect_commit_sha: str
    type: str = "rollback_staged"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class FinalEvent:
    summary: str
    type: str = "final"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class ErrorEvent:
    message: str
    type: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
