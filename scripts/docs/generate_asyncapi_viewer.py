#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASYNCAPI = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"
OUT = ROOT / "docs/runtime/generated/nats-jetstream-asyncapi/index.html"

HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Pocket Lab NATS / JetStream AsyncAPI Viewer</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --panel2: #1e293b;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --line: #334155;
      --accent: #38bdf8;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
      --violet: #a78bfa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #1e3a8a 0, transparent 34rem), var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      padding: 30px;
      border-bottom: 1px solid var(--line);
      background: rgba(15, 23, 42, .9);
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(12px);
    }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .subtitle { color: var(--muted); line-height: 1.55; max-width: 1050px; }
    .toolbar {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 20px;
    }
    input, select, button {
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 14px;
    }
    input { min-width: 320px; flex: 1; }
    button { cursor: pointer; }
    main { padding: 28px; max-width: 1440px; margin: 0 auto; }
    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .stat {
      background: rgba(17, 24, 39, .9);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }
    .stat strong { display: block; font-size: 24px; margin-bottom: 4px; }
    .stat span { color: var(--muted); font-size: 13px; }
    .layout {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 20px;
    }
    .list, .detail {
      background: rgba(17, 24, 39, .88);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      min-height: 650px;
    }
    .list-header, .detail-header {
      padding: 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(30, 41, 59, .75);
    }
    .subject-list { max-height: 740px; overflow: auto; }
    .subject {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(51, 65, 85, .55);
      cursor: pointer;
    }
    .subject:hover, .subject.active { background: rgba(56, 189, 248, .10); }
    .subject code {
      color: #bae6fd;
      word-break: break-all;
      font-size: 12px;
    }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      margin-bottom: 6px;
      border: 1px solid var(--line);
      color: var(--muted);
    }
    .badge.command { color: var(--green); border-color: rgba(34, 197, 94, .35); }
    .badge.event { color: var(--accent); border-color: rgba(56, 189, 248, .35); }
    .badge.audit { color: var(--amber); border-color: rgba(245, 158, 11, .35); }
    .badge.dlq { color: var(--red); border-color: rgba(239, 68, 68, .35); }
    .detail-body { padding: 20px; }
    .cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(260px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .card {
      background: rgba(30, 41, 59, .65);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
    }
    .card h3 { margin: 0 0 8px; font-size: 15px; }
    .card p, .card li { color: var(--muted); line-height: 1.5; }
    pre {
      background: #020617;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      overflow: auto;
      color: #dbeafe;
      max-height: 380px;
    }
    .flow {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      margin: 18px 0;
    }
    .node {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(30, 41, 59, .75);
    }
    .arrow { color: var(--muted); }
    @media (max-width: 980px) {
      .layout, .stats, .cards { grid-template-columns: 1fr; }
      input { min-width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Pocket Lab NATS / JetStream AsyncAPI Viewer</h1>
    <div class="subtitle">
      Interactive event-contract explorer for Pocket Lab command subjects, event subjects, audit subjects,
      DLQ behavior, payload schemas, retry policy, and runtime stream design.
    </div>
    <div class="toolbar">
      <input id="search" placeholder="Search subjects, schemas, messages..." />
      <select id="filter">
        <option value="all">All subjects</option>
        <option value="command">Commands</option>
        <option value="event">Events</option>
        <option value="audit">Audit</option>
        <option value="dlq">DLQ</option>
      </select>
      <button onclick="downloadSpec()">Download AsyncAPI JSON</button>
    </div>
  </header>

  <main>
    <section class="stats">
      <div class="stat"><strong id="commandsCount">0</strong><span>Commands</span></div>
      <div class="stat"><strong id="eventsCount">0</strong><span>Events</span></div>
      <div class="stat"><strong id="auditCount">0</strong><span>Audit Subjects</span></div>
      <div class="stat"><strong id="dlqCount">0</strong><span>DLQ Subjects</span></div>
      <div class="stat"><strong id="schemaCount">0</strong><span>Schemas</span></div>
    </section>

    <section class="layout">
      <aside class="list">
        <div class="list-header">
          <strong>Subjects</strong>
          <div style="color: var(--muted); font-size: 13px; margin-top: 4px;">Click a subject to inspect message and payload schema.</div>
        </div>
        <div id="subjectList" class="subject-list"></div>
      </aside>

      <section class="detail">
        <div class="detail-header">
          <strong id="detailTitle">Select a subject</strong>
          <div id="detailSub" style="color: var(--muted); font-size: 13px; margin-top: 4px;"></div>
        </div>
        <div class="detail-body" id="detailBody">
          <div class="flow">
            <div class="node">FastAPI</div><div class="arrow">→</div>
            <div class="node">NATS / JetStream</div><div class="arrow">→</div>
            <div class="node">Worker</div><div class="arrow">→</div>
            <div class="node">Events</div><div class="arrow">→</div>
            <div class="node">UI</div>
          </div>
          <p style="color: var(--muted);">Choose a command, event, audit, or DLQ subject from the left.</p>
        </div>
      </section>
    </section>
  </main>

<script id="asyncapi-spec" type="application/json">__ASYNCAPI_JSON__</script>

<script>
const spec = JSON.parse(document.getElementById("asyncapi-spec").textContent);
const channels = spec.channels || {};
const messages = (spec.components && spec.components.messages) || {};
const schemas = (spec.components && spec.components.schemas) || {};

function kind(subject) {
  if (subject.startsWith("pocketlab.commands.")) return "command";
  if (subject.startsWith("pocketlab.audit.")) return "audit";
  if (subject.startsWith("pocketlab.dlq.")) return "dlq";
  return "event";
}

function firstMessageName(channel) {
  const keys = Object.keys(channel.messages || {});
  return keys[0] || "";
}

const subjects = Object.keys(channels).sort().map(subject => {
  const channel = channels[subject];
  const msgName = firstMessageName(channel);
  const msg = messages[msgName] || {};
  return { subject, channel, msgName, msg, kind: kind(subject) };
});

function renderStats() {
  document.getElementById("commandsCount").textContent = subjects.filter(s => s.kind === "command").length;
  document.getElementById("eventsCount").textContent = subjects.filter(s => s.kind === "event").length;
  document.getElementById("auditCount").textContent = subjects.filter(s => s.kind === "audit").length;
  document.getElementById("dlqCount").textContent = subjects.filter(s => s.kind === "dlq").length;
  document.getElementById("schemaCount").textContent = Object.keys(schemas).length;
}

function renderList() {
  const q = document.getElementById("search").value.toLowerCase();
  const f = document.getElementById("filter").value;
  const el = document.getElementById("subjectList");
  el.innerHTML = "";

  subjects
    .filter(s => f === "all" || s.kind === f)
    .filter(s => !q || JSON.stringify(s).toLowerCase().includes(q))
    .forEach((s) => {
      const div = document.createElement("div");
      div.className = "subject";
      div.onclick = () => selectSubject(s, div);
      div.innerHTML = `<span class="badge ${s.kind}">${s.kind.toUpperCase()}</span><br><code>${escapeHtml(s.subject)}</code>`;
      el.appendChild(div);
    });
}

function selectSubject(s, node) {
  document.querySelectorAll(".subject").forEach(n => n.classList.remove("active"));
  if (node) node.classList.add("active");

  document.getElementById("detailTitle").textContent = s.subject;
  document.getElementById("detailSub").textContent = s.msg.summary || s.msg.title || s.kind;

  const schemaRef = s.msg.payload && s.msg.payload.$ref;
  const schemaName = schemaRef ? schemaRef.split("/").pop() : "";
  const schema = schemaName ? schemas[schemaName] : {};

  document.getElementById("detailBody").innerHTML = `
    <div class="cards">
      <div class="card">
        <h3>Subject Type</h3>
        <p><span class="badge ${s.kind}">${s.kind.toUpperCase()}</span></p>
      </div>
      <div class="card">
        <h3>Message</h3>
        <p>${escapeHtml(s.msg.title || s.msg.name || s.msgName)}</p>
      </div>
      <div class="card">
        <h3>Payload Schema</h3>
        <p><code>${escapeHtml(schemaName || "Not specified")}</code></p>
      </div>
      <div class="card">
        <h3>Runtime Use</h3>
        <p>${runtimeUse(s.kind)}</p>
      </div>
    </div>

    <h3>Flow</h3>
    <div class="flow">${flowFor(s.kind)}</div>

    <h3>Message Definition</h3>
    <pre>${escapeHtml(JSON.stringify(s.msg, null, 2))}</pre>

    <h3>Payload Schema</h3>
    <pre>${escapeHtml(JSON.stringify(schema, null, 2))}</pre>
  `;
}

function flowFor(k) {
  if (k === "command") return `<div class="node">FastAPI</div><div class="arrow">→</div><div class="node">JetStream Command</div><div class="arrow">→</div><div class="node">Worker</div>`;
  if (k === "event") return `<div class="node">Worker / Runtime</div><div class="arrow">→</div><div class="node">Event Stream</div><div class="arrow">→</div><div class="node">UI + Journal</div>`;
  if (k === "audit") return `<div class="node">Security Action</div><div class="arrow">→</div><div class="node">Audit Stream</div><div class="arrow">→</div><div class="node">Evidence</div>`;
  return `<div class="node">Failed Command</div><div class="arrow">→</div><div class="node">Retry Exhausted</div><div class="arrow">→</div><div class="node">DLQ</div>`;
}

function runtimeUse(k) {
  if (k === "command") return "Durable command submitted by FastAPI and consumed by the worker.";
  if (k === "event") return "Runtime event emitted for UI updates, workflow recovery, telemetry, or observability.";
  if (k === "audit") return "Security-relevant event retained for auditability.";
  return "Dead-letter record for failed command handling and operator investigation.";
}

function escapeHtml(v) {
  return String(v || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function downloadSpec() {
  const blob = new Blob([JSON.stringify(spec, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pocketlab-nats-jetstream.asyncapi.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

document.getElementById("search").addEventListener("input", renderList);
document.getElementById("filter").addEventListener("change", renderList);
renderStats();
renderList();
</script>
</body>
</html>
'''

def main() -> None:
    if not ASYNCAPI.exists():
        raise SystemExit(f"Missing AsyncAPI contract: {ASYNCAPI}")

    spec = json.loads(ASYNCAPI.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML.replace("__ASYNCAPI_JSON__", json.dumps(spec)), encoding="utf-8")
    print(f"Wrote interactive AsyncAPI viewer: {OUT}")

if __name__ == "__main__":
    main()
