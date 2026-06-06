"""In-memory registry of pending rollbacks.

The agent stages a DRAFT rollback MR but never merges. The UI surfaces the
staged rollback to the human, who clicks Approve, which hits
``POST /approve/{rollback_id}`` and (phase 7) tells GitLab MCP to merge.

For phase 5 we only need this registry shape — the actual merge wire-up
lands in phase 7.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PendingRollback:
    rollback_id: str
    project_id: str
    issue_url: str
    mr_url: str
    mr_iid: int
    suspect_commit_sha: str
    status: str = "pending"  # pending | approved | merged | rejected | failed
    created_at: float = field(default_factory=time.time)
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RollbackRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, PendingRollback] = {}

    def stage(
        self,
        *,
        project_id: str,
        issue_url: str,
        mr_url: str,
        mr_iid: int,
        suspect_commit_sha: str,
    ) -> PendingRollback:
        rb = PendingRollback(
            rollback_id=uuid.uuid4().hex,
            project_id=project_id,
            issue_url=issue_url,
            mr_url=mr_url,
            mr_iid=mr_iid,
            suspect_commit_sha=suspect_commit_sha,
        )
        with self._lock:
            self._items[rb.rollback_id] = rb
        return rb

    def get(self, rollback_id: str) -> PendingRollback | None:
        with self._lock:
            return self._items.get(rollback_id)

    def all(self) -> list[PendingRollback]:
        with self._lock:
            return list(self._items.values())

    def set_status(
        self, rollback_id: str, status: str, *, error: str | None = None
    ) -> PendingRollback | None:
        with self._lock:
            rb = self._items.get(rollback_id)
            if rb is None:
                return None
            rb.status = status
            rb.last_error = error
            return rb

    def clear(self) -> None:  # mostly for tests
        with self._lock:
            self._items.clear()


# A single module-level registry is fine for the demo; the agent + the
# /pending and /approve endpoints all share it.
REGISTRY = RollbackRegistry()
