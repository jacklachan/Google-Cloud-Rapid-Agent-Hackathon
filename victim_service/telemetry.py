"""OpenTelemetry setup for the victim service.

Exports traces to Google Cloud Trace when GOOGLE_CLOUD_PROJECT is set,
otherwise prints to stdout. Auto-instruments FastAPI and httpx so the entire
frontend -> auth -> data chain shows up as a single trace.

Faultline's telemetry tools (phase 2) read these traces back out of Cloud
Trace + Cloud Logging to figure out the dependency graph and the alert window.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from fastapi import FastAPI


log = logging.getLogger(__name__)

_INITIALISED = False


def init_telemetry(service_name: str) -> None:
    """Configure a global TracerProvider tagged with ``service.name``.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _INITIALISED
    if _INITIALISED:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("SERVICE_VERSION", "0.0.0"),
        }
    )
    provider = TracerProvider(resource=resource)

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    use_cloud = bool(project) and os.getenv("FAULTLINE_FAKE_TELEMETRY", "0") != "1"

    if use_cloud:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            exporter = CloudTraceSpanExporter(project_id=project)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            log.info("OTel -> Cloud Trace (project=%s, service=%s)", project, service_name)
        except Exception as exc:  # exporter import or auth failure
            log.warning("Cloud Trace exporter failed (%s); falling back to console.", exc)
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        log.info("OTel -> console (service=%s)", service_name)

    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    _INITIALISED = True


def instrument_app(app: FastAPI) -> None:
    """Auto-instrument a FastAPI app. Call after init_telemetry."""
    FastAPIInstrumentor.instrument_app(app)
