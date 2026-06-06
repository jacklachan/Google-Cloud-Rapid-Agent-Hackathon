# Faultline — Google Cloud Rapid Agent Hackathon submission (GitLab track)

## 30-second pitch

When a production service breaks, on-call wastes minutes paging through dashboards just to figure out *which* service is the root cause and *which commit* caused it. **Faultline** is an autonomous Gemini agent that does that triage in seconds: it reads Google Cloud telemetry, walks the service dependency graph to the real source of the cascade, correlates the failure window with recent GitLab commits, names the suspect, drafts the postmortem, and stages a one-click rollback merge request. Then it stops — a human still approves before anything merges.

Built on Gemini 2.5 Flash + Google ADK + the official GitLab MCP server + Cloud Run + Cloud Logging/Trace/Monitoring. Original code, MIT, in a public repo with the license committed in the first commit.

---

## Problem

The first ten minutes of an incident are the most expensive. The on-call has to answer three questions before they can do anything useful:

1. **What is broken?** Which service is the source of the cascade, not just the loudest alert?
2. **Why?** Which recent code change introduced the regression?
3. **What now?** What is the safest mitigation — rollback, hotfix, feature-flag flip?

Today, that triage is humans clicking through Cloud Monitoring, Cloud Trace, then jumping to GitLab to scroll commits, then context-switching to a draft MR. It is mechanical, recall-driven, and very repeatable — exactly the work an agent should do.

## What Faultline does

An 8-step investigation policy baked **verbatim** into the agent's system prompt (`agent/prompt.py`):

1. **Read the incident signal** — which service is alerting, on what metric, over what window.
2. **Find the true source** — walk the dependency graph from the alerting service toward the highest-contributing node. Do *not* fixate on the first red service.
3. **Establish the change window** — list GitLab commits to the suspect service deployed shortly before the failure began.
4. **Read the suspect diffs** via the GitLab MCP server.
5. **Match symptom-to-change** — latency creep → suspect added query / N+1; 5xx spike → suspect new dep / bad config; OOM → suspect resource / pool change. Rank candidates by how well the change type explains the symptom, not just by recency.
6. **Converge on one offending commit** — state confidence + causal chain (commit → mechanism → symptom).
7. **Take action via GitLab MCP** — draft a blameless postmortem, open a GitLab issue, open a DRAFT rollback merge request.
8. **Stop.** Surface everything to the human and wait for explicit approval. Never merge on its own.

The web console renders each step live as the agent emits it. When the human clicks **Approve**, Faultline strips the `Draft:` prefix from the MR, merges it via GitLab REST, the victim's `.gitlab-ci.yml` redeploys the reverted code to Cloud Run, and the system recovers in under a minute.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Reasoning LLM | **Gemini 2.5 Flash** on Vertex AI | hackathon rule 1; Flash is the cheapest GA Gemini 2.5 (free-tier friendly) and supports the function calling + MCP tools we need |
| Orchestration | **Google ADK** (`google-adk` Python) | hackathon rule 2; ADK's `McpToolset` is what connects us to GitLab |
| Partner integration | **Official GitLab MCP server** (`<gitlab>/api/v4/mcp`) via ADK `McpToolset` + `StreamableHTTPConnectionParams` + `PRIVATE-TOKEN` header | hackathon rule 3; both reads (commits/diffs) and writes (issue/MR) flow through MCP |
| Observability | **Cloud Logging / Trace / Monitoring** | hackathon rule 4; OpenTelemetry instruments the victim service and exports to Cloud Trace |
| Compute | **Cloud Run** | minimal-ops, scale-to-zero free tier; one image / three roles for the victim |
| Server | **FastAPI** + Server-Sent Events | streams the agent's step-by-step reasoning live to the UI |
| UI | **Vanilla HTML/JS/CSS** | no build step, no framework, no npm |

## What's load-bearing about GitLab

The agent cannot complete an investigation without GitLab MCP. Steps 3, 4, and 7 of the policy all call MCP tools:

- `search` (scope=commits) — find recent commits on the suspect service
- `get_merge_request_commits` and `get_merge_request_diffs` — read what changed
- `create_issue` — post the blameless postmortem
- `create_merge_request` (draft=true) — stage the rollback

The terminal merge — which fires the redeploy — is a plain GitLab REST call (`PUT /merge_requests/:iid/merge`), because the published MCP tool list does not include a merge tool. Rule 3 calls out reads + issue/MR-creation specifically; both go through MCP.

## How we comply with the hackathon rules

| Rule | Compliance |
|---|---|
| 1. Runtime LLM must be Gemini via Vertex AI | Only one LLM call site: `agent/agent.py` builds an ADK `LlmAgent(model="gemini-2.5-flash", ...)` with `GOOGLE_GENAI_USE_VERTEXAI=true`. No other LLM is imported anywhere. |
| 2. Orchestrate with Google ADK / Agent Builder | `google-adk` drives the whole agent loop. ADK `Runner`, `LlmAgent`, `McpToolset`, `InMemorySessionService`. |
| 3. Load-bearing GitLab MCP integration | All commit reads + issue/MR creation go through the official GitLab MCP server, configured via `McpToolset(connection_params=StreamableHTTPConnectionParams(url=<gitlab>/api/v4/mcp, headers={"PRIVATE-TOKEN": ...}))`. |
| 4. Google Cloud observability only | `opentelemetry-exporter-gcp-trace` from the victim; `google-cloud-logging` / `monitoring_v3` / `trace_v1` from the agent's read tools. No Datadog/Elastic/etc. |
| 5. Original code only | New repo, no prior code imported. Verified by `git log` — first commit is the MIT license + scaffold. |
| 6. Public + MIT in first commit | `LICENSE` (MIT) shipped in commit `6de412e` alongside the README. Repo is public. |

## What's interesting under the hood

- **Symptom-aware ranking.** Step 5 of the policy ranks candidate commits by how well the change *type* explains the symptom *class*, not just by recency. A latency-creep symptom prefers a commit that adds a query loop over a more recent typo-fix.
- **Fake mode end-to-end.** Every external surface has a `FAULTLINE_FAKE_*` shadow: telemetry tools, the agent run, the GitLab merge. The full 8-step demo flow can be replayed offline against canned fixtures, which made phase-by-phase development (and CI) possible without burning Vertex / GitLab quota.
- **Tool filtering.** The GitLab MCP toolset is filtered to six tools the policy actually uses. The LLM never sees the full MCP surface — fewer tools, fewer wrong turns, faster runs.
- **Human-gated merge.** The agent literally cannot merge. The merge endpoint lives in the FastAPI server, not the agent. Even if the LLM hallucinated a merge tool call, there is no such tool in the toolset.

## Tests

`pytest` covers every layer:

- `test_smoke.py` — repo importability + `/health`
- `test_victim.py` — 3-role FastAPI chain, regression toggles, request-order check
- `test_telemetry_tools.py` — fixture shapes for each anomaly class
- `test_gitlab_tools.py` — MCP wiring (endpoint, auth header, transport, allowlist)
- `test_agent_factory.py` — model id, instruction, tool set, Vertex env flags
- `test_server.py` — SSE event shape, registry, approve flow
- `test_approve.py` — fake + real merge paths, failure handling, idempotency
- `test_e2e.py` — full demo loop across all 4 scenarios

**46 tests, all passing.** A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the suite on every push.

## Repo

`https://github.com/jacklachan/Google-Cloud-Rapid-Agent-Hackathon`

## Demo

See [DEMO.md](DEMO.md) for a 3-minute scripted walkthrough.

## License

MIT © 2026 mohit
