"""Console tracing / logging setup for the Contact Center QA POC.

Turns on verbose, timestamped console logging for every layer (config, tools,
agents, HTTP requests) and best-effort OpenTelemetry spans from the Microsoft
Agent Framework so agent/model/tool activity streams to the same console.

Controlled by env vars:
* ``LOG_LEVEL``            – DEBUG (default) / INFO / WARNING ...
* ``ENABLE_AGENT_TRACES``  – "true" (default) to emit Agent Framework spans.
"""

from __future__ import annotations

import logging
import os
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# Third-party loggers that would otherwise flood the console at DEBUG.
_NOISY = (
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.identity",
    "azure.identity.aio",
    "urllib3",
    "urllib3.connectionpool",
    "httpx",
    "httpcore",
    "openai",
    "openai._base_client",
    "asyncio",
    "watchfiles",
    "watchfiles.main",
    "python_multipart",
)

_configured = False


def setup_logging() -> None:
    """Configure a single stdout handler at LOG_LEVEL for the whole app (idempotent)."""
    global _configured
    if _configured:
        return

    level_name = os.getenv("LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Our own loggers honour the configured level explicitly.
    logging.getLogger("ccqa").setLevel(level)

    # Keep chatty dependencies at WARNING so the important traces stand out.
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    logging.getLogger("ccqa.trace").info("Console logging initialised at level %s", level_name)


def enable_agent_traces() -> str:
    """Best-effort: stream Microsoft Agent Framework spans to the console.

    Returns a short status string describing what was enabled. Never raises —
    the app must run even if observability wiring is unavailable.
    """
    if os.getenv("ENABLE_AGENT_TRACES", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return "disabled (ENABLE_AGENT_TRACES=false)"

    statuses: list[str] = []

    # 1) Install a console span exporter on the global OpenTelemetry provider so
    #    any spans the Agent Framework emits are printed to this console.
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        statuses.append("otel-console")
    except Exception as exc:  # noqa: BLE001
        statuses.append(f"otel-console-failed({exc})")

    # 2) Turn on Agent Framework instrumentation so it actually emits spans.
    try:
        from agent_framework.observability import enable_instrumentation

        try:
            enable_instrumentation()
        except TypeError:
            enable_instrumentation(enable=True)  # type: ignore[call-arg]
        statuses.append("af-instrumentation")
    except Exception as exc:  # noqa: BLE001
        statuses.append(f"af-instrumentation-skipped({type(exc).__name__})")

    # 3) Include prompt / response content in the spans (debug builds only).
    try:
        from agent_framework.observability import enable_sensitive_telemetry

        try:
            enable_sensitive_telemetry()
        except TypeError:
            enable_sensitive_telemetry(True)  # type: ignore[call-arg]
        statuses.append("af-sensitive")
    except Exception:  # noqa: BLE001
        statuses.append("af-sensitive-skipped")

    return " + ".join(statuses)
