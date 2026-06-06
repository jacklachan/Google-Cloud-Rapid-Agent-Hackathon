# Faultline — 3-minute demo script

Time budget: 0:00 → 3:00. Aimed at hackathon judges who have ~3 minutes per submission.

## Pre-roll setup (off-camera, before the timer starts)

- Victim service deployed clean to Cloud Run; load generator running at ~5 RPS in a hidden terminal so the dashboards have steady-state data.
- Faultline server deployed to Cloud Run; URL open in a browser tab.
- `scripts/plant_regression.py --scenario n_plus_one` queued in a second terminal, ready to run on demand.
- Cloud Run "data" service page open in a third tab so you can show the live env-var flip if asked.

## 0:00 — 0:20  Hook

> "Production just broke. The on-call wastes the first 10 minutes figuring out *which* service is actually at fault and *which commit* caused it. Faultline does that in seconds — autonomous Gemini agent on Google ADK, with the GitLab MCP server doing the heavy lifting."

Show the empty Faultline console. Point at the "Approve rollback" button area: "And it never merges on its own. A human still gates the rollback."

## 0:20 — 0:35  Plant the bug

Run, on camera:

```
python -m scripts.plant_regression --scenario n_plus_one
```

> "I'm dropping a believable regression into the victim's GitLab repo — a perf-flavoured commit that swaps a batched query for a one-by-one fetch. This is exactly the kind of change that produces a latency-creep symptom in production."

Show the new MR in GitLab, then the merge confirmation. Don't dwell.

## 0:35 — 1:30  Watch the agent investigate

Switch to the Faultline console. Click **Start investigation**.

Narrate as cards stream in (they will arrive at ~1/sec in fake mode; in live mode they'll be a bit faster).

- **Step 1 — Read the signal.** "Agent's pulling error rate on the alerting service."
- **Step 2 — Walk the cascade.** "It's not stopping at the alerting service. It's reading metrics on each downstream node and following the latency signal to its source. Look — it's switched focus from `frontend` to `data`."
- **Step 3 — Change window.** "Now it's asking GitLab MCP for recent commits on `data`."
- **Step 4 — Diff.** "Reading the diff through `get_merge_request_diffs`. This is real MCP traffic, not a screenshot."
- **Step 5 — Symptom fit.** "Here's the judgement call. Latency creep matches a query-loop change, not a 5xx-style new-dependency change."
- **Step 6 — Converge.** "One commit. With confidence and a causal chain."
- **Step 7 — Action.** "Issue + DRAFT rollback MR, both via GitLab MCP."
- **Step 8 — Stop.** "Stops. Waits."

## 1:30 — 2:00  The rollback card

Switch to the "Pending rollback" card. Click through to the postmortem issue and the DRAFT MR in GitLab.

> "The agent wrote a blameless postmortem, linked the suspect commit, and staged the revert as draft. Everything a human reviewer needs is one click away."

## 2:00 — 2:30  Approve

Back in the console. Click **Approve rollback**.

> "When I click this, Faultline strips the Draft prefix, merges the MR, the victim's GitLab CI fires, Cloud Run redeploys the reverted code."

Switch to the load generator's tail. Show p95 / error rate dropping back to baseline within ~30 seconds.

## 2:30 — 2:55  The closer

> "Three things make this work:
> One — the 8-step policy is baked verbatim into the system prompt. The agent doesn't improvise around it.
> Two — the GitLab MCP server is the load-bearing partner integration. Both the reads and the issue/MR writes go through MCP via ADK's McpToolset.
> Three — the agent literally cannot merge. The merge endpoint lives in the FastAPI server, not the toolset. Even if the LLM hallucinated a merge tool, there's no such tool registered."

## 2:55 — 3:00  Outro

> "Public repo, MIT, 46 tests green, CI runs on every push. Thanks."

## Fallback if live demo breaks

If Vertex AI or GitLab is unreachable during the demo:

1. Set `FAULTLINE_FAKE_AGENT=1` on the Cloud Run service (or restart locally with the env var).
2. Click Start. The canned step sequence will play with realistic timing.
3. The Approve button still works end-to-end (it walks the registry to `merged` without hitting GitLab).
4. Mention you're showing fake mode and the live-mode wiring is in the code + commit history.
