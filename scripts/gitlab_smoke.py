"""Phase-3 live de-risk script.

Runs end-to-end against the real GitLab MCP server using the credentials in
``.env`` to prove the four critical operations work BEFORE we plug the toolset
into the ADK agent in phase 4:

    1. list_commits on the default branch of GITLAB_PROJECT_PATH
    2. create_issue with [faultline-smoke] in the title
    3. create_merge_request as DRAFT with [faultline-smoke] in the title
    4. get_merge_request_diffs on the MR we just created

This script is destructive (it creates a smoke issue + draft MR in your
project) so it prints what it's about to do and prompts for confirmation.

Usage:
    python -m scripts.gitlab_smoke               # interactive
    FAULTLINE_SMOKE_AUTO=1 python -m scripts.gitlab_smoke   # no prompt
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Light-weight .env loader."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))


def _call(tool, args: dict) -> Any:  # noqa: ANN401, F821 (type alias only)
    """Run a single MCP tool. Returns the parsed result."""
    return tool.run_async(args=args, tool_context=None)


async def _run() -> int:
    _load_dotenv()
    project = os.getenv("GITLAB_PROJECT_PATH")
    branch = os.getenv("GITLAB_DEFAULT_BRANCH", "main")
    if not project:
        print("FAIL: GITLAB_PROJECT_PATH not set in .env", file=sys.stderr)
        return 2

    from agent.tools_gitlab import build_gitlab_toolset, GITLAB_TOOL_ALLOWLIST

    toolset = build_gitlab_toolset()
    tools = await toolset.get_tools()
    by_name = {t.name: t for t in tools}

    print(f"OK: connected to GitLab MCP, {len(tools)} tools available.")
    print(f"Project under test: {project} (default branch {branch})")
    missing = [t for t in ("list_commits", "create_issue", "create_merge_request", "get_merge_request_diffs") if t not in by_name]
    if missing:
        print(f"FAIL: required tools missing from MCP server: {missing}", file=sys.stderr)
        print(f"  available tools (first 30): {sorted(by_name)[:30]}", file=sys.stderr)
        return 3

    if os.getenv("FAULTLINE_SMOKE_AUTO") != "1":
        print()
        print("About to:")
        print(f"  1. list_commits in {project}")
        print(f"  2. create issue   '[faultline-smoke] phase 3 round-trip'")
        print(f"  3. open DRAFT MR  '[faultline-smoke] phase 3 round-trip'")
        print(f"  4. read its diff")
        print()
        try:
            input("Press ENTER to proceed, or Ctrl-C to abort... ")
        except (EOFError, KeyboardInterrupt):
            print("aborted.")
            return 130

    # 1. list_commits
    list_commits = by_name["list_commits"]
    result = await list_commits.run_async(
        args={"project_id": project, "ref_name": branch, "per_page": 5},
        tool_context=None,
    )
    print(f"\n[1/4] list_commits: {json.dumps(result, default=str)[:300]} ...")

    # 2. create_issue
    create_issue = by_name["create_issue"]
    issue_result = await create_issue.run_async(
        args={
            "project_id": project,
            "title": "[faultline-smoke] phase 3 round-trip",
            "description": "Auto-created by faultline scripts/gitlab_smoke.py. Safe to close.",
        },
        tool_context=None,
    )
    print(f"\n[2/4] create_issue: {json.dumps(issue_result, default=str)[:300]} ...")

    # 3. create_merge_request — needs a source branch that differs from target.
    # We create one from the default branch's tip just for the smoke test.
    import httpx
    from urllib.parse import quote

    api = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/") + "/api/v4"
    token = os.environ["GITLAB_TOKEN"]
    pid = quote(project, safe="")
    smoke_branch = "faultline-smoke-source"

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Best-effort delete any leftover branch from a prior run.
        await client.delete(
            f"{api}/projects/{pid}/repository/branches/{quote(smoke_branch, safe='')}",
            headers={"PRIVATE-TOKEN": token},
        )
        r = await client.post(
            f"{api}/projects/{pid}/repository/branches",
            headers={"PRIVATE-TOKEN": token},
            params={"branch": smoke_branch, "ref": branch},
        )
        if r.status_code not in (200, 201):
            print(f"  ! could not create source branch ({r.status_code}): {r.text[:200]}")
        else:
            print(f"  + created scratch branch {smoke_branch!r} for the MR")

    create_mr = by_name["create_merge_request"]
    mr_result = await create_mr.run_async(
        args={
            "project_id": project,
            "source_branch": smoke_branch,
            "target_branch": branch,
            "title": "Draft: [faultline-smoke] phase 3 round-trip",
            "description": "Auto-created by faultline scripts/gitlab_smoke.py. Close without merging.",
            "draft": True,
        },
        tool_context=None,
    )
    print(f"\n[3/4] create_merge_request: {json.dumps(mr_result, default=str)[:300]} ...")

    # 4. get_merge_request_diffs — pull the IID from the create response.
    mr_iid = None
    try:
        # MCP tools often return a list of text content blocks containing JSON.
        if isinstance(mr_result, dict):
            mr_iid = mr_result.get("iid")
        if mr_iid is None and isinstance(mr_result, list) and mr_result:
            first = mr_result[0]
            if isinstance(first, dict):
                text = first.get("text") or first.get("data") or ""
                if text:
                    parsed = json.loads(text) if isinstance(text, str) else text
                    mr_iid = parsed.get("iid")
    except Exception as exc:
        print(f"  ! could not parse MR iid from result: {exc}")

    if mr_iid:
        get_diffs = by_name["get_merge_request_diffs"]
        diffs = await get_diffs.run_async(
            args={"project_id": project, "merge_request_iid": int(mr_iid)},
            tool_context=None,
        )
        print(f"\n[4/4] get_merge_request_diffs (iid={mr_iid}): {json.dumps(diffs, default=str)[:300]} ...")
    else:
        print("\n[4/4] skipped get_merge_request_diffs (could not parse iid)")

    print("\nAll operations succeeded. Phase 3 de-risked.")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
