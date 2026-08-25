"""Creative but realistic mock data for the Contact Center QA POC.

Nothing here calls a real service. It represents:

* ``CURRENT_FRAMEWORK`` – the QA program a contact center is running *today*.
* ``AGENT_PERFORMANCE`` – recent operational data used by the performance agent.
* ``MARKET_BENCHMARKS`` – a curated "2026 web research" knowledge base that the
  researcher agent's search tool draws from (stands in for a live web search).
* ``*_SIMULATION`` – pre-authored agent output used when Foundry is not
  configured, so the UI always has something rich to show.
"""

from __future__ import annotations

from .models import (
    AgentResult,
    ApprovalRoute,
    ApprovalStep,
    Finding,
    KPI,
    ProposedChange,
    QAFramework,
    ScorecardCategory,
    Source,
)

# ---------------------------------------------------------------------------
# 1. The QA framework the contact center runs today (deliberately a bit dated).
# ---------------------------------------------------------------------------

CURRENT_FRAMEWORK = QAFramework(
    name="Contact Center SLA & KPI Framework",
    version="v2.1 (2024)",
    last_reviewed="2024-11-02",
    coverage="18 SLAs/KPIs across 6 categories; QA sampled at ~3% of interactions today",
    evaluation_method="Each KPI = eligible outcomes ÷ total eligible × 100, measured monthly against target",
    kpis=[
        # --- Business KPIs ---
        KPI(id="slo_voice", name="Service Level Objective – Voice", description="Calls answered within target ÷ eligible offered calls × 100", current_target="80% within 20s", unit="%", category="Business KPIs", standard="ISO 18295"),
        KPI(id="rto_deferred", name="Response Time Objective – Deferred Channels", description="Transactions responded within RTO ÷ eligible transactions × 100 (email, chat, complaints, back-office)", current_target="90% within RTO", unit="%", category="Business KPIs", standard="ISO 18295"),
        KPI(id="abandonment", name="Abandonment Rate", description="Calls abandoned after entering the queue ÷ eligible offered calls × 100", current_target="≤ 5%", unit="%", category="Business KPIs", standard="COPC"),
        KPI(id="callback_completion", name="Callback Completion", description="Successfully completed callbacks ÷ valid callback requests × 100", current_target="≥ 95%", unit="%", category="Business KPIs", standard="COPC"),
        KPI(id="callback_sla", name="Callback Within SLA", description="Callbacks completed within the promised time ÷ valid callback requests × 100", current_target="≥ 90%", unit="%", category="Business KPIs", standard="COPC"),
        KPI(id="customer_voice_sl", name="Customer Voice Service Level", description="Valid Customer Voice cases completed within SLA ÷ total valid cases × 100", current_target="≥ 90%", unit="%", category="Business KPIs", standard="ISO 18295"),
        KPI(id="qa", name="Quality Assurance", description="Transactions without customer-critical errors ÷ monitored transactions × 100", current_target="≥ 90%", unit="%", category="Business KPIs", standard="ISO 9001"),
        KPI(id="csat", name="Consolidated CSAT – All Channels", description="Σ(Channel CSAT × eligible volume) ÷ total eligible volume", current_target="≥ 85%", unit="%", category="Business KPIs", standard="COPC"),
        KPI(id="kb_accuracy", name="Knowledgebase Accuracy", description="Knowledge items without critical errors ÷ items checked × 100", current_target="≥ 95%", unit="%", category="Business KPIs", standard="ISO 9001"),
        # --- Staffing ---
        KPI(id="fcr", name="Agent FCR", description="Eligible interactions resolved at first contact ÷ total eligible interactions × 100", current_target="≥ 75%", unit="%", category="Staffing", standard="COPC"),
        KPI(id="esat", name="Employee Satisfaction – ESAT", description="Satisfied / top-box employee responses ÷ total valid responses × 100", current_target="≥ 80%", unit="%", category="Staffing", standard="ISO 30414"),
        # --- Global Stars Rating ---
        KPI(id="global_stars", name="Global Stars Rating", description="Σ(Criteria score × weight) ÷ Σ(Max score × weight) × 100 (UAE Global Star Rating)", current_target="4★ (≥ 80%)", unit="%", category="Global Stars Rating", standard="7-Star"),
        # --- Technology & Building ---
        KPI(id="tech_availability", name="Technology Availability", description="Available operating time ÷ scheduled operating time × 100", current_target="≥ 99.5%", unit="%", category="Technology & Building", standard="ISO 20000"),
        # --- General Items ---
        KPI(id="equipment_readiness", name="Equipment Readiness", description="Operational equipment/workstations ÷ required equipment/workstations × 100", current_target="100%", unit="%", category="General Items", standard="7-Star"),
        KPI(id="facility_compliance", name="Building/Facility Compliance", description="Compliant facility requirements ÷ applicable requirements × 100", current_target="100%", unit="%", category="General Items", standard="7-Star"),
        KPI(id="general_compliance", name="General Requirements Compliance", description="Compliant applicable requirements ÷ total requirements assessed × 100", current_target="100%", unit="%", category="General Items", standard="7-Star"),
        # --- Human Resources ---
        KPI(id="recruitment_ontime", name="Recruitment On-Time Achievement", description="Positions filled within the agreed timeline ÷ positions due to be filled × 100", current_target="≥ 90%", unit="%", category="Human Resources", standard="ISO 30414"),
        KPI(id="new_hire_success", name="Quality of Hiring – New Hire Success Rate", description="New hires passing training, nesting & probation ÷ eligible new hires × 100", current_target="≥ 85%", unit="%", category="Human Resources", standard="ISO 30414"),
    ],
    scorecard=[
        ScorecardCategory(name="Greeting & Opening", weight=10, description="Branded greeting, identity verification."),
        ScorecardCategory(name="Communication Clarity", weight=20, description="Clear, jargon-free, well-paced."),
        ScorecardCategory(name="Problem Resolution", weight=35, description="Correct diagnosis and complete resolution."),
        ScorecardCategory(name="Compliance & Disclosures", weight=20, description="Mandatory disclosures and data handling."),
        ScorecardCategory(name="Empathy & Closing", weight=15, description="Acknowledgement, recap, next steps."),
    ],
)


# ---------------------------------------------------------------------------
# 2. Recent operational performance data (mock) for the performance agent.
# ---------------------------------------------------------------------------

AGENT_PERFORMANCE = {
    "period": "Last 30 days",
    "interactions_analyzed": 42875,
    "channels": {"voice": 0.58, "chat": 0.27, "email": 0.15},
    "kpi_actuals": {
        "slo_voice": "76% within 20s",
        "rto_deferred": "84% within RTO",
        "abandonment": "7.8%",
        "callback_completion": "91%",
        "callback_sla": "83%",
        "customer_voice_sl": "88%",
        "qa": "87%",
        "csat": "79%",
        "kb_accuracy": "92%",
        "fcr": "68%",
        "esat": "74%",
        "global_stars": "78%",
        "tech_availability": "99.1%",
        "equipment_readiness": "97%",
        "facility_compliance": "96%",
        "general_compliance": "94%",
        "recruitment_ontime": "82%",
        "new_hire_success": "80%",
    },
    "teams": [
        {"team": "Billing & Payments", "slo_voice": "71% in 20s", "fcr": "61%", "csat": "72%", "qa": "84%", "abandonment": "9.4%"},
        {"team": "Technical Support", "slo_voice": "74% in 20s", "fcr": "64%", "csat": "75%", "qa": "82%", "abandonment": "6.1%"},
        {"team": "Retention", "slo_voice": "83% in 20s", "fcr": "71%", "csat": "83%", "qa": "88%", "abandonment": "3.9%"},
        {"team": "General Inquiries", "slo_voice": "86% in 20s", "fcr": "74%", "csat": "81%", "qa": "86%", "abandonment": "4.2%"},
    ],
    "signals": [
        "Voice service level 76% vs the 80%/20s target; abandonment 7.8% exceeds the 5% ceiling.",
        "Agent FCR 68% vs the 75% target, with Billing lagging at 61%.",
        "Consolidated CSAT 79% vs the 85% target, dragged down by Billing (72%).",
        "General requirements compliance 94% vs 100%; disclosures missed on 11% of billing-dispute calls.",
        "Only ~3% of interactions are QA-monitored, so coaching relies on anecdotes.",
    ],
}

# Surface each KPI's mocked current average on the framework (kpi_actuals is the
# single source of truth so the panel and the performance agent never disagree).
for _kpi in CURRENT_FRAMEWORK.kpis:
    _kpi.current_value = AGENT_PERFORMANCE["kpi_actuals"].get(_kpi.id, _kpi.current_value)


# ---------------------------------------------------------------------------
# 3. Curated 2026 "web research" knowledge base for the researcher agent's
#    search tool. Each entry stands in for a page the agent would find online.
# ---------------------------------------------------------------------------

# Official standards sources — deep links to the exact standard pages (verified) reused across the KB and simulations.
_SRC_ISO_18295 = Source(title="ISO 18295-1:2017 — Customer contact centres — Part 1: Requirements", url="https://www.iso.org/standard/64739.html", publisher="ISO")
_SRC_ISO_9001 = Source(title="ISO 9001:2015 — Quality management systems — Requirements", url="https://www.iso.org/standard/62085.html", publisher="ISO")
_SRC_ISO_10002 = Source(title="ISO 10002:2018 — Customer satisfaction — Guidelines for complaints handling", url="https://www.iso.org/standard/71580.html", publisher="ISO")
_SRC_ISO_30414 = Source(title="ISO 30414:2018 — Guidelines for internal and external human capital reporting", url="https://www.iso.org/standard/69338.html", publisher="ISO")
_SRC_ISO_20000 = Source(title="ISO/IEC 20000-1:2018 — Service management — Part 1: SMS requirements", url="https://www.iso.org/standard/70636.html", publisher="ISO/IEC")
_SRC_COPC = Source(title="COPC Customer Experience (CX) Standard, Release 7.0", url="https://www.copc.com/copc-standards/copc-cx-standard/", publisher="COPC Inc.")
_SRC_STAR7 = Source(title="Global Star Rating System for Services", url="https://u.ae/en/about-the-uae/digital-uae/digital-services-adoption/global-star-rating-system-for-services", publisher="UAE Government")

MARKET_BENCHMARKS = [
    {
        "topic": "Service level & accessibility (ISO 18295-1)",
        "insight": (
            "ISO 18295-1 requires a customer contact centre to define, publish and monitor "
            "service-level and accessibility targets for each channel, and to record and act on "
            "corrective action whenever a target is not met."
        ),
        "benchmark": "Defined, monitored service-level and accessibility targets per channel with documented corrective action.",
        "sources": [_SRC_ISO_18295],
    },
    {
        "topic": "First contact resolution & complaint handling (COPC / ISO 10002)",
        "insight": (
            "The COPC CX Standard treats first contact resolution and repeat contact as core "
            "measures of both efficiency and experience, while ISO 10002 sets requirements for "
            "fair, traceable complaint handling with root-cause correction."
        ),
        "benchmark": "Measure FCR and repeat contact objectively; handle and root-cause complaints in line with ISO 10002.",
        "sources": [_SRC_COPC, _SRC_ISO_10002],
    },
    {
        "topic": "Quality monitoring & error taxonomy (ISO 9001 / COPC)",
        "insight": (
            "The COPC CX Standard and ISO 9001 require a calibrated quality-monitoring process "
            "with a defined error taxonomy, must-pass critical items, and regular calibration so "
            "that scoring is consistent, repeatable and defensible."
        ),
        "benchmark": "Calibrated monitoring, a defined critical-error taxonomy, and documented corrective action.",
        "sources": [_SRC_COPC, _SRC_ISO_9001],
    },
    {
        "topic": "Customer satisfaction measurement (COPC / ISO 18295-1)",
        "insight": (
            "COPC and ISO 18295-1 require a structured customer-satisfaction measurement method "
            "applied consistently across channels, with results reviewed by management and linked "
            "to service improvement."
        ),
        "benchmark": "A consistent multi-channel satisfaction methodology, reviewed by management and linked to action.",
        "sources": [_SRC_COPC, _SRC_ISO_18295],
    },
    {
        "topic": "Workforce competence & staffing (ISO 18295-1 / ISO 30414)",
        "insight": (
            "ISO 18295-1 sets requirements for agent competence, training and adequate staffing "
            "to meet service levels; ISO 30414 defines the human-capital measures — recruitment, "
            "onboarding success and training — that evidence workforce readiness."
        ),
        "benchmark": "Documented competence and staffing to meet service levels; human-capital measures per ISO 30414.",
        "sources": [_SRC_ISO_18295, _SRC_ISO_30414],
    },
    {
        "topic": "End-to-end service quality rating (Global 7-Star)",
        "insight": (
            "The Global Star Rating for Services assesses end-to-end service across channels — "
            "customer experience, efficiency, accessibility and service delivery — against a "
            "defined 2-to-7 star scale."
        ),
        "benchmark": "Assessment against the Global Star Rating criteria across all service channels.",
        "sources": [_SRC_STAR7],
    },
    {
        "topic": "Technology availability & continuity (ISO/IEC 20000)",
        "insight": (
            "ISO/IEC 20000 requires the availability and continuity of the technology that "
            "underpins service delivery to be planned, measured and reported against agreed "
            "service targets."
        ),
        "benchmark": "Planned, measured availability and continuity reported against agreed service targets.",
        "sources": [_SRC_ISO_20000],
    },
]


# ---------------------------------------------------------------------------
# 3b. Quality-standards catalog the KPIs are mapped to. Surfaced to the agents
#     via the get_quality_standards tool so recommendations cite the governing
#     framework (ISO / COPC / Global 7-Star Rating).
# ---------------------------------------------------------------------------

QUALITY_STANDARDS = [
    {
        "code": "ISO 18295",
        "name": "ISO 18295-1/-2 — Customer contact centres",
        "body": "International Organization for Standardization",
        "focus": "Service levels, accessibility, response times, complaint handling and agent competence for customer contact centres.",
        "example_metrics": "Service level %, abandonment rate, response time, first-contact resolution, customer satisfaction.",
        "sources": [
            _SRC_ISO_18295,
        ],
    },
    {
        "code": "ISO 9001",
        "name": "ISO 9001 — Quality management systems",
        "body": "International Organization for Standardization",
        "focus": "Process quality, error prevention, corrective action and continual improvement (Plan-Do-Check-Act).",
        "example_metrics": "Defect/error rate, QA conformance, corrective-action closure, knowledge accuracy.",
        "sources": [
            _SRC_ISO_9001,
        ],
    },
    {
        "code": "COPC",
        "name": "COPC Customer Experience (CX) Standard 7.0",
        "body": "COPC Inc.",
        "focus": "Performance management for contact centres balancing service, quality, efficiency and customer-experience outcomes against proven targets.",
        "example_metrics": "FCR, service level, quality score, CSAT/NPS, forecast accuracy, schedule adherence.",
        "sources": [
            _SRC_COPC,
        ],
    },
    {
        "code": "7-Star",
        "name": "Global Star Rating for Services (7-Star Quality of Service)",
        "body": "UAE Government — Global Star Rating Program",
        "focus": "End-to-end service quality across channels, rated 2–7 stars on customer experience, efficiency, accessibility and service delivery.",
        "example_metrics": "Overall star score, channel experience, service efficiency, complaint resolution, accessibility, facility readiness.",
        "sources": [
            _SRC_STAR7,
        ],
    },
    {
        "code": "ISO 30414",
        "name": "ISO 30414 — Human capital reporting",
        "body": "International Organization for Standardization",
        "focus": "Workforce metrics for recruitment, onboarding, retention, readiness and employee satisfaction.",
        "example_metrics": "Time-to-fill, new-hire success/attrition, training completion, employee satisfaction (ESAT).",
        "sources": [
            _SRC_ISO_30414,
        ],
    },
    {
        "code": "ISO 20000",
        "name": "ISO/IEC 20000 — IT service management",
        "body": "ISO/IEC",
        "focus": "Reliability and availability of the technology underpinning service delivery.",
        "example_metrics": "System availability %, incident MTTR, change success rate.",
        "sources": [
            _SRC_ISO_20000,
        ],
    },
]


# ---------------------------------------------------------------------------
# 4. Pre-authored agent output (used when Foundry is not configured).
# ---------------------------------------------------------------------------

MARKET_BENCHMARK_SIMULATION = AgentResult(
    agent="Market Benchmark Researcher",
    headline="3 gaps against ISO 18295, ISO 9001 and COPC requirements",
    summary=(
        "Measured against ISO 18295-1, ISO 9001 and the COPC CX Standard, three gaps stand out: "
        "quality monitoring covers only ~3% of interactions and is not calibrated, first contact "
        "resolution is self-reported rather than measured objectively, and the scorecard has no "
        "defined must-pass critical-error items. Each is a documented requirement of the standards above."
    ),
    mode="simulation",
    findings=[
        Finding(
            id="mb-coverage",
            title="Extend calibrated quality monitoring beyond the current 3% sample",
            observation=(
                "Quality monitoring currently reviews about 3% of interactions. ISO 9001 and the "
                "COPC CX Standard require a calibrated monitoring process sized to give a "
                "representative, defensible view of quality across channels and teams."
            ),
            suggestion=(
                "Introduce a 'Monitoring Coverage' measure and expand automated, calibrated "
                "scoring so quality is representative across channels, with human calibration on a sample."
            ),
            impact="high",
            category="Coverage",
            proposed_change=ProposedChange(
                sla_id="qa",
                sla_name="Quality Assurance",
                field="coverage",
                current_value="~3% sampled (manual)",
                proposed_value="Representative, calibrated coverage across channels",
                rationale="ISO 9001 and COPC require calibrated, representative monitoring; a 3% manual sample does not meet that intent.",
            ),
            sources=[_SRC_ISO_9001, _SRC_COPC],
        ),
        Finding(
            id="mb-fcr",
            title="Measure First Contact Resolution objectively via repeat-contact",
            observation=(
                "First Contact Resolution is currently self-reported by agents. The COPC CX "
                "Standard requires it to be measured objectively — for example from a defined "
                "repeat-contact window — and ISO 10002 requires the underlying issues to be root-caused."
            ),
            suggestion="Switch FCR measurement to an objective 7-day repeat-contact signal and root-cause repeat drivers.",
            impact="high",
            category="Resolution",
            proposed_change=ProposedChange(
                sla_id="fcr",
                sla_name="Agent FCR",
                field="measurement",
                current_value="Self-reported",
                proposed_value="Objective 7-day repeat-contact measurement",
                rationale="COPC requires objective FCR measurement; ISO 10002 requires root-cause correction of repeat contacts.",
            ),
            sources=[_SRC_COPC, _SRC_ISO_10002],
        ),
        Finding(
            id="mb-taxonomy",
            title="Define a critical-error taxonomy with must-pass items on the scorecard",
            observation=(
                "The scorecard has no defined critical-error taxonomy or must-pass items. ISO 9001 "
                "and the COPC CX Standard require critical errors — particularly compliance and "
                "accuracy failures — to be defined and to fail the interaction automatically."
            ),
            suggestion="Add a defined critical-error taxonomy with must-pass compliance and accuracy items.",
            impact="medium",
            category="Quality",
            proposed_change=ProposedChange(
                sla_id="qa",
                sla_name="Quality Assurance",
                field="enforcement",
                current_value="No defined critical-error taxonomy",
                proposed_value="Critical-error taxonomy with must-pass items",
                rationale="ISO 9001 and COPC require critical errors to be defined and to auto-fail the interaction.",
            ),
            sources=[_SRC_ISO_9001, _SRC_COPC],
        ),
    ],
)


PERFORMANCE_SIMULATION = AgentResult(
    agent="Performance Improvement",
    headline="42,875 interactions analyzed · 3 coaching priorities",
    summary=(
        "Billing is missing disclosures on 11% of payment-dispute calls (compliance risk), "
        "Tech Support AHT runs 34% over target with a matching CSAT gap, and there is no "
        "trend line connecting coaching to later QA-score movement. These are the three "
        "highest-return interventions this month."
    ),
    mode="simulation",
    findings=[
        Finding(
            id="pi-compliance",
            title="Close the billing disclosure gap (11% of payment-dispute calls)",
            observation=(
                "Compliance adherence is 94% overall but Billing drops to 89%; required "
                "disclosures were missed on 11% of sampled payment-dispute calls."
            ),
            suggestion=(
                "Auto-flag missing-disclosure events with keyword indicators and require the "
                "compliance category to pass before an interaction can score above 80."
            ),
            impact="high",
            category="Compliance",
            proposed_change=ProposedChange(
                sla_id="compliance",
                sla_name="Compliance Adherence",
                field="enforcement",
                current_value="100% target, no auto-flagging",
                proposed_value="100% target + automated missing-disclosure flags",
                rationale="Turns a monitored target into an enforced, auditable control.",
            ),
            sources=[_SRC_COPC, _SRC_ISO_9001],
        ),
        Finding(
            id="pi-aht",
            title="Attack Tech Support AHT — 34% over target and dragging CSAT",
            observation=(
                "Tech Support AHT is 12.1 min vs. the 8:00 target (34% over) and its CSAT is "
                "7 points below Retention. Long holds and silence are frequent."
            ),
            suggestion=(
                "Target knowledge-base gaps behind long holds and coach on hold etiquette; "
                "track AHT and silence together rather than AHT alone."
            ),
            impact="medium",
            category="Efficiency",
            proposed_change=ProposedChange(
                sla_id="aht",
                sla_name="Average Handle Time (AHT)",
                field="target",
                current_value="≤ 8:00 min (single metric)",
                proposed_value="≤ 8:00 min paired with silence < 30s",
                rationale="Prevents AHT gaming and links efficiency to experience.",
            ),
            sources=[_SRC_COPC],
        ),
        Finding(
            id="pi-coaching",
            title="Make coaching measurable — track QA lift 30 days after each session",
            observation=(
                "Coaching happens but no trend line links a coaching session to later QA-score "
                "movement, so it is impossible to prove what works."
            ),
            suggestion=(
                "Add a 'Coaching Effectiveness' KPI: measured QA-score lift 30 days after a "
                "coaching session, tracked per agent and per skill."
            ),
            impact="medium",
            category="Coaching",
            proposed_change=ProposedChange(
                sla_id="new",
                sla_name="Coaching Effectiveness (30-day QA lift)",
                field="new_kpi",
                current_value="Not measured",
                proposed_value="≥ +5 pts QA score 30 days post-coaching",
                rationale="Closes the loop from score to coaching to measurable improvement.",
            ),
            sources=[_SRC_COPC, _SRC_ISO_9001],
        ),
    ],
)


# ---------------------------------------------------------------------------
# 5. Governance — the approval routing chain for framework changes.
# ---------------------------------------------------------------------------

APPROVAL_ROUTE = ApprovalRoute(
    title="QA Framework Change — Approval Routing",
    steps=[
        ApprovalStep(order=1, role="QA Lead", owner="Priya Raman", responsibility="Validate criteria are specific, weighted and calibratable.", sla="1 business day"),
        ApprovalStep(order=2, role="Contact Center Manager", owner="Marcus Bell", responsibility="Confirm targets are achievable and staffed.", sla="2 business days"),
        ApprovalStep(order=3, role="Compliance Officer", owner="Dana Ortiz", responsibility="Sign off on disclosure and audit-trail changes.", sla="2 business days"),
        ApprovalStep(order=4, role="VP, Customer Experience", owner="Alex Whitfield", responsibility="Approve KPI targets tied to CSAT/NPS outcomes.", sla="3 business days"),
    ],
)
