"""Demo victim service: 3-stage chain frontend -> auth -> data.

Phase 1 will:
  - Implement the three FastAPI apps (single process, three routers, or
    three processes — phase-1 design decision).
  - Instrument with OpenTelemetry exporting to Google Cloud.
  - Add Dockerfile + Cloud Run deploy script.
  - Add .gitlab-ci.yml so an MR merge auto-redeploys on Cloud Run.
"""
