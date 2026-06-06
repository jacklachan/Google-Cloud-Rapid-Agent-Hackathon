"""Victim service: a 3-stage chain frontend -> auth -> data.

One Docker image, three roles. The SERVICE_NAME env var selects which FastAPI
app the entrypoint runs. Deploy three Cloud Run services from the same image
with SERVICE_NAME = frontend | auth | data so each gets its own URL and shows
up as a distinct node in Cloud Trace.

The frontend calls auth and data over HTTP so OpenTelemetry trace context
propagates as headers and the dep chain is visible in the Cloud Trace UI.
"""
