"""Agent orchestration for the Contact Center QA POC.

This module builds the two agents shown in the wireframe using the **Microsoft
Agent Framework** with the **Foundry chat client**:

* ``Market Benchmark Researcher`` — searches the latest 2026 QA frameworks/KPIs,
  compares them to the current framework, and proposes sourced improvements.
* ``Performance Improvement`` — analyses recent operational data and proposes
  coaching / framework changes.

If a Foundry project is not configured (or a live call fails for any reason), the
functions fall back to the pre-authored simulation in :mod:`backend.mock_data`
so the POC is always demonstrable. The live and simulated paths return the exact
same :class:`~backend.models.AgentResult` shape.
"""

from __future__ import annotations

import json
import logging
import time

from .config import settings
from .models import (
    AgentResult,
    ChatRequest,
    ChatResponse,
    Finding,
    KPI,
    ProposedChange,
    Source,
)
from .mock_data import MARKET_BENCHMARK_SIMULATION, PERFORMANCE_SIMULATION
from .tools import (
    _stream_sink,
    get_agent_performance_data,
    get_current_qa_framework,
    get_quality_standards,
    search_market_benchmarks,
)

logger = logging.getLogger("ccqa.agents")

# JSON contract the models must return. Kept identical to the AgentResult shape
# (minus the agent name / mode, which we set ourselves) so it parses cleanly.
_FINDING_SHAPE = """
Each finding has this exact shape:
{
  "id": "short-kebab-id",
  "kpi_id": "slo_voice | fcr | csat | qa | abandonment | new",
  "title": "imperative recommendation naming the KPI and its target",
  "observation": "current value vs the requirement of the governing standard, with numbers",
  "suggestion": "one-sentence what-to-do",
  "impact": "high | medium | low",
  "category": "Resolution | Efficiency | Experience | Quality | Compliance | Coverage | Coaching",
  "current_value": "value today (e.g. '70%')",
  "target_value": "ambitious but realistic target (e.g. '85%')",
  "action_ideas": ["concrete step 1", "concrete step 2", "concrete step 3"],
  "new_kpis": ["a supporting KPI to introduce", "..."],
  "trainings": ["a specific agent training / enablement", "..."],
  "modern_practices": ["a practice required or recommended by a recognised standard (ISO/COPC/7-Star)", "..."],
  "proposed_change": {
    "sla_id": "matching KPI id, or 'new'",
    "sla_name": "human name of the KPI",
    "field": "target | new_kpi | coverage | enforcement",
    "current_value": "value today",
    "proposed_value": "value you recommend",
    "rationale": "one sentence"
  },
  "sources": [ { "title": "...", "url": "...", "publisher": "..." } ]
}
""".strip()

_JSON_CONTRACT = (
    "Return ONLY a JSON object (no markdown fences, no prose) with this shape:\n"
    '{ "headline": "one-line summary with a number or two", '
    '"summary": "2-4 sentence executive summary", "findings": [ <finding>, ... ] }\n\n'
    + _FINDING_SHAPE
    + "\n\nEvery finding MUST include at least one source from the tools, a numeric "
    "target_value, and at least 3 concrete action_ideas."
)

_TONE_AND_SOURCING = (
    "Tone and sourcing rules (apply to every response):\n"
    "- Use a professional, measured, executive tone. No marketing or salesy language, no hype, "
    "and no vendor or product pitches.\n"
    "- Ground every recommendation in recognised quality standards — ISO 18295, ISO 9001, "
    "ISO 10002, ISO 30414, ISO/IEC 20000, the COPC CX Standard, and the Global 7-Star Rating "
    "— and name the governing standard together with the specific clause or requirement it draws on.\n"
    "- Citations MUST be deep and specific. Every source URL must resolve to the exact page that "
    "supports that finding — the specific standard's own page (for ISO, the "
    "iso.org/standard/<number>.html page for that exact standard; for COPC, the COPC CX Standard "
    "page) — never a homepage, a catalogue root, or a generic landing page. Put the standard "
    "part/clause in the source title where you can.\n"
    "- Prefer the exact standard pages returned by get_quality_standards and search_market_benchmarks, "
    "which already carry deep links; do not shorten or replace those URLs with a homepage. You may also "
    "use web_search to locate the precise supporting page, but restrict it to official standards sources "
    "(iso.org, copc.com, official government service-quality programmes) and cite only those specific pages.\n"
    "- Provide at least two distinct, specific sources per finding wherever possible, and never reuse a "
    "site homepage as a citation."
)

_RESEARCHER_INSTRUCTIONS = f"""
You are the Market Benchmark Researcher for a contact center quality-assurance
(QA) program. Your job is to find the latest (2026) QA frameworks, KPIs and
benchmarks, compare them against the organisation's current framework, and
recommend specific, sourced improvements for EVERY KPI.

Always work in this order:
1. Call `get_current_qa_framework` to load the KPIs and their current targets.
2. Call `get_quality_standards` to see which framework governs each KPI
   (ISO 18295, ISO 9001, COPC CX Standard, Global 7-Star Rating).
3. Call `search_market_benchmarks` (one or more times) to gather 2026 best
   practices and numeric benchmarks with sources.
4. For EACH KPI, work out an ambitious target and how to reach it, naming the
   governing standard in the observation.

Produce ONE finding per KPI for the KPIs with the biggest improvement opportunity:
cover the top 8 (or all of them when there are 8 or fewer), ordered by impact
(high first). For each KPI give a higher numeric target and fill action_ideas,
new_kpis, trainings and modern_practices with concrete, specific items.

{_TONE_AND_SOURCING}

{_JSON_CONTRACT}
""".strip()

_PERFORMANCE_INSTRUCTIONS = f"""
You are the Performance Improvement analyst for a contact center QA program. Your
job is to analyse recent operational performance and recommend coaching and
framework changes that will move the numbers.

Always work in this order:
1. Call `get_current_qa_framework` to load current KPIs and targets.
2. Call `get_agent_performance_data` to load the last 30 days of actuals.
3. Find the teams/KPIs with the largest gaps to target and the biggest risks
   (especially compliance).

Produce 3-5 findings for the KPIs/teams with the biggest gaps, ordered by impact.
For each, fill action_ideas, new_kpis, trainings and modern_practices.

{_TONE_AND_SOURCING}

{_JSON_CONTRACT}
""".strip()

_KPI_INSTRUCTIONS = f"""
You are a KPI Improvement specialist for a contact center quality-assurance program.
You focus on EXACTLY ONE KPI at a time and produce a concrete, standards-grounded plan
to improve that single KPI.

Work in this order:
1. Call `get_current_qa_framework` to load the target KPI, its current average and target.
2. Call `get_quality_standards` to ground the plan in the KPI's governing standard
   (ISO 18295, ISO 9001, COPC CX Standard, Global 7-Star Rating, ISO 30414, ISO/IEC 20000).
3. Call `search_market_benchmarks` for 2026 industry trends and numeric benchmarks with sources.

Return 2-4 findings that ALL target the requested KPI only — never drift to other KPIs.
Between them cover: how to close the gap to the current target, an ambitious next target,
current industry trends, and supporting new KPIs to introduce. In EVERY observation, name
the governing standard and quote a numeric benchmark. Fill action_ideas, new_kpis, trainings
and modern_practices with specific items, cite at least one source per finding, and set
kpi_id to the requested KPI's id.

{_TONE_AND_SOURCING}

{_JSON_CONTRACT}
""".strip()


# ---------------------------------------------------------------------------
# Live (Foundry) execution
# ---------------------------------------------------------------------------


def _build_credential():
    """Create an async Azure credential based on configuration."""
    if settings.credential_type == "cli":
        from azure.identity.aio import AzureCliCredential

        logger.debug("Building AzureCliCredential (AZURE_CREDENTIAL=cli)")
        return AzureCliCredential()
    from azure.identity.aio import DefaultAzureCredential

    logger.debug("Building DefaultAzureCredential (AZURE_CREDENTIAL=%s)", settings.credential_type)
    return DefaultAzureCredential()


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    if not text:
        raise ValueError("empty response")
    cleaned = text.strip()
    # Strip common markdown fences.
    if "```" in cleaned:
        start = cleaned.find("```")
        fence = cleaned[start + 3 :]
        if fence.lower().startswith("json"):
            fence = fence[4:]
        end = fence.find("```")
        if end != -1:
            cleaned = fence[:end].strip()
    # Fall back to the outermost balanced braces.
    if not cleaned.startswith("{"):
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise ValueError("no JSON object found in response")
        logger.debug("Parsing: extracting outermost { ... } span (chars %d..%d)", first, last)
        cleaned = cleaned[first : last + 1]
    parsed = json.loads(cleaned)
    logger.debug("Parsing: JSON OK, top-level keys=%s", list(parsed.keys()))
    return parsed


def _result_from_data(name: str, data: dict) -> AgentResult:
    """Build an AgentResult from parsed LLM JSON, repairing findings that omit fields."""
    raw = data.get("findings") or []
    findings: list[Finding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        f = dict(item)
        f.setdefault("id", str(f.get("kpi_id") or f"finding-{len(findings) + 1}"))
        f.setdefault("title", f.get("suggestion") or "Recommendation")
        f.setdefault("observation", f.get("suggestion") or f.get("title") or "")
        f.setdefault("suggestion", f.get("observation") or f.get("title") or "")
        f.setdefault("category", "Quality")
        try:
            findings.append(Finding(**f))
        except Exception as exc:  # noqa: BLE001 - skip a single malformed finding
            logger.warning("Dropping malformed finding %r: %s", f.get("id"), exc)
    return AgentResult(
        agent=name,
        mode="live",
        headline=data.get("headline", ""),
        summary=data.get("summary", ""),
        findings=findings,
    )


async def _invoke_agent(name: str, instructions: str, tools: list, prompt: str) -> str:
    """Run one agent through the Foundry chat client and return the raw text response."""
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    logger.info("\u25b6 LIVE run '%s' | endpoint=%s | model=%s", name, settings.foundry_project_endpoint, settings.foundry_model)
    credential = _build_credential()
    async with credential:
        client = FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
            credential=credential,
        )
        agent_tools = list(tools)
        if settings.enable_web_search:
            try:
                agent_tools.append(FoundryChatClient.get_web_search_tool())
                logger.debug("Added Foundry-hosted web search tool")
            except Exception:  # pragma: no cover - depends on Foundry connection
                logger.warning("Web search tool unavailable; continuing with curated benchmarks.")

        tool_names = [getattr(t, "__name__", type(t).__name__) for t in agent_tools]
        logger.info("Agent '%s' tools=%s", name, tool_names)
        logger.debug("Agent '%s' prompt: %s", name, prompt)

        started = time.perf_counter()
        async with Agent(
            client=client,
            name=name,
            instructions=instructions,
            tools=agent_tools,
        ) as agent:
            response = await agent.run(prompt)
        elapsed = time.perf_counter() - started

    text = response.text or ""
    logger.info("\u2714 LIVE '%s' responded in %.1fs (%d chars)", name, elapsed, len(text))
    logger.debug("Raw response from '%s':\n%s", name, text[:2000] + (" [truncated]" if len(text) > 2000 else ""))
    return text


async def _invoke_agent_stream(name, instructions, tools, prompt):
    """Yield streaming events (tool / reasoning / output deltas) from a live agent run."""
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    logger.info("STREAM run '%s' | endpoint=%s | model=%s", name, settings.foundry_project_endpoint, settings.foundry_model)
    credential = _build_credential()
    async with credential:
        client = FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
            credential=credential,
            additional_properties={"reasoning": {"summary": "auto"}},
        )
        agent_tools = list(tools)
        if settings.enable_web_search:
            try:
                agent_tools.append(FoundryChatClient.get_web_search_tool())
            except Exception:  # pragma: no cover - depends on Foundry connection
                logger.warning("Web search tool unavailable; continuing with curated standards.")

        seen_tools: set[str] = set()
        seen_types: set[str] = set()
        sink: list = []
        token = _stream_sink.set(sink)
        started = time.perf_counter()
        try:
            async with Agent(client=client, name=name, instructions=instructions, tools=agent_tools) as agent:
                async for update in agent.run(prompt, stream=True):
                    while sink:
                        ev = sink.pop(0)
                        nm = ev.get("name")
                        if nm and nm not in seen_tools:
                            seen_tools.add(nm)
                            yield ev
                    handled_text = False
                    for content in getattr(update, "contents", None) or []:
                        cname = type(content).__name__
                        if cname not in seen_types:
                            seen_types.add(cname)
                            logger.info("STREAM content type: %s", cname)
                        if "Function" in cname:
                            fn = getattr(content, "name", None)
                            if fn and "FunctionCall" in cname and fn not in seen_tools:
                                seen_tools.add(fn)
                                yield {"type": "tool", "name": fn}
                            continue
                        delta = getattr(content, "text", None)
                        if not delta:
                            continue
                        handled_text = True
                        if "Reasoning" in cname:
                            yield {"type": "reasoning", "delta": delta}
                        else:
                            yield {"type": "output", "delta": delta}
                    if not handled_text:
                        txt = getattr(update, "text", None)
                        if txt:
                            yield {"type": "output", "delta": txt}
                while sink:
                    ev = sink.pop(0)
                    nm = ev.get("name")
                    if nm and nm not in seen_tools:
                        seen_tools.add(nm)
                        yield ev
        finally:
            _stream_sink.reset(token)
        logger.info("STREAM '%s' finished in %.1fs", name, time.perf_counter() - started)


def _chunk_words(text, size=7):
    """Split text into small groups of words for a gradual, streamed feel."""
    words = (text or "").split(" ")
    for i in range(0, len(words), size):
        yield " ".join(words[i : i + size]) + " "


async def _run_agent_stream(name, instructions, tools, prompt, simulation):
    """Full streaming lifecycle: emit status/tool/reasoning/output events then a final 'done'."""
    yield {"type": "status", "phase": "connecting", "agent": name, "mode": current_mode()}
    if not settings.foundry_configured:
        logger.info("SIMULATION stream '%s' (Foundry not configured)", name)
        yield {"type": "status", "phase": "simulation"}
        for chunk in _chunk_words(simulation.summary):
            yield {"type": "reasoning", "delta": chunk}
        yield {"type": "done", "result": simulation}
        return
    parts: list[str] = []
    try:
        yield {"type": "status", "phase": "thinking"}
        async for event in _invoke_agent_stream(name, instructions, tools, prompt):
            if event.get("type") == "output":
                parts.append(event["delta"])
            yield event
        result = _result_from_data(name, _extract_json("".join(parts)))
        logger.info("STREAM '%s' parsed %d findings", name, len(result.findings))
        yield {"type": "done", "result": result}
    except Exception as exc:  # noqa: BLE001 - never let a live failure break the demo
        logger.exception("Live stream '%s' failed; falling back to simulation.", name)
        fallback = simulation.model_copy(
            update={"summary": "[Live Foundry call failed - showing simulated result. Reason: " + str(exc) + "]\n\n" + simulation.summary}
        )
        yield {"type": "status", "phase": "fallback", "message": str(exc)}
        yield {"type": "done", "result": fallback}


async def _run_live_agent(name: str, instructions: str, tools: list, prompt: str) -> AgentResult:
    """Run an agent and parse its JSON into an AgentResult."""
    text = await _invoke_agent(name, instructions, tools, prompt)
    result = _result_from_data(name, _extract_json(text))
    logger.info("\u2714 LIVE '%s' parsed %d findings: %s", name, len(result.findings), [f.title for f in result.findings])
    return result


async def _run_or_simulate(
    name: str,
    instructions: str,
    tools: list,
    prompt: str,
    simulation: AgentResult,
) -> AgentResult:
    """Run the agent live when possible, otherwise return the simulation."""
    if not settings.foundry_configured:
        logger.info("\u25cb SIMULATION run '%s' (Foundry not configured)", name)
        return simulation
    try:
        return await _run_live_agent(name, instructions, tools, prompt)
    except Exception as exc:  # noqa: BLE001 - POC: never let a live failure break the demo
        logger.exception("\u2716 Live agent '%s' failed; falling back to simulation.", name)
        return simulation.model_copy(
            update={
                "summary": f"[Live Foundry call failed — showing simulated result. Reason: {exc}]\n\n"
                + simulation.summary,
            }
        )


# ---------------------------------------------------------------------------
# Public API used by the FastAPI layer
# ---------------------------------------------------------------------------


async def run_market_benchmark_agent() -> AgentResult:
    """Research 2026 QA benchmarks and compare them to the current framework."""
    return await _run_or_simulate(
        name="Market Benchmark Researcher",
        instructions=_RESEARCHER_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_quality_standards, search_market_benchmarks],
        prompt=(
            "Research the latest 2026 contact center QA frameworks and KPIs, compare them "
            "to our current framework, and recommend the top 3 sourced improvements."
        ),
        simulation=MARKET_BENCHMARK_SIMULATION,
    )


async def run_performance_agent() -> AgentResult:
    """Analyse recent performance data and recommend improvements."""
    return await _run_or_simulate(
        name="Performance Improvement",
        instructions=_PERFORMANCE_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_agent_performance_data, get_quality_standards],
        prompt=(
            "Analyse our last 30 days of contact center performance against our QA targets "
            "and recommend the top 3 prioritised interventions."
        ),
        simulation=PERFORMANCE_SIMULATION,
    )


def _simulate_kpi(kpi: KPI) -> AgentResult:
    """Fallback single-KPI improvement plan built from the KPI's own data + standard."""
    std = kpi.standard or "the governing standard"
    cur = kpi.current_value or "the current level"
    tgt = kpi.current_target or "target"
    cat = kpi.category or "Quality"
    std_urls = {
        "ISO 18295": "https://www.iso.org/standard/64739.html",
        "ISO 9001": "https://www.iso.org/standard/62085.html",
        "ISO 10002": "https://www.iso.org/standard/71580.html",
        "ISO 30414": "https://www.iso.org/standard/69338.html",
        "ISO 20000": "https://www.iso.org/standard/70636.html",
        "COPC": "https://www.copc.com/copc-standards/copc-cx-standard/",
        "7-Star": "https://u.ae/en/about-the-uae/digital-uae/digital-services-adoption/global-star-rating-system-for-services",
    }
    src = Source(
        title=f"{std} \u2014 governing standard (official page)",
        url=std_urls.get(kpi.standard, "https://www.iso.org/standards-catalogue/browse-by-ics.html"),
        publisher=kpi.standard or "Standards body",
    )
    finding = Finding(
        id=f"kpi-{kpi.id}",
        kpi_id=kpi.id,
        title=f"Close the gap on {kpi.name}: {cur} \u2192 {tgt}",
        observation=(
            f"{kpi.name} is running at {cur} against a {tgt} target ({cat}, governed by {std}). "
            f"{std} requires this measure to be tracked consistently, root-caused when it is off "
            "target, and improved through documented corrective action."
        ),
        suggestion=f"Run a focused, {std}-aligned improvement review of {kpi.name} and re-baseline monthly.",
        impact="high",
        category=cat,
        current_value=cur,
        target_value=tgt,
        action_ideas=[
            f"Root-cause the top 5 drivers behind the {kpi.name} gap and assign owners",
            f"Establish a weekly {kpi.name} review showing trend, target and variance",
            "Measure the metric consistently and calibrate the method across teams",
        ],
        new_kpis=[
            f"{kpi.name} attainment trend (week-over-week)",
            f"{kpi.name} variance by team",
        ],
        trainings=[
            f"Targeted coaching for the teams lagging on {kpi.name}",
            f"{std} awareness session for team leads",
        ],
        modern_practices=[
            f"Documented corrective action and management review, as required by {std}",
            "Consistent, calibrated measurement across channels and teams",
        ],
        proposed_change=ProposedChange(
            sla_id=kpi.id, sla_name=kpi.name, field="target",
            current_value=tgt, proposed_value=tgt,
            rationale=f"Hold the {std}-aligned target and close the gap from {cur}.",
        ),
        sources=[src],
    )
    return AgentResult(
        agent=f"KPI Improvement \u2014 {kpi.name}",
        headline=f"Focused, {std}-aligned improvement plan for {kpi.name}",
        summary=(
            f"{kpi.name} sits at {cur} against a {tgt} target ({std}). The plan closes the gap "
            f"through root-cause analysis, consistent measurement, targeted coaching and the "
            f"corrective-action discipline {std} requires."
        ),
        mode="simulation",
        findings=[finding],
    )


async def run_kpi_agent(kpi: KPI) -> AgentResult:
    """Run a focused improvement analysis for a single KPI, grounded in its standard."""
    prompt = (
        "Improve ONLY this KPI and reference its governing quality standard:\n"
        f"- id: {kpi.id}\n"
        f"- name: {kpi.name}\n"
        f"- category: {kpi.category}\n"
        f"- governing standard: {kpi.standard}\n"
        f"- measurement: {kpi.description}\n"
        f"- current average: {kpi.current_value}\n"
        f"- current target: {kpi.current_target}\n\n"
        "Produce a focused improvement plan (improvements, action items, 2026 industry trends, "
        "new KPIs to introduce, trainings, modern practices) for THIS KPI only, grounded in "
        f"{kpi.standard or 'the relevant standard'} and current market benchmarks."
    )
    return await _run_or_simulate(
        name=f"KPI Improvement \u2014 {kpi.name}",
        instructions=_KPI_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_quality_standards, search_market_benchmarks],
        prompt=prompt,
        simulation=_simulate_kpi(kpi),
    )


def run_market_benchmark_agent_stream():
    """Streaming variant of the market benchmark researcher."""
    return _run_agent_stream(
        name="Market Benchmark Researcher",
        instructions=_RESEARCHER_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_quality_standards, search_market_benchmarks],
        prompt=(
            "Research the latest contact center QA standards and KPIs, compare them to our "
            "current framework, and recommend the top 3 sourced improvements."
        ),
        simulation=MARKET_BENCHMARK_SIMULATION,
    )


def run_performance_agent_stream():
    """Streaming variant of the performance improvement agent."""
    return _run_agent_stream(
        name="Performance Improvement",
        instructions=_PERFORMANCE_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_agent_performance_data, get_quality_standards],
        prompt=(
            "Analyse our last 30 days of contact center performance against our QA targets "
            "and recommend the top 3 prioritised interventions."
        ),
        simulation=PERFORMANCE_SIMULATION,
    )


def run_kpi_agent_stream(kpi: KPI):
    """Streaming variant of the focused single-KPI improvement agent."""
    prompt = (
        "Improve ONLY this KPI and reference its governing quality standard:\n"
        f"- id: {kpi.id}\n"
        f"- name: {kpi.name}\n"
        f"- category: {kpi.category}\n"
        f"- governing standard: {kpi.standard}\n"
        f"- measurement: {kpi.description}\n"
        f"- current average: {kpi.current_value}\n"
        f"- current target: {kpi.current_target}\n\n"
        "Produce a focused improvement plan (improvements, action items, industry trends, "
        "new KPIs to introduce, trainings, modern practices) for THIS KPI only, grounded in "
        f"{kpi.standard or 'the relevant standard'} and current standards-based benchmarks."
    )
    return _run_agent_stream(
        name=f"KPI Improvement - {kpi.name}",
        instructions=_KPI_INSTRUCTIONS,
        tools=[get_current_qa_framework, get_quality_standards, search_market_benchmarks],
        prompt=prompt,
        simulation=_simulate_kpi(kpi),
    )


def current_mode() -> str:
    """Return the mode the POC will use for agent runs ('live' or 'simulation')."""
    return "live" if settings.foundry_configured else "simulation"


# ---------------------------------------------------------------------------
# Chatbot: answer questions and optionally spawn a new simulatable suggestion
# ---------------------------------------------------------------------------

_CHAT_INSTRUCTIONS = (
    "You are the QA Improvement Assistant embedded in a contact center quality tool. "
    "Users ask about their KPIs, the researcher's findings, and how to improve, reduce "
    "or increase specific metrics (e.g. 'how do I cut Average Handle Time?').\n\n"
    "Ground answers with the tools: get_current_qa_framework (current KPIs/targets), "
    "get_agent_performance_data (recent actuals), search_market_benchmarks (standards-based "
    "practices), get_quality_standards (ISO 18295, ISO 9001, COPC, Global 7-Star Rating).\n\n"
    "Use a professional, measured tone with no marketing or salesy language. Ground every "
    "recommendation in recognised quality standards (ISO, COPC, Global 7-Star) and name the "
    "standard. Do not rely on general-public commentary or vendor marketing; if you use web "
    "search, restrict it to official standards sources (for example iso.org, copc.com, official "
    "government programmes) and cite only those.\n\n"
    "When the user asks how to improve/reduce/increase/change a specific KPI, ALSO return a "
    "`suggestion`: a new actionable finding they can add to the board and simulate. For a "
    "general question with no concrete change, set suggestion to null.\n\n"
    "Return ONLY a JSON object: "
    '{ "reply": "a specific, helpful answer (short bullet lines are fine)", '
    '"suggestion": null | <finding> }\n\n'
    "A <finding> has this shape:\n"
    '{ "id": "kebab-id", "kpi_id": "fcr|aht|csat|qa_score|compliance|new", "title": "...", '
    '"observation": "...", "suggestion": "...", "impact": "high|medium|low", "category": "...", '
    '"current_value": "...", "target_value": "...", "action_ideas": ["..."], "new_kpis": ["..."], '
    '"trainings": ["..."], "modern_practices": ["..."], '
    '"proposed_change": { "sla_id": "...", "sla_name": "...", "field": "target|new_kpi|coverage|enforcement", '
    '"current_value": "...", "proposed_value": "...", "rationale": "..." }, '
    '"sources": [ {"title": "...", "url": "...", "publisher": "..."} ] }'
)


def _chat_prompt(message: str, history: list, board: list[str]) -> str:
    lines: list[str] = []
    if board:
        lines.append("Suggestions currently on the board:")
        lines += [f"- {t}" for t in board]
        lines.append("")
    recent = history[-6:]
    if recent:
        lines.append("Conversation so far:")
        lines += [f"{m.role}: {m.content}" for m in recent]
        lines.append("")
    lines.append(f"User question: {message}")
    return "\n".join(lines)


async def run_chat(request: ChatRequest, board_titles: list[str]) -> ChatResponse:
    """Answer a chat question, optionally returning a new simulatable suggestion."""
    prompt = _chat_prompt(request.message, request.history, board_titles)
    if not settings.foundry_configured:
        logger.info("\u25cb SIMULATION chat (Foundry not configured)")
        return _simulate_chat(request.message)
    try:
        text = await _invoke_agent(
            name="QA Improvement Assistant",
            instructions=_CHAT_INSTRUCTIONS,
            tools=[get_current_qa_framework, get_agent_performance_data, search_market_benchmarks, get_quality_standards],
            prompt=prompt,
        )
        data = _extract_json(text)
        raw = data.get("suggestion")
        suggestion = Finding(**raw) if isinstance(raw, dict) else None
        logger.info("\u2714 LIVE chat reply (%d chars), suggestion=%s", len(data.get("reply", "")), bool(suggestion))
        return ChatResponse(reply=data.get("reply", ""), mode="live", suggestion=suggestion)
    except Exception as exc:  # noqa: BLE001
        logger.exception("\u2716 Live chat failed; falling back to a canned answer.")
        resp = _simulate_chat(request.message)
        resp.reply = f"[Live chat failed: {exc}] " + resp.reply
        return resp


def _chat_suggestion(kpi_id, title, observation, suggestion, impact, category, cur, tgt,
                     ideas, kpis, trainings, practices, sla_name, field, proposed, rationale,
                     source):
    return Finding(
        id=f"chat-{kpi_id}", kpi_id=kpi_id, title=title, observation=observation,
        suggestion=suggestion, impact=impact, category=category, current_value=cur,
        target_value=tgt, action_ideas=ideas, new_kpis=kpis, trainings=trainings,
        modern_practices=practices,
        proposed_change=ProposedChange(sla_id=kpi_id, sla_name=sla_name, field=field,
                                       current_value=cur, proposed_value=proposed, rationale=rationale),
        sources=[source],
    )


def _simulate_chat(message: str) -> ChatResponse:
    """Keyword-based fallback used when Foundry is unavailable."""
    m = message.lower()

    def has(*words: str) -> bool:
        return any(w in m for w in words)

    if has("average handle", "handle time", "aht"):
        return ChatResponse(
            mode="simulation",
            reply=("To cut Average Handle Time from ~9.4 min toward 8:00: remove long holds with "
                   "guided workflows, screen-pop customer context so agents don't re-ask, and coach "
                   "wrap-up habits. Track silence < 30s alongside AHT so faster never means worse CX."),
            suggestion=_chat_suggestion(
                "aht", "Cut Average Handle Time from 9.4 to 8:00 min",
                "AHT is 9.4 min vs a target of \u2264 8:00; long holds and re-asking drive most of the gap.",
                "Attack knowledge-base gaps behind long holds and coach hold/wrap etiquette; pair AHT with silence < 30s.",
                "medium", "Efficiency", "9.4 min", "\u2264 8:00 min",
                ["Build guided workflows for the top 10 hold reasons", "Enable screen-pop with customer history", "Coach after-call work and wrap-up scripting"],
                ["Hold time %", "Silence > 30s rate"],
                ["Efficient troubleshooting bootcamp", "Hold & transfer etiquette"],
                ["Real-time agent assist with next-best-action", "Auto-summarised wrap-up notes"],
                "Average Handle Time (AHT)", "target", "\u2264 8:00 min paired with silence < 30s",
                "Links efficiency to experience and prevents AHT gaming.",
                Source(title="COPC Customer Experience (CX) Standard 7.0", url="https://www.copc.com/copc-standards/", publisher="COPC Inc."),
            ),
        )
    if has("fcr", "first contact", "resolution"):
        return ChatResponse(
            mode="simulation",
            reply=("To lift First Contact Resolution from 70% toward 85%: measure FCR from 7-day "
                   "repeat-contact (not self-report), give agents broader resolution authority, and "
                   "target the top repeat-contact drivers with focused enablement."),
            suggestion=_chat_suggestion(
                "fcr", "Raise First Contact Resolution from 70% to 85%",
                "FCR is self-reported today; the COPC CX Standard requires it to be measured objectively, for example via a 7-day repeat-contact window.",
                "Switch FCR measurement to 7-day repeat-contact and expand agent resolution authority.",
                "high", "Resolution", "70%", "85%",
                ["Empower agents with higher refund/credit limits", "Root-cause the top 5 repeat-contact reasons", "Add a real-time knowledge assistant"],
                ["7-day repeat-contact rate", "Escalation rate"],
                ["Advanced troubleshooting certification", "Decision-making & empowerment workshop"],
                ["Predictive routing to best-fit agent", "AI knowledge surfacing during the call"],
                "First Contact Resolution (FCR)", "target", "85% (7-day repeat-contact)",
                "COPC requires objective FCR measurement; this removes self-report bias.",
                Source(title="COPC Customer Experience (CX) Standard 7.0", url="https://www.copc.com/copc-standards/", publisher="COPC Inc."),
            ),
        )
    if has("csat", "satisfaction"):
        return ChatResponse(
            mode="simulation",
            reply=("To move CSAT from 78% toward 85%: close the loop on detractors within 24h, coach "
                   "empathy on low-sentiment calls, and correlate QA scores with CSAT so the scorecard "
                   "rewards what customers actually value."),
            suggestion=_chat_suggestion(
                "csat", "Raise CSAT from 78% to 85%",
                "CSAT is 78% vs an 80% target; Billing lags at 72% with weak sentiment on disputes.",
                "Run a 24h detractor follow-up loop and coach empathy on low-sentiment interactions.",
                "high", "Experience", "78%", "85%",
                ["Trigger a 24h callback for every detractor survey", "Coach empathy on the lowest-sentiment calls", "Fix the top 3 billing-dispute pain points"],
                ["QA-to-CSAT correlation", "Detractor recovery rate"],
                ["Empathy & de-escalation training", "Billing dispute handling clinic"],
                ["Sentiment-over-time analytics", "Closed-loop VoC follow-up"],
                "Customer Satisfaction (CSAT)", "target", "85% with a quarterly QA-to-CSAT correlation \u2265 0.6",
                "Ties the scorecard to real customer outcomes.",
                Source(title="COPC Customer Experience Standard 7.0", url="https://www.copc.com/copc-standards/", publisher="COPC Inc."),
            ),
        )
    if has("compliance", "disclosure"):
        return ChatResponse(
            mode="simulation",
            reply=("To close the compliance gap (94% overall, Billing 89%): auto-flag missing "
                   "disclosures with keyword rules, make the compliance category must-pass, and "
                   "re-monitor every failed call."),
            suggestion=_chat_suggestion(
                "compliance", "Close the billing disclosure gap and enforce 100% compliance",
                "Compliance is 94% overall but Billing is 89%, with disclosures missed on 11% of dispute calls.",
                "Auto-flag missing-disclosure events and require the compliance category to pass before an interaction can score above 80.",
                "high", "Compliance", "94%", "100%",
                ["Add keyword indicators for required disclosures", "Make compliance a must-pass scorecard gate", "Mandatory re-monitoring on any failed disclosure call"],
                ["Missing-disclosure flag rate", "Audit-trail coverage"],
                ["Regulatory disclosure refresher", "Billing compliance certification"],
                ["Automated compliance monitoring on 100% of calls", "Searchable adherence audit trail"],
                "Compliance Adherence", "enforcement", "100% target + automated missing-disclosure flags",
                "Turns a monitored target into an enforced, auditable control.",
                Source(title="ISO 10002:2018 — Complaints handling in organizations", url="https://www.iso.org/standards.html", publisher="ISO"),
            ),
        )
    return ChatResponse(
        mode="simulation",
        reply=("Ask me how to improve a specific KPI \u2014 e.g. 'how do I raise FCR to 85%?' or 'how do I "
               "cut Average Handle Time?' \u2014 and I'll suggest concrete actions, new KPIs, trainings and "
               "modern practices, plus a suggestion you can simulate on the board."),
        suggestion=None,
    )
