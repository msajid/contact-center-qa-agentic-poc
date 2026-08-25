"""FastAPI application for the Contact Center QA POC.

Serves the browser UI and the JSON API that drives it:

* ``GET  /api/status``                      – live vs. simulation mode + config
* ``GET  /api/framework``                   – the current (working) QA framework
* ``POST /api/research/market-benchmark``   – run the researcher agent
* ``POST /api/research/performance``        – run the performance agent
* ``POST /api/integrate``                   – preview a finding's change (diff)
* ``POST /api/approve``                     – apply approved changes + route
* ``GET  /api/approval-route``              – governance routing chain
* ``POST /api/reset``                       – restore the original framework
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agents import (
    current_mode,
    run_chat,
    run_kpi_agent,
    run_kpi_agent_stream,
    run_market_benchmark_agent,
    run_market_benchmark_agent_stream,
    run_performance_agent,
    run_performance_agent_stream,
)
from .config import settings
from .mock_data import APPROVAL_ROUTE, CURRENT_FRAMEWORK
from .models import (
    AgentResult,
    ApprovalRoute,
    ApproveRequest,
    ChatRequest,
    ChatResponse,
    Finding,
    IntegrateRequest,
    IntegrationPreview,
    KPI,
    KpiResearchRequest,
    QAFramework,
)
from .observability import enable_agent_traces

# Logging is configured on import of .config (setup_logging). Grab our logger.
logger = logging.getLogger("ccqa.api")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Contact Center QA POC", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_TRACE_STATUS = enable_agent_traces()
logger.info("=" * 68)
logger.info("Contact Center QA POC starting")
logger.info("  mode            : %s", current_mode())
logger.info("  model           : %s", settings.foundry_model)
logger.info("  web search      : %s", settings.enable_web_search)
logger.info("  agent tracing   : %s", _TRACE_STATUS)
logger.info("=" * 68)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    """Log every HTTP request/response with timing (API at INFO, assets at DEBUG)."""
    started = time.perf_counter()
    is_api = request.url.path.startswith("/api")
    emit = logger.info if is_api else logger.debug
    emit("\u2192 %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("\u2716 %s %s raised an unhandled error", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    emit("\u2190 %s %s \u2192 %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


class WorkspaceState:
    """In-memory demo state: a mutable framework + a cache of agent findings."""

    def __init__(self) -> None:
        self.framework: QAFramework = CURRENT_FRAMEWORK.model_copy(deep=True)
        self.findings: dict[str, Finding] = {}
        self.approved: set[str] = set()
        self.chat_seq: int = 0

    def cache(self, result: AgentResult) -> None:
        for finding in result.findings:
            self.findings[finding.id] = finding
        logger.debug(
            "State cached %d findings from '%s': %s",
            len(result.findings),
            result.agent,
            [f.id for f in result.findings],
        )

    def get_finding(self, finding_id: str) -> Finding:
        finding = self.findings.get(finding_id)
        if finding is None:
            raise HTTPException(status_code=404, detail=f"Unknown finding '{finding_id}'. Run the agent first.")
        return finding

    def reset(self) -> None:
        self.framework = CURRENT_FRAMEWORK.model_copy(deep=True)
        self.approved.clear()


state = WorkspaceState()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@app.get("/api/status")
async def get_status() -> dict:
    return {
        "mode": current_mode(),
        "foundry_configured": settings.foundry_configured,
        "model": settings.foundry_model,
        "web_search": settings.enable_web_search,
    }


@app.get("/api/framework", response_model=QAFramework)
async def get_framework() -> QAFramework:
    return state.framework


@app.post("/api/research/market-benchmark", response_model=AgentResult)
async def research_market_benchmark() -> AgentResult:
    logger.info("API research/market-benchmark: running Market Benchmark Researcher…")
    result = await run_market_benchmark_agent()
    state.cache(result)
    logger.info("API research/market-benchmark: %s mode, %d findings", result.mode, len(result.findings))
    return result


@app.post("/api/research/performance", response_model=AgentResult)
async def research_performance() -> AgentResult:
    logger.info("API research/performance: running Performance Improvement…")
    result = await run_performance_agent()
    state.cache(result)
    logger.info("API research/performance: %s mode, %d findings", result.mode, len(result.findings))
    return result


@app.post("/api/research/kpi", response_model=AgentResult)
async def research_kpi(req: KpiResearchRequest) -> AgentResult:
    kpi = next((k for k in state.framework.kpis if k.id == req.kpi_id), None)
    if kpi is None:
        raise HTTPException(status_code=404, detail=f"Unknown KPI '{req.kpi_id}'. Reload the framework and retry.")
    logger.info("API research/kpi: focused improvement for %s (%s), standard=%s…", kpi.id, kpi.name, kpi.standard)
    result = await run_kpi_agent(kpi)
    state.cache(result)
    logger.info("API research/kpi: %s mode, %d findings for %s", result.mode, len(result.findings), kpi.id)
    return result


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _sse_stream(agen):
    """Serialize an agent event stream as Server-Sent Events, caching the final result."""
    try:
        async for event in agen:
            if event.get("type") == "done":
                result = event["result"]
                state.cache(result)
                payload = {"type": "done", "result": result.model_dump()}
            else:
                payload = event
            yield f"data: {json.dumps(payload)}\n\n"
    except Exception as exc:  # noqa: BLE001 - a stream must always terminate cleanly
        logger.exception("SSE stream failed")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"


@app.post("/api/research/market-benchmark/stream")
async def research_market_benchmark_stream() -> StreamingResponse:
    logger.info("API research/market-benchmark/stream: streaming run...")
    return StreamingResponse(_sse_stream(run_market_benchmark_agent_stream()), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/research/performance/stream")
async def research_performance_stream() -> StreamingResponse:
    logger.info("API research/performance/stream: streaming run...")
    return StreamingResponse(_sse_stream(run_performance_agent_stream()), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/research/kpi/stream")
async def research_kpi_stream(req: KpiResearchRequest) -> StreamingResponse:
    kpi = next((k for k in state.framework.kpis if k.id == req.kpi_id), None)
    if kpi is None:
        raise HTTPException(status_code=404, detail=f"Unknown KPI '{req.kpi_id}'. Reload the framework and retry.")
    logger.info("API research/kpi/stream: streaming focused improvement for %s...", kpi.id)
    return StreamingResponse(_sse_stream(run_kpi_agent_stream(kpi)), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/integrate", response_model=IntegrationPreview)
async def integrate(req: IntegrateRequest) -> IntegrationPreview:
    logger.info("API integrate: finding_id=%s agent=%s", req.finding_id, req.agent)
    finding = state.get_finding(req.finding_id)
    change = finding.proposed_change
    if change is None:
        return IntegrationPreview(
            finding_id=finding.id,
            rationale=finding.suggestion,
            narrative=f"'{finding.title}' would be adopted as guidance (no single KPI value changes).",
            risk=finding.impact,
        )

    is_new = change.field in {"new_kpi"} or change.sla_id == "new"
    if is_new:
        narrative = (
            f"Simulating integration would ADD a new KPI '{change.sla_name}' to the framework, "
            f"tracked as: {change.proposed_value}."
        )
    else:
        narrative = (
            f"Simulating integration would update '{change.sla_name}' from "
            f"'{change.current_value}' to '{change.proposed_value}'."
        )

    return IntegrationPreview(
        finding_id=finding.id,
        sla_id=change.sla_id,
        sla_name=change.sla_name,
        field=change.field,
        current_value=change.current_value,
        proposed_value=change.proposed_value,
        rationale=change.rationale,
        narrative=narrative,
        risk=finding.impact,
    )


@app.post("/api/approve")
async def approve(req: ApproveRequest) -> dict:
    logger.info("API approve: %d finding(s) %s", len(req.finding_ids), req.finding_ids)
    if not req.finding_ids:
        raise HTTPException(status_code=400, detail="No findings selected for approval.")

    applied: list[dict] = []
    for finding_id in req.finding_ids:
        finding = state.get_finding(finding_id)
        state.approved.add(finding_id)
        change = finding.proposed_change
        if change is None:
            applied.append({"finding_id": finding_id, "change": "Adopted as guidance."})
            continue

        is_new = change.field == "new_kpi" or change.sla_id == "new"
        if is_new:
            new_id = finding.id.replace("mb-", "").replace("pi-", "") or finding.id
            if not any(k.id == new_id for k in state.framework.kpis):
                state.framework.kpis.append(
                    KPI(
                        id=new_id,
                        name=change.sla_name,
                        description=finding.suggestion,
                        current_target=change.proposed_value,
                        category=finding.category,
                    )
                )
            applied.append({"finding_id": finding_id, "change": f"Added KPI '{change.sla_name}'."})
        else:
            for kpi in state.framework.kpis:
                if kpi.id == change.sla_id:
                    kpi.current_target = change.proposed_value
                    applied.append(
                        {
                            "finding_id": finding_id,
                            "change": f"{kpi.name}: {change.current_value} → {change.proposed_value}",
                        }
                    )
                    break

    # Reflect that the framework has moved to the next version.
    state.framework.version = "v3.0 (2026, pending approval)"
    state.framework.last_reviewed = "2026-08-18"

    logger.info("API approve: applied %d change(s); framework now %s", len(applied), state.framework.version)
    for entry in applied:
        logger.debug("  applied \u2192 %s", entry["change"])

    return {
        "approved": sorted(state.approved),
        "applied": applied,
        "framework": state.framework.model_dump(),
        "route": APPROVAL_ROUTE.model_dump(),
    }


@app.get("/api/approval-route", response_model=ApprovalRoute)
async def approval_route() -> ApprovalRoute:
    return APPROVAL_ROUTE


@app.post("/api/reset")
async def reset() -> dict:
    logger.info("API reset: restoring original framework")
    state.reset()
    return {"status": "reset", "framework": state.framework.model_dump()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    logger.info("API chat: %r", req.message[:120])
    board_titles = [f.title for f in state.findings.values()]
    result = await run_chat(req, board_titles)
    if result.suggestion is not None:
        state.chat_seq += 1
        result.suggestion.id = f"{result.suggestion.id}-{state.chat_seq}"
        state.findings[result.suggestion.id] = result.suggestion
        logger.info("API chat: %s mode, spawned suggestion %s", result.mode, result.suggestion.id)
    else:
        logger.info("API chat: %s mode, no suggestion", result.mode)
    return result


# Serve the browser UI (mounted last so /api routes take precedence).
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
