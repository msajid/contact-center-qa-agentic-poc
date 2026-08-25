"use strict";

// ------------------------------------------------------------------ helpers
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

// ------------------------------------------------------------- tracing
// Frontend debug traces stream to the browser DevTools Console (press F12).
const DEBUG = true;
let _traceSeq = 0;
function trace(scope, msg, data) {
  if (!DEBUG) return;
  const ts = new Date().toISOString().slice(11, 23);
  const s1 = "color:#9b2c3a;font-weight:bold";
  const s2 = "color:#2563eb;font-weight:bold";
  if (data !== undefined) {
    console.debug(`%c[CCQA ${ts}]%c ${scope}`, s1, s2, msg, data);
  } else {
    console.debug(`%c[CCQA ${ts}]%c ${scope}`, s1, s2, msg);
  }
}
function safeParse(s) {
  try { return JSON.parse(s); } catch { return s; }
}
console.info(
  "%c CCQA debug tracing ON \u2014 every action & API call is logged here. ",
  "background:#e2707c;color:#fff;padding:3px 8px;border-radius:4px;font-weight:bold"
);

async function api(path, options = {}) {
  const id = ++_traceSeq;
  const method = (options.method || "GET").toUpperCase();
  const started = performance.now();
  trace("api", `#${id} \u2192 ${method} ${path}`, options.body ? safeParse(options.body) : "");
  let res;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    trace("api", `#${id} \u2716 network error ${method} ${path}`, e.message);
    throw e;
  }
  const ms = Math.round(performance.now() - started);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    trace("api", `#${id} \u2190 ${res.status} ${method} ${path} (${ms} ms) ERROR`, detail);
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  const json = await res.json();
  trace("api", `#${id} \u2190 ${res.status} ${method} ${path} (${ms} ms)`, json);
  return json;
}

function toast(message, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

// -------------------------------------------------------------- app state
const findingsById = new Map(); // id -> { finding, agent }
const selected = new Set();
let selectedKpiId = null; // KPI chosen in the left panel for a focused run
let currentFramework = null; // last framework payload (for KPI lookups)

// ------------------------------------------------------------- status
async function loadStatus() {
  try {
    const s = await api("/api/status");
    trace("status", `mode=${s.mode} model=${s.model} web_search=${s.web_search}`);
    const badge = $("#mode-badge");
    const text = $("#mode-text");
    if (s.mode === "live") {
      badge.classList.add("live");
      text.textContent = `Live · Foundry (${s.model})`;
    } else {
      badge.classList.remove("live");
      text.textContent = "Simulation mode";
    }
  } catch {
    $("#mode-text").textContent = "offline";
  }
}

// ------------------------------------------------------------- framework
function kpiNum(s) {
  if (!s) return null;
  const bounded = String(s).match(/[≥≤]\s*([\d.]+)/);
  if (bounded) return parseFloat(bounded[1]);
  const first = String(s).match(/([\d.]+)/);
  return first ? parseFloat(first[1]) : null;
}

function kpiStatus(cur, tgt) {
  const c = kpiNum(cur);
  const t = kpiNum(tgt);
  if (c == null || t == null) return "";
  const lowerBetter = String(tgt).includes("≤");
  const gap = lowerBetter ? c - t : t - c;
  if (gap <= 0) return "ok";
  if (gap <= 3) return "warn";
  return "bad";
}

function stdClass(std) {
  const s = String(std || "").toLowerCase();
  if (s.startsWith("iso")) return "iso";
  if (s.includes("copc")) return "copc";
  if (s.includes("star")) return "star";
  return "other";
}

function standardChip(std) {
  if (!std) return "";
  return `<span class="std-chip ${stdClass(std)}" title="Governing standard: ${esc(
    std
  )}">${esc(std)}</span>`;
}

function renderFramework(fw, changedIds = []) {
  $("#framework-meta").textContent = `${fw.evaluation_method}`;
  $("#framework-version").textContent = fw.version;

  $("#framework-facts").innerHTML = `
    <div class="fact"><div class="fact-label">Coverage</div><div class="fact-value">${esc(fw.coverage)}</div></div>
    <div class="fact"><div class="fact-label">Last reviewed</div><div class="fact-value">${esc(fw.last_reviewed)}</div></div>`;

  const order = [];
  const byCat = new Map();
  fw.kpis.forEach((k) => {
    const cat = k.category || "Other";
    if (!byCat.has(cat)) {
      byCat.set(cat, []);
      order.push(cat);
    }
    byCat.get(cat).push(k);
  });
  const kpiHtml = (k) => {
    const changed = changedIds.includes(k.id) ? "changed" : "";
    const st = kpiStatus(k.current_value, k.current_target);
    const now = k.current_value
      ? `<div class="kpi-metric kpi-now ${st}"><span class="kpi-mlabel">Avg</span><span class="kpi-mval">${esc(
          k.current_value
        )}</span></div>`
      : "";
    return `<div class="kpi ${changed}" data-kpi-id="${esc(k.id)}">
        <div>
          <div class="kpi-name">${esc(k.name)}${standardChip(k.standard)}</div>
          <div class="kpi-desc">${esc(k.description)}</div>
        </div>
        <div class="kpi-metrics">
          ${now}
          <div class="kpi-metric kpi-target"><span class="kpi-mlabel">Target</span><span class="kpi-mval">${esc(
            k.current_target
          )}</span></div>
        </div>
      </div>`;
  };
  $("#kpi-list").innerHTML = order
    .map(
      (cat) =>
        `<div class="kpi-group"><div class="kpi-group-h">${esc(cat)}</div>${byCat
          .get(cat)
          .map(kpiHtml)
          .join("")}</div>`
    )
    .join("");

  $("#scorecard").innerHTML = fw.scorecard
    .map(
      (c) => `<div class="score-row">
        <div class="score-name">${esc(c.name)}</div>
        <div class="score-bar"><span style="width:${c.weight * 2}%"></span></div>
        <div class="score-weight">${c.weight}%</div>
      </div>`
    )
    .join("");

  currentFramework = fw;
  if (selectedKpiId) {
    const el = $(`.kpi[data-kpi-id="${CSS.escape(selectedKpiId)}"]`);
    if (el) el.classList.add("selected");
  }
}

async function loadFramework(changedIds = []) {
  const fw = await api("/api/framework");
  renderFramework(fw, changedIds);
}

// ------------------------------------------------------------- findings
function listBlock(cls, label, items) {
  if (!items || !items.length) return "";
  const lis = items.map((i) => `<li>${esc(i)}</li>`).join("");
  return `<div class="rec-block ${cls}"><div class="rec-h">${label}</div><ul class="rec-list">${lis}</ul></div>`;
}

function findingCard(finding, agent) {
  const src = (finding.sources || [])
    .map(
      (s) =>
        `<a class="source-chip" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(
          s.publisher || s.title
        )}</a>`
    )
    .join("");

  let uplift = "";
  if (finding.current_value && finding.target_value) {
    const tag =
      finding.kpi_id && finding.kpi_id !== "new"
        ? `<span class="kpi-tag">${esc(finding.kpi_id)}</span>`
        : "";
    uplift = `<div class="uplift"><span class="from">${esc(finding.current_value)}</span><span class="arrow">&rarr;</span><span class="to">${esc(
      finding.target_value
    )}</span>${tag}</div>`;
  }

  const rec =
    listBlock("actions", "Actions to try", finding.action_ideas) +
    listBlock("kpis", "New KPIs to introduce", finding.new_kpis) +
    listBlock("trainings", "Trainings", finding.trainings) +
    listBlock("practices", "Standard-aligned practices", finding.modern_practices);
  const recWrap = rec ? `<div class="rec">${rec}</div>` : "";

  return `<article class="finding" data-finding-id="${esc(finding.id)}" data-agent="${esc(agent)}">
    <div class="finding-top">
      <input type="checkbox" class="finding-check" title="Select for approval" />
      <h4 class="finding-title">${esc(finding.title)}</h4>
      <span class="badge badge--${esc(finding.impact)}">${esc(finding.impact)}</span>
    </div>
    ${uplift}
    <p class="obs"><strong>Finding:</strong> ${esc(finding.observation)}</p>
    <p class="sugg"><strong>Suggestion:</strong> ${esc(finding.suggestion)}</p>
    ${recWrap}
    ${src ? `<div class="sources">${src}</div>` : ""}
    <div class="finding-actions">
      <button class="btn btn--integrate" data-action="integrate">Simulate Integration</button>
    </div>
    <div class="preview" hidden></div>
  </article>`;
}

function renderAgentResult(agent, result) {
  result.findings.forEach((f) => findingsById.set(f.id, { finding: f, agent }));

  const summary = $(`#${agent}-summary`);
  summary.hidden = false;
  summary.innerHTML = `<div class="headline">${esc(result.headline)}</div><div>${esc(
    result.summary
  )}</div>`;

  $(`#${agent}-findings`).innerHTML = result.findings
    .map((f) => findingCard(f, agent))
    .join("");
}

const TOOL_LABELS = {
  get_current_qa_framework: "Loading the current QA framework",
  get_quality_standards: "Reviewing ISO / COPC / 7-Star standards",
  search_market_benchmarks: "Searching official standards sources",
  get_agent_performance_data: "Analysing recent performance data",
};
function toolLabel(name) {
  if (TOOL_LABELS[name]) return TOOL_LABELS[name];
  if (/web|search|bing|browser/i.test(name)) return "Searching the web (official sources)";
  return `Using ${name}`;
}

// Stream an agent run over SSE: show tool calls + reasoning live, then render findings.
async function streamAgentRun(agent, endpoint, body) {
  trace("action", `Stream run: ${agent} -> ${endpoint}`, body || "");
  const findingsEl = $(`#${agent}-findings`);
  $(`#${agent}-summary`).hidden = true;
  findingsEl.innerHTML = `
    <div class="stream">
      <div class="stream-head"><span class="stream-dot"></span><span class="stream-status">Connecting to Foundry…</span></div>
      <div class="stream-tools"></div>
      <div class="stream-reason-wrap" hidden><div class="stream-reason-h">Model reasoning</div><div class="stream-reason"></div></div>
      <div class="stream-draft" hidden></div>
    </div>`;
  const statusEl = $(".stream-status", findingsEl);
  const toolsEl = $(".stream-tools", findingsEl);
  const reasonWrap = $(".stream-reason-wrap", findingsEl);
  const reasonEl = $(".stream-reason", findingsEl);
  const draftEl = $(".stream-draft", findingsEl);
  const seenTools = new Set();
  let draftChars = 0;
  let finalResult = null;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try { const j = await res.json(); detail = j.detail || detail; } catch (_) {}
    throw new Error(detail);
  }

  const statusMap = {
    connecting: "Connecting to Foundry…",
    thinking: "Thinking…",
    simulation: "Composing (simulation)…",
    fallback: "Live call failed — using fallback…",
  };
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      let ev;
      try { ev = JSON.parse(dataLine.slice(5).trim()); } catch (_) { continue; }
      if (ev.type === "status") {
        statusEl.textContent = statusMap[ev.phase] || "Working…";
      } else if (ev.type === "tool") {
        if (seenTools.has(ev.name)) continue;
        seenTools.add(ev.name);
        const row = document.createElement("div");
        row.className = "stream-tool";
        row.textContent = toolLabel(ev.name);
        toolsEl.appendChild(row);
        statusEl.textContent = "Gathering evidence…";
      } else if (ev.type === "reasoning") {
        reasonWrap.hidden = false;
        reasonEl.textContent += ev.delta;
        reasonEl.scrollTop = reasonEl.scrollHeight;
        statusEl.textContent = "Reasoning…";
      } else if (ev.type === "output") {
        draftChars += (ev.delta || "").length;
        draftEl.hidden = false;
        draftEl.textContent = `Drafting recommendations… ${draftChars} characters`;
        statusEl.textContent = "Drafting recommendations…";
      } else if (ev.type === "done") {
        finalResult = ev.result;
      } else if (ev.type === "error") {
        throw new Error(ev.message || "stream error");
      }
    }
  }
  if (!finalResult) throw new Error("No result received from the agent.");
  trace("action", `Stream '${finalResult.agent}' done: ${finalResult.findings.length} findings (mode=${finalResult.mode})`);
  renderAgentResult(agent, finalResult);
  toast(`${finalResult.agent} — ${finalResult.findings.length} suggestions`, "success");
  return finalResult;
}

async function runAgent(agent, btn) {
  if (agent === "kpi") return runKpiAgent(btn);
  btn.classList.add("loading");
  btn.disabled = true;
  try {
    const endpoint =
      agent === "market"
        ? "/api/research/market-benchmark/stream"
        : "/api/research/performance/stream";
    await streamAgentRun(agent, endpoint, null);
  } catch (e) {
    toast(e.message, "error");
    $(`#${agent}-findings`).innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
  } finally {
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

// -------------------------------------------------------- KPI focused agent
function selectKpi(id) {
  selectedKpiId = id;
  trace("select", `KPI selected: ${id}`);
  $$("#kpi-list .kpi").forEach((el) =>
    el.classList.toggle("selected", el.dataset.kpiId === id)
  );
  const kpi = currentFramework?.kpis.find((k) => k.id === id);
  const bar = $("#kpi-run-bar");
  if (bar) {
    bar.hidden = false;
    $("#kpi-run-label").innerHTML = kpi
      ? `Selected: <strong>${esc(kpi.name)}</strong> ${standardChip(kpi.standard)}`
      : `Selected: <strong>${esc(id)}</strong>`;
  }
  const pbtn = $("#kpi-panel-run");
  if (pbtn) pbtn.disabled = false;
  const sub = $("#kpi-panel-sub");
  if (sub && kpi) {
    sub.textContent = `Ready to analyse \u201c${kpi.name}\u201d. Click Run agent for a focused improvement plan.`;
  }
}

async function runKpiAgent(btn) {
  if (!selectedKpiId) {
    toast("Pick a KPI in the framework on the left first", "");
    return;
  }
  const kpi = currentFramework?.kpis.find((k) => k.id === selectedKpiId);
  const label = kpi ? kpi.name : selectedKpiId;
  trace("action", `Run KPI agent: ${selectedKpiId}`);
  const runButtons = $$('.btn--run[data-agent="kpi"]');
  runButtons.forEach((b) => {
    b.classList.add("loading");
    b.disabled = true;
  });
  $("#kpi-panel-sub").textContent = `Analysing “${label}” against ${
    kpi ? kpi.standard : "its standard"
  } and official benchmarks…`;
  try {
    await streamAgentRun("kpi", "/api/research/kpi/stream", { kpi_id: selectedKpiId });
    $("#kpi-panel-sub").textContent = `Focused improvement plan for “${label}”${
      kpi ? " · " + kpi.standard : ""
    }.`;
  } catch (e) {
    toast(e.message, "error");
    $("#kpi-findings").innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
  } finally {
    runButtons.forEach((b) => {
      b.classList.remove("loading");
      b.disabled = false;
    });
  }
}

// ------------------------------------------------------- integration preview
async function simulateIntegration(findingId, btn, card) {
  trace("action", `Simulate Integration: ${findingId}`);
  const entry = findingsById.get(findingId);
  btn.classList.add("loading");
  btn.disabled = true;
  try {
    const preview = await api("/api/integrate", {
      method: "POST",
      body: JSON.stringify({ finding_id: findingId, agent: entry.agent }),
    });
    const box = $(".preview", card);
    let diff = "";
    if (preview.current_value && preview.proposed_value) {
      diff = `<div class="diff">
        <div class="from">${esc(preview.current_value)}</div>
        <div class="arrow">&rarr;</div>
        <div class="to">${esc(preview.proposed_value)}</div>
      </div>`;
    }
    box.innerHTML = `<div class="preview-narrative">${esc(preview.narrative)}<br><em>${esc(
      preview.rationale
    )}</em></div>${diff}`;
    box.hidden = false;

    // Briefly highlight the affected KPI in the framework panel.
    if (preview.sla_id) {
      const kpiEl = $(`.kpi[data-kpi-id="${CSS.escape(preview.sla_id)}"]`);
      if (kpiEl) {
        kpiEl.classList.add("changed");
        setTimeout(() => kpiEl.classList.remove("changed"), 2600);
      }
    }
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

// ------------------------------------------------------------- selection
function updateSelectionUI() {
  const n = selected.size;
  trace("select", `${n} finding(s) selected`, [...selected]);
  $("#selected-count").textContent = `${n} change${n === 1 ? "" : "s"} selected`;
  $("#approve-btn").disabled = n === 0;
}

// ------------------------------------------------------------- approve
async function approveChanges() {
  const ids = [...selected];
  trace("action", `Approve Changes: ${ids.length} selected`, ids);
  const changedIds = ids
    .map((id) => findingsById.get(id)?.finding?.proposed_change?.sla_id)
    .filter((x) => x && x !== "new");

  try {
    const res = await api("/api/approve", {
      method: "POST",
      body: JSON.stringify({ finding_ids: ids }),
    });
    renderFramework(res.framework, changedIds);

    const applied = res.applied
      .map((a) => `<li>${esc(a.change)}</li>`)
      .join("");
    openModal(
      "Changes Approved",
      `<p style="font-size:13px;color:#52606d;margin-top:0">
         ${ids.length} change(s) applied to the working framework
         (now <strong>${esc(res.framework.version)}</strong>) and sent to approval routing.</p>
       <ul class="applied-list">${applied}</ul>
       ${routeHtml(res.route)}`
    );
    toast("Changes approved & routed for sign-off", "success");

    selected.clear();
    $$(".finding").forEach((c) => c.classList.remove("selected"));
    $$(".finding-check").forEach((c) => (c.checked = false));
    updateSelectionUI();
  } catch (e) {
    toast(e.message, "error");
  }
}

// ------------------------------------------------------------- routing
function routeHtml(route) {
  const steps = route.steps
    .map(
      (s) => `<div class="route-step">
        <div class="route-num">${s.order}</div>
        <div>
          <div class="route-role">${esc(s.role)}</div>
          <div class="route-owner">${esc(s.owner)}</div>
          <div class="route-resp">${esc(s.responsibility)}</div>
          <div class="route-sla">SLA: ${esc(s.sla)}</div>
        </div>
      </div>`
    )
    .join("");
  return `<h3 style="font-size:13px;margin:18px 0 4px">${esc(route.title)}</h3>${steps}`;
}

async function showRoute() {
  trace("action", "Show Approval Routing");
  try {
    const route = await api("/api/approval-route");
    openModal("Approval Routing", routeHtml(route));
  } catch (e) {
    toast(e.message, "error");
  }
}

// ------------------------------------------------------------- modal
function openModal(title, bodyHtml) {
  trace("modal", `open: ${title}`);
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = bodyHtml;
  $("#modal").hidden = false;
}
function closeModal() {
  if (!$("#modal").hidden) trace("modal", "close");
  $("#modal").hidden = true;
}

// ------------------------------------------------------------- reset
async function resetFramework() {
  trace("action", "Reset framework");
  try {
    const res = await api("/api/reset", { method: "POST" });
    selectedKpiId = null;
    renderFramework(res.framework);
    selected.clear();
    findingsById.clear();
    ["market", "performance", "kpi"].forEach((a) => {
      $(`#${a}-summary`).hidden = true;
      $(`#${a}-findings`).innerHTML =
        '<div class="empty-state">Run the agent to generate findings.</div>';
    });
    $("#kpi-run-bar").hidden = true;
    $("#kpi-panel-run").disabled = true;
    $("#kpi-panel-sub").textContent =
      "Select a KPI on the left, then run a focused, standards-grounded improvement analysis for just that KPI.";
    $$(".chat-suggestion").forEach((c) => c.remove());
    updateSelectionUI();
    toast("Framework reset to v2.1", "success");
  } catch (e) {
    toast(e.message, "error");
  }
}

// ------------------------------------------------------------- chatbot
const chatHistory = [];

function addChatMsg(role, text, extraClass = "") {
  const el = document.createElement("div");
  el.className = `chat-msg ${role} ${extraClass}`.trim();
  el.textContent = text;
  const thread = $("#chat-thread");
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

async function sendChat(message) {
  trace("action", `Chat send: ${message}`);
  addChatMsg("user", message);
  chatHistory.push({ role: "user", content: message });
  const thinking = addChatMsg("assistant", "\u2026thinking", "thinking");
  const sendBtn = $("#chat-send");
  sendBtn.classList.add("loading");
  sendBtn.disabled = true;
  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, history: chatHistory }),
    });
    thinking.remove();
    addChatMsg("assistant", res.reply);
    chatHistory.push({ role: "assistant", content: res.reply });
    if (res.suggestion) {
      trace("chat", `suggestion spawned: ${res.suggestion.id}`);
      findingsById.set(res.suggestion.id, { finding: res.suggestion, agent: "chat" });
      const wrap = document.createElement("div");
      wrap.className = "chat-suggestion";
      wrap.innerHTML =
        '<div class="chat-suggestion-label">New suggestion \u2014 tick it, then Simulate &amp; Approve below</div>' +
        findingCard(res.suggestion, "chat");
      const thread = $("#chat-thread");
      thread.appendChild(wrap);
      thread.scrollTop = thread.scrollHeight;
    }
  } catch (e) {
    thinking.remove();
    addChatMsg("assistant", "Sorry \u2014 " + e.message);
  } finally {
    sendBtn.classList.remove("loading");
    sendBtn.disabled = false;
  }
}

// ------------------------------------------------------------- events
document.addEventListener("click", (e) => {
  const runBtn = e.target.closest(".btn--run[data-agent]");
  if (runBtn) return runAgent(runBtn.dataset.agent, runBtn);

  const intBtn = e.target.closest('[data-action="integrate"]');
  if (intBtn) {
    const card = intBtn.closest(".finding");
    return simulateIntegration(card.dataset.findingId, intBtn, card);
  }

  const chip = e.target.closest(".chip-suggest");
  if (chip) return sendChat(chip.dataset.ask);

  const kpiRow = e.target.closest("#kpi-list .kpi[data-kpi-id]");
  if (kpiRow) return selectKpi(kpiRow.dataset.kpiId);
});

$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  sendChat(msg);
});

document.addEventListener("change", (e) => {
  const check = e.target.closest(".finding-check");
  if (!check) return;
  const card = check.closest(".finding");
  const id = card.dataset.findingId;
  if (check.checked) {
    selected.add(id);
    card.classList.add("selected");
  } else {
    selected.delete(id);
    card.classList.remove("selected");
  }
  updateSelectionUI();
});

$("#approve-btn").addEventListener("click", approveChanges);
$("#route-btn").addEventListener("click", showRoute);
$("#reset-btn").addEventListener("click", resetFramework);
$("#modal-close").addEventListener("click", closeModal);
$("#modal-done").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#modal").hidden) closeModal();
});

// ------------------------------------------------------------- init
(async function init() {
  await Promise.all([loadStatus(), loadFramework()]);
})();
