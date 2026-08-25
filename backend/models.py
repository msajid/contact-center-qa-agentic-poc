"""Pydantic data models shared across the Contact Center QA POC.

These models define the contract between the agents, the FastAPI layer, and the
browser UI. Keeping them in one place means the simulated agent output and the
live agent output are guaranteed to have the same shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Impact = Literal["low", "medium", "high"]


class Source(BaseModel):
    """A citation backing a research finding."""

    title: str
    url: str
    publisher: str | None = None


class ProposedChange(BaseModel):
    """A concrete, reviewable change to a single KPI / SLA in the framework."""

    sla_id: str = Field(description="Identifier of the KPI/SLA being changed.")
    sla_name: str
    field: str = Field(default="target", description="Which attribute changes, e.g. 'target'.")
    current_value: str
    proposed_value: str
    rationale: str


class Finding(BaseModel):
    """A single insight produced by an agent, with an actionable suggestion."""

    id: str
    title: str
    observation: str = Field(description="What the agent noticed.")
    suggestion: str = Field(description="What the agent recommends doing about it.")
    impact: Impact = "medium"
    category: str = Field(description="QA domain, e.g. 'Coverage', 'Compliance', 'CSAT'.")
    # Per-KPI improvement plan (optional; populated for KPI-focused findings).
    kpi_id: str | None = Field(default=None, description="Framework KPI id this targets, or 'new'.")
    current_value: str | None = None
    target_value: str | None = None
    action_ideas: list[str] = Field(default_factory=list, description="Concrete steps to reach the target.")
    new_kpis: list[str] = Field(default_factory=list, description="Supporting KPIs to introduce.")
    trainings: list[str] = Field(default_factory=list, description="Agent trainings/enablement to run.")
    modern_practices: list[str] = Field(default_factory=list, description="What leading contact centers do.")
    proposed_change: ProposedChange | None = None
    sources: list[Source] = Field(default_factory=list)


class AgentResult(BaseModel):
    """The full result of running one agent."""

    agent: str
    headline: str
    summary: str
    mode: Literal["live", "simulation"] = "simulation"
    findings: list[Finding] = Field(default_factory=list)


class KPI(BaseModel):
    """A measurable standard (SLA / KPI) inside the current QA framework."""

    id: str
    name: str
    description: str
    current_target: str
    current_value: str = Field(default="", description="Mocked current average / actual for this KPI.")
    unit: str = ""
    category: str = ""
    standard: str = Field(default="", description="Governing quality standard, e.g. 'ISO 18295', 'COPC', '7-Star'.")


class ScorecardCategory(BaseModel):
    """One weighted category on the QA evaluation scorecard."""

    name: str
    weight: int
    description: str


class QAFramework(BaseModel):
    """The organisation's current quality-assurance framework."""

    name: str
    version: str
    last_reviewed: str
    coverage: str
    evaluation_method: str
    kpis: list[KPI] = Field(default_factory=list)
    scorecard: list[ScorecardCategory] = Field(default_factory=list)


class IntegrationPreview(BaseModel):
    """A before/after preview produced by 'Simulate Integration'."""

    finding_id: str
    sla_id: str | None = None
    sla_name: str | None = None
    field: str | None = None
    current_value: str | None = None
    proposed_value: str | None = None
    rationale: str
    narrative: str
    risk: Impact = "low"


class ApprovalStep(BaseModel):
    """One stop in the change-approval routing chain."""

    order: int
    role: str
    owner: str
    responsibility: str
    sla: str


class ApprovalRoute(BaseModel):
    """The full governance routing chain for approving framework changes."""

    title: str
    steps: list[ApprovalStep] = Field(default_factory=list)


# ----- Request bodies -------------------------------------------------------


class IntegrateRequest(BaseModel):
    finding_id: str
    agent: str


class ApproveRequest(BaseModel):
    finding_ids: list[str] = Field(default_factory=list)


class KpiResearchRequest(BaseModel):
    """Run the focused improvement agent for a single KPI."""

    kpi_id: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """An assistant reply plus an optional new suggestion the user can simulate."""

    reply: str
    mode: Literal["live", "simulation"] = "simulation"
    suggestion: Finding | None = None
