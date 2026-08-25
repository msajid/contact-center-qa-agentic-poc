"""Function tools exposed to the Microsoft Agent Framework agents.

Each function is a plain, typed callable — Agent Framework turns these into tools
the model can invoke. They return JSON strings so the model receives structured,
unambiguous data. The researcher's ``search_market_benchmarks`` tool stands in
for a live web search by reading the curated 2026 knowledge base.
"""

from __future__ import annotations

import contextvars
import json
import logging
from typing import Annotated

from pydantic import Field

from .mock_data import AGENT_PERFORMANCE, CURRENT_FRAMEWORK, MARKET_BENCHMARKS, QUALITY_STANDARDS

logger = logging.getLogger("ccqa.tools")

# A streaming run sets this per-request sink (a list) so tool calls surface live in the UI.
_stream_sink: contextvars.ContextVar = contextvars.ContextVar("ccqa_stream_sink", default=None)


def emit_stream_tool(name: str) -> None:
    """Record a tool invocation on the active streaming sink, if one is set."""
    sink = _stream_sink.get()
    if sink is not None:
        sink.append({"type": "tool", "name": name})


def get_current_qa_framework() -> str:
    """Return the contact center's current QA framework (KPIs, targets, scorecard, coverage)."""
    logger.info("🔧 TOOL get_current_qa_framework() invoked by agent")
    emit_stream_tool("get_current_qa_framework")
    out = CURRENT_FRAMEWORK.model_dump_json(indent=2)
    logger.debug("🔧 TOOL get_current_qa_framework -> %d chars, %d KPIs", len(out), len(CURRENT_FRAMEWORK.kpis))
    return out


def search_market_benchmarks(
    topic: Annotated[
        str,
        Field(description="What to research, e.g. 'FCR benchmark', 'AI auto-QA coverage', 'sentiment'."),
    ] = "",
) -> str:
    """Search the latest (2026) contact center QA frameworks, KPIs and benchmarks on the web.

    Returns matching research entries, each with an insight, a numeric benchmark
    and citable sources. Pass an empty topic to retrieve the full landscape.
    """
    logger.info("🔧 TOOL search_market_benchmarks(topic=%r) invoked by agent", topic)
    emit_stream_tool("search_market_benchmarks")
    topic_l = (topic or "").lower().strip()
    if not topic_l:
        matches = MARKET_BENCHMARKS
    else:
        matches = [
            b
            for b in MARKET_BENCHMARKS
            if topic_l in b["topic"].lower()
            or topic_l in b["insight"].lower()
            or topic_l in b["benchmark"].lower()
        ] or MARKET_BENCHMARKS
    payload = [
        {
            "topic": b["topic"],
            "insight": b["insight"],
            "benchmark": b["benchmark"],
            "sources": [s.model_dump() for s in b["sources"]],
        }
        for b in matches
    ]
    logger.debug(
        "🔧 TOOL search_market_benchmarks -> %d entries: %s",
        len(payload),
        ", ".join(m["topic"] for m in payload),
    )
    return json.dumps(payload, indent=2)


def get_agent_performance_data() -> str:
    """Return the last 30 days of contact center performance data, per team and per KPI."""
    logger.info("🔧 TOOL get_agent_performance_data() invoked by agent")
    emit_stream_tool("get_agent_performance_data")
    out = json.dumps(AGENT_PERFORMANCE, indent=2)
    logger.debug(
        "🔧 TOOL get_agent_performance_data -> %d chars, %d interactions, %d teams",
        len(out),
        AGENT_PERFORMANCE.get("interactions_analyzed", 0),
        len(AGENT_PERFORMANCE.get("teams", [])),
    )
    return out


def get_quality_standards(
    standard: Annotated[
        str,
        Field(description="Optional standard code/name to filter, e.g. 'ISO 18295', 'COPC', '7-Star'. Empty returns all."),
    ] = "",
) -> str:
    """Return the quality standards governing the KPIs (ISO 18295, ISO 9001, COPC CX Standard, Global 7-Star Rating, ...).

    Use this to ground improvement recommendations in the right framework and to
    name the standard a KPI belongs to. Pass an empty value to get the full catalog.
    """
    logger.info("🔧 TOOL get_quality_standards(standard=%r) invoked by agent", standard)
    emit_stream_tool("get_quality_standards")
    q = (standard or "").lower().strip()
    if not q:
        matches = QUALITY_STANDARDS
    else:
        matches = [
            s for s in QUALITY_STANDARDS if q in s["code"].lower() or q in s["name"].lower()
        ] or QUALITY_STANDARDS
    payload = [
        {
            "code": s["code"],
            "name": s["name"],
            "body": s["body"],
            "focus": s["focus"],
            "example_metrics": s["example_metrics"],
            "sources": [src.model_dump() for src in s["sources"]],
        }
        for s in matches
    ]
    logger.debug("🔧 TOOL get_quality_standards -> %d entries: %s", len(payload), ", ".join(m["code"] for m in payload))
    return json.dumps(payload, indent=2)
