"""One-click demo planter for /demo/plant.

Creates a fresh "regression" commit on a brand-new branch in the configured
GitLab project, opens an MR from it, and immediately merges it so the commit
lands on the default branch. The next /investigate run will find it as a
recent merge through GitLab MCP.

We deliberately do NOT flip the live victim Cloud Run env — telemetry runs in
fake-mode on the demo server so the metric anomaly always shows up regardless
of whether load is being driven. The GitLab side is fully live: the planted
commit, the postmortem issue, and the rollback MR are all real records in
mohitlalith07/faultline.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from urllib.parse import quote

import httpx


log = logging.getLogger(__name__)


_SCENARIO_TITLES = {
    "n_plus_one": "perf(data): tune query path for n_plus_one workload",
    "slow_query": "perf(data): drop redundant index on items.updated_at",
    "bad_dep": "chore(data): swap json client to ujson",
    "leaky": "feat(data): in-memory result cache for items endpoint",
}


def _base() -> str:
    return os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")


def _project() -> str:
    p = os.getenv("GITLAB_PROJECT_PATH")
    if not p:
        raise RuntimeError("GITLAB_PROJECT_PATH not set")
    return p


def _token() -> str:
    t = os.getenv("GITLAB_TOKEN")
    if not t:
        raise RuntimeError("GITLAB_TOKEN not set")
    return t


def _headers() -> dict[str, str]:
    return {"PRIVATE-TOKEN": _token(), "Accept": "application/json"}


async def plant_regression(scenario: str = "n_plus_one") -> dict[str, Any]:
    """Drop a fresh regression commit on a new branch, merge it.

    Returns the merge result (sha, mr iid, web_url) the UI can show.
    """
    scenario = (scenario or "n_plus_one").strip().lower()
    title = _SCENARIO_TITLES.get(scenario, _SCENARIO_TITLES["n_plus_one"])

    project = _project()
    base = _base()
    pid = quote(project, safe="")
    default = os.getenv("GITLAB_DEFAULT_BRANCH", "main")
    branch = f"demo-plant-{int(time.time())}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1) Get current content of the file we will edit (creates one if absent).
        ci_path = "victim_service/.gitlab-ci.yml"
        get_file = await client.get(
            f"{base}/api/v4/projects/{pid}/repository/files/{quote(ci_path, safe='')}/raw",
            headers=_headers(),
            params={"ref": default},
        )
        if get_file.status_code == 200:
            current = get_file.text
            if 'REGRESSION_MODE: ""' in current:
                new = current.replace('REGRESSION_MODE: ""', f'REGRESSION_MODE: "{scenario}"')
            else:
                # Just append a comment so the diff is non-trivial.
                new = current.rstrip("\n") + f"\n    REGRESSION_MODE: \"{scenario}\"\n"
            action = {"action": "update", "file_path": ci_path, "content": new}
        else:
            # File missing — create it with a believable yaml stub.
            new = (
                "stages:\n  - deploy\n\n"
                "deploy_to_cloud_run:\n  stage: deploy\n  variables:\n"
                f"    REGRESSION_MODE: \"{scenario}\"\n"
                "  script:\n    - echo deploy\n"
            )
            action = {"action": "create", "file_path": ci_path, "content": new}

        # 2) Single REST commit creates the branch + commits the change.
        commit = await client.post(
            f"{base}/api/v4/projects/{pid}/repository/commits",
            headers=_headers(),
            json={
                "branch": branch,
                "start_branch": default,
                "commit_message": title,
                "actions": [action],
            },
        )
        commit.raise_for_status()
        commit_sha = commit.json().get("id", "")

        # 3) Open the MR.
        mr = await client.post(
            f"{base}/api/v4/projects/{pid}/merge_requests",
            headers=_headers(),
            json={
                "source_branch": branch,
                "target_branch": default,
                "title": title,
                "description": (
                    "Planted by Faultline's one-click demo so the agent has a "
                    "real recent commit to investigate. Auto-merged after open."
                ),
            },
        )
        mr.raise_for_status()
        mr_payload = mr.json()
        mr_iid = mr_payload["iid"]

        # 4) Merge it. GitLab sometimes returns 405 immediately after MR open
        # while the diff checks are still computing; brief retry handles it.
        merged: dict[str, Any] = {}
        for attempt in range(6):
            mr_url = f"{base}/api/v4/projects/{pid}/merge_requests/{mr_iid}/merge"
            r = await client.put(
                mr_url,
                headers=_headers(),
                json={"should_remove_source_branch": True},
            )
            if r.status_code == 200:
                merged = r.json()
                break
            log.warning("merge attempt %d returned %d", attempt + 1, r.status_code)
            await _sleep(2)
        if not merged:
            raise RuntimeError(f"failed to merge planted MR !{mr_iid} after retries")

        return {
            "scenario": scenario,
            "branch": branch,
            "commit_sha": commit_sha,
            "mr_iid": mr_iid,
            "mr_url": mr_payload.get("web_url", ""),
            "merge_commit_sha": merged.get("merge_commit_sha", ""),
            "title": title,
        }


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
