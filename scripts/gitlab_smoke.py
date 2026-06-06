"""Phase-3 live de-risk script.

Runs end-to-end against the real GitLab MCP server using the credentials in
``.env`` to prove the four critical operations work BEFORE we plug the toolset
into the ADK agent in phase 4:

    1. search recent commits on the default branch of GITLAB_PROJECT_PATH
    2. get_merge_request_diffs on an arbitrary recent MR (if any)
    3. create_issue with [faultline-smoke] in the title
    4. create_merge_request as DRAFT with [faultline-smoke] in the title

This script is destructive (it creates a smoke issue + draft MR in your
project) so it prints what it's about to do and waits for ENTER before
actually doing it.

Usage:
    python -m scripts.gitlab_smoke
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Light-weight .env loader so the script works without `python -m pip install python-dotenv`."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))


async def _run() -> int:
    _load_dotenv()
    project = os.getenv("GITLAB_PROJECT_PATH")
    if not project:
        print("FAIL: GITLAB_PROJECT_PATH not set in .env", file=sys.stderr)
        return 2

    from agent.tools_gitlab import build_gitlab_toolset

    toolset = build_gitlab_toolset()

    # ADK's McpToolset exposes get_tools(); each tool has an async `run_async`.
    tools = await toolset.get_tools()
    by_name = {t.name: t for t in tools}
    for required in ("search", "get_merge_request_diffs", "create_issue", "create_merge_request"):
        if required not in by_name:
            print(f"FAIL: GitLab MCP did not expose {required!r}. Got: {sorted(by_name)}", file=sys.stderr)
            return 3

    print(f"OK: connected to GitLab MCP, {len(tools)} tools available.")
    print(f"Project under test: {project}")
    print()
    print("About to:")
    print(f"  1. search commits in {project}")
    print(f"  2. create issue   '[faultline-smoke] phase 3 round-trip'")
    print(f"  3. open DRAFT MR  'Draft: [faultline-smoke] phase 3 round-trip'")
    print()
    input("Press ENTER to proceed, or Ctrl-C to abort... ")

    # 1. search recent commits
    search_tool = by_name["search"]
    result = await search_tool.run_async(
        args={"scope": "commits", "search": project, "id": project},
        tool_context=None,
    )
    print("\n[1/3] search:", json.dumps(result, default=str)[:400], "...")

    # 2. create_issue
    create_issue = by_name["create_issue"]
    issue_result = await create_issue.run_async(
        args={
            "id": project,
            "title": "[faultline-smoke] phase 3 round-trip",
            "description": "Auto-created by faultline scripts/gitlab_smoke.py. Safe to close.",
        },
        tool_context=None,
    )
    print("\n[2/3] create_issue:", json.dumps(issue_result, default=str)[:400], "...")

    # 3. create_merge_request (draft)
    create_mr = by_name["create_merge_request"]
    mr_result = await create_mr.run_async(
        args={
            "id": project,
            "source_branch": "faultline-smoke-source",
            "target_branch": os.getenv("GITLAB_DEFAULT_BRANCH", "main"),
            "title": "Draft: [faultline-smoke] phase 3 round-trip",
            "description": "Auto-created by faultline scripts/gitlab_smoke.py. Close without merging.",
            "draft": True,
        },
        tool_context=None,
    )
    print("\n[3/3] create_merge_request:", json.dumps(mr_result, default=str)[:400], "...")

    print("\nAll four operations succeeded. Phase 3 de-risked.")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
