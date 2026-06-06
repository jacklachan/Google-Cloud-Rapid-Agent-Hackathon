"""The /investigate streaming engine.

Two paths:

  * **Real path** (default): runs the live ADK ``LlmAgent`` against Vertex AI,
    converts ADK ``Event``s into our SSE event shape, and writes a staged
    rollback into the in-memory registry when the agent reports one.

  * **Fake path** (``FAULTLINE_FAKE_AGENT=1``): emits a canned step sequence
    matching the active ``FAULTLINE_FAKE_SCENARIO``. This lets phase 6 UI work
    proceed without Vertex / GitLab credentials and keeps the demo flow
    parallel to the real run.

Both paths yield the same ``dict`` shape, so the SSE endpoint code in
``main.py`` is identical.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

from .events import (
    ErrorEvent,
    FinalEvent,
    RollbackStagedEvent,
    StepEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .rollbacks import REGISTRY


log = logging.getLogger(__name__)


def _fake_agent() -> bool:
    return os.getenv("FAULTLINE_FAKE_AGENT", "0") == "1"


# ---------------------------------------------------------------------------
# Fake path
# ---------------------------------------------------------------------------

_FAKE_SUSPECT_BY_SCENARIO = {
    "n_plus_one": ("a1b2c3d4", "feat(data): batch user lookups by id (N+1 fix attempt)"),
    "slow_query": ("e5f6a7b8", "perf(data): drop redundant index on items.updated_at"),
    "bad_dep": ("c9d0e1f2", "chore(data): swap json client to ujson"),
    "leaky": ("3a4b5c6d", "feat(data): in-memory result cache"),
}


async def _fake_run(scenario: str, project_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """Emit a deterministic step trace for offline UI dev + demo dry-runs."""
    sha, msg = _FAKE_SUSPECT_BY_SCENARIO.get(
        scenario, ("0000000", "feat: unknown scenario")
    )

    async def _emit(ev) -> dict[str, Any]:
        await asyncio.sleep(0.4)  # let the UI feel like work is happening
        return ev.to_dict()

    yield await _emit(StepEvent(step=1, text=f"Reading alert signal on faultline-victim-frontend (scenario={scenario})."))
    yield await _emit(ToolCallEvent(name="read_metric", args={"service": "faultline-victim-frontend", "metric": "error_rate"}))
    yield await _emit(ToolResultEvent(name="read_metric", result_preview="error_rate spiked starting -5m on frontend"))

    yield await _emit(StepEvent(step=2, text="Walking dependency graph to find the true source."))
    yield await _emit(ToolCallEvent(name="list_dependency_edges", args={"service": "faultline-victim-frontend"}))
    yield await _emit(ToolResultEvent(name="list_dependency_edges", result_preview="frontend -> [auth, data]"))
    yield await _emit(ToolCallEvent(name="read_metric", args={"service": "faultline-victim-data", "metric": "p95_latency_ms"}))
    yield await _emit(ToolResultEvent(name="read_metric", result_preview="p95 latency on data jumped from 80ms to 260ms"))
    yield await _emit(StepEvent(step=2, text="Root cause is faultline-victim-data, not frontend (cascade)."))

    yield await _emit(StepEvent(step=3, text="Establishing the change window: looking at recent merges to data."))
    yield await _emit(ToolCallEvent(name="search", args={"scope": "commits", "id": project_id}))
    yield await _emit(ToolResultEvent(name="search", result_preview=f"3 recent commits, most recent: {sha[:8]} {msg!r}"))

    yield await _emit(StepEvent(step=4, text=f"Reading suspect diff at commit {sha[:8]}."))
    yield await _emit(ToolCallEvent(name="get_merge_request_diffs", args={"id": project_id, "merge_request_iid": 42}))
    yield await _emit(ToolResultEvent(name="get_merge_request_diffs", result_preview="diff touches data/items endpoint loop"))

    yield await _emit(StepEvent(step=5, text=f"Symptom-to-change fit: scenario={scenario} matches the change type in this diff."))

    yield await _emit(StepEvent(step=6, text=f"Converging on commit {sha[:8]} as the most likely offender. Confidence: high."))

    yield await _emit(StepEvent(step=7, text="Opening postmortem issue + DRAFT rollback merge request via GitLab MCP."))
    yield await _emit(ToolCallEvent(name="create_issue", args={"id": project_id, "title": f"[faultline] Suspected regression: {sha[:8]}"}))
    issue_url = f"https://gitlab.com/{project_id}/-/issues/101"
    yield await _emit(ToolResultEvent(name="create_issue", result_preview=f"issue#101 created at {issue_url}"))
    yield await _emit(ToolCallEvent(name="create_merge_request", args={"id": project_id, "draft": True, "title": f"Draft: revert {sha[:8]}"}))
    mr_url = f"https://gitlab.com/{project_id}/-/merge_requests/77"
    yield await _emit(ToolResultEvent(name="create_merge_request", result_preview=f"draft MR!77 at {mr_url}"))

    rb = REGISTRY.stage(
        project_id=project_id,
        issue_url=issue_url,
        mr_url=mr_url,
        mr_iid=77,
        suspect_commit_sha=sha,
    )
    yield await _emit(
        RollbackStagedEvent(
            rollback_id=rb.rollback_id,
            issue_url=issue_url,
            mr_url=mr_url,
            mr_iid=77,
            project_id=project_id,
            suspect_commit_sha=sha,
        )
    )

    yield await _emit(StepEvent(step=8, text="STOP. Awaiting human approval before merging."))
    yield await _emit(
        FinalEvent(
            summary=(
                f"Suspect commit {sha[:8]} on {project_id} causes the "
                f"{scenario} symptom. Draft rollback MR is staged; click "
                f"Approve to merge and trigger redeploy."
            )
        )
    )


# ---------------------------------------------------------------------------
# Real path (ADK Runner)
# ---------------------------------------------------------------------------

def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    parts = getattr(content, "parts", None)
    if not parts:
        return ""
    out: list[str] = []
    for p in parts:
        t = getattr(p, "text", None)
        if t:
            out.append(t)
    return "".join(out)


def _result_preview(value: Any, limit: int = 240) -> str:
    try:
        return json.dumps(value, default=str)[:limit]
    except Exception:
        return str(value)[:limit]


async def _real_run(
    *,
    scenario: str,
    service: str,
    window_minutes: int,
    project_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the real ADK agent and convert its events to our SSE shape."""
    # Local imports so a missing ADK install only matters when we actually run.
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from agent.agent import build_agent

    agent = build_agent(include_gitlab=True)
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="faultline",
        session_service=session_service,
        auto_create_session=True,
    )

    # Send the agent the incident context and let the policy take over.
    user_msg = (
        f"Incident: service '{service}' is alerting over the last "
        f"{window_minutes} minutes. Scenario hint (offline replay only): "
        f"{scenario}. The project to investigate in GitLab is {project_id}. "
        "Follow the 8-step investigation policy. Stage a DRAFT rollback MR "
        "and stop for approval — do not merge."
    )

    step_counter = 0
    seen_rollback = False

    async for event in runner.run_async(
        user_id="demo",
        session_id="demo",
        new_message=user_msg,
    ):
        # Tool calls
        try:
            calls = event.get_function_calls() if hasattr(event, "get_function_calls") else []
        except Exception:
            calls = []
        for c in calls or []:
            name = getattr(c, "name", "tool")
            args = getattr(c, "args", {}) or {}
            yield ToolCallEvent(name=name, args=dict(args)).to_dict()

        # Tool results
        try:
            responses = (
                event.get_function_responses()
                if hasattr(event, "get_function_responses")
                else []
            )
        except Exception:
            responses = []
        for r in responses or []:
            name = getattr(r, "name", "tool")
            response = getattr(r, "response", None)
            preview = _result_preview(response)
            yield ToolResultEvent(name=name, result_preview=preview).to_dict()

            # Auto-stage when the agent creates an MR via GitLab MCP.
            if name == "create_merge_request" and isinstance(response, dict) and not seen_rollback:
                mr_url = response.get("web_url") or response.get("url", "")
                mr_iid = int(response.get("iid", 0) or 0)
                issue_url = ""  # populated below if we just saw create_issue
                sha = response.get("sha", "") or ""
                rb = REGISTRY.stage(
                    project_id=project_id,
                    issue_url=issue_url,
                    mr_url=mr_url,
                    mr_iid=mr_iid,
                    suspect_commit_sha=sha,
                )
                yield RollbackStagedEvent(
                    rollback_id=rb.rollback_id,
                    issue_url=issue_url,
                    mr_url=mr_url,
                    mr_iid=mr_iid,
                    project_id=project_id,
                    suspect_commit_sha=sha,
                ).to_dict()
                seen_rollback = True

        # Plain text narration
        text = _extract_text(getattr(event, "content", None))
        if text and not (calls or responses):
            partial = getattr(event, "partial", False)
            if not partial:
                step_counter += 1
                yield StepEvent(step=step_counter, text=text.strip()).to_dict()

        if hasattr(event, "is_final_response"):
            try:
                if event.is_final_response():
                    yield FinalEvent(summary=text.strip() or "Investigation complete.").to_dict()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def stream_investigation(
    *,
    service: str,
    window_minutes: int = 15,
    scenario: str | None = None,
    project_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield SSE-shaped dicts describing the agent's investigation step by step."""
    scenario = (scenario or os.getenv("FAULTLINE_FAKE_SCENARIO", "n_plus_one")).strip().lower()
    project_id = project_id or os.getenv("GITLAB_PROJECT_PATH", "demo/faultline-victim")

    try:
        if _fake_agent():
            async for ev in _fake_run(scenario, project_id):
                yield ev
        else:
            async for ev in _real_run(
                scenario=scenario,
                service=service,
                window_minutes=window_minutes,
                project_id=project_id,
            ):
                yield ev
    except Exception as exc:  # surface to the UI rather than dropping the stream
        log.exception("investigation stream failed")
        yield ErrorEvent(message=f"{type(exc).__name__}: {exc}").to_dict()
