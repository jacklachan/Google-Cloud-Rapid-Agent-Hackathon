// Faultline web console.
//
// Phase 6 will connect EventSource to /investigate (SSE) and render each step
// the agent emits. Phase 7 wires the Approve button to POST /approve which
// auto-merges the rollback MR via GitLab MCP and triggers victim redeploy.

"use strict";

(function () {
  const status = document.getElementById("status");
  status.textContent = "phase 0 scaffold loaded — agent not wired yet";
})();
