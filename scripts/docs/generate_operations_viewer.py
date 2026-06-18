#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/operations/pocketlab-typed-operations.json"
OUT = ROOT / "docs/runtime/generated/typed-operations-catalog/index.html"


HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Pocket Lab Typed Operations Catalog</title>
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
      background: radial-gradient(circle at top left, #312e81 0, transparent 34rem), var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      padding: 30px;
      border-bottom: 1px solid var(--line);
      background: rgba(15, 23, 42, .92);
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(12px);
    }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .subtitle { color: var(--muted); line-height: 1.55; max-width: 1050px; }
    .toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; }
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
    main { padding: 28px; max-width: 1460px; margin: 0 auto; }
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
    .layout { display: grid; grid-template-columns: 390px 1fr; gap: 20px; }
    .list, .detail {
      background: rgba(17, 24, 39, .88);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      min-height: 680px;
    }
    .list-header, .detail-header {
      padding: 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(30, 41, 59, .75);
    }
    .operation-list { max-height: 760px; overflow: auto; }
    .operation {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(51, 65, 85, .55);
      cursor: pointer;
    }
    .operation:hover, .operation.active { background: rgba(167, 139, 250, .10); }
    .operation code { color: #ddd6fe; word-break: break-all; font-size: 12px; }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      margin: 2px 4px 6px 0;
      border: 1px solid var(--line);
      color: var(--muted);
    }
    .badge.write { color: var(--amber); border-color: rgba(245, 158, 11, .35); }
    .badge.read { color: var(--green); border-color: rgba(34, 197, 94, .35); }
    .badge.secret { color: var(--red); border-color: rgba(239, 68, 68, .35); }
    .badge.release { color: var(--violet); border-color: rgba(167, 139, 250, .35); }
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
      max-height: 360px;
    }
    .flow { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 18px 0; }
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
  <h1>Pocket Lab Typed Operations Catalog</h1>
  <div class="subtitle">
    Interactive catalog of Pocket Lab typed operations, UI entry points, API paths, NATS subjects,
    event outcomes, safety behavior, Simple Mode labels, and Professional Mode labels.
  </div>
  <div class="toolbar">
    <input id="search" placeholder="Search operations, UI screens, API paths, NATS subjects..." />
    <select id="filter">
      <option value="all">All operations</option>
      <option value="write">Write/safety-sensitive</option>
      <option value="release">Release</option>
      <option value="secret">Vault/secret</option>
      <option value="fleet">Fleet</option>
      <option value="drift">Drift</option>
    </select>
    <button onclick="downloadContract()">Download operations JSON</button>
  </div>
</header>

<main>
  <section class="stats">
    <div class="stat"><strong id="opCount">0</strong><span>Operations</span></div>
    <div class="stat"><strong id="writeCount">0</strong><span>Write-sensitive</span></div>
    <div class="stat"><strong id="releaseCount">0</strong><span>Release ops</span></div>
    <div class="stat"><strong id="secretCount">0</strong><span>Vault/secret ops</span></div>
    <div class="stat"><strong id="fleetCount">0</strong><span>Fleet ops</span></div>
  </section>

  <section class="layout">
    <aside class="list">
      <div class="list-header">
        <strong>Operations</strong>
        <div style="color: var(--muted); font-size: 13px; margin-top: 4px;">Click an operation to inspect runtime behavior.</div>
      </div>
      <div id="operationList" class="operation-list"></div>
    </aside>

    <section class="detail">
      <div class="detail-header">
        <strong id="detailTitle">Select an operation</strong>
        <div id="detailSub" style="color: var(--muted); font-size: 13px; margin-top: 4px;"></div>
      </div>
      <div class="detail-body" id="detailBody">
        <div class="flow">
          <div class="node">UI</div><div class="arrow">→</div>
          <div class="node">FastAPI</div><div class="arrow">→</div>
          <div class="node">NATS / JetStream</div><div class="arrow">→</div>
          <div class="node">Worker</div><div class="arrow">→</div>
          <div class="node">Events</div>
        </div>
        <p style="color: var(--muted);">Choose a typed operation from the left.</p>
      </div>
    </section>
  </section>
</main>

<script id="operations-contract" type="application/json">__OPERATIONS_JSON__</script>
<script>
const contract = JSON.parse(document.getElementById("operations-contract").textContent);
const operations = contract.operations || [];

function tags(op) {
  const text = JSON.stringify(op).toLowerCase();
  const result = [];
  if (text.includes("write") || text.includes("mutat") || text.includes("destructive") || text.includes("apply")) result.push("write");
  if (op.operation.includes("release")) result.push("release");
  if (op.operation.includes("secret") || op.operation.includes("vault") || text.includes("password")) result.push("secret");
  if (op.operation.includes("fleet")) result.push("fleet");
  if (op.operation.includes("drift")) result.push("drift");
  return result;
}

function renderStats() {
  document.getElementById("opCount").textContent = operations.length;
  document.getElementById("writeCount").textContent = operations.filter(o => tags(o).includes("write")).length;
  document.getElementById("releaseCount").textContent = operations.filter(o => tags(o).includes("release")).length;
  document.getElementById("secretCount").textContent = operations.filter(o => tags(o).includes("secret")).length;
  document.getElementById("fleetCount").textContent = operations.filter(o => tags(o).includes("fleet")).length;
}

function renderList() {
  const q = document.getElementById("search").value.toLowerCase();
  const f = document.getElementById("filter").value;
  const el = document.getElementById("operationList");
  el.innerHTML = "";

  operations
    .filter(op => f === "all" || tags(op).includes(f))
    .filter(op => !q || JSON.stringify(op).toLowerCase().includes(q))
    .forEach(op => {
      const div = document.createElement("div");
      div.className = "operation";
      div.onclick = () => selectOperation(op, div);
      const opTags = tags(op).map(t => `<span class="badge ${t}">${t.toUpperCase()}</span>`).join("");
      div.innerHTML = `${opTags}<br><code>${escapeHtml(op.operation)}</code><div style="color: var(--muted); font-size: 12px; margin-top: 6px;">${escapeHtml(op.title)}</div>`;
      el.appendChild(div);
    });
}

function selectOperation(op, node) {
  document.querySelectorAll(".operation").forEach(n => n.classList.remove("active"));
  if (node) node.classList.add("active");

  document.getElementById("detailTitle").textContent = op.operation;
  document.getElementById("detailSub").textContent = op.summary || op.title;

  document.getElementById("detailBody").innerHTML = `
    <div class="cards">
      <div class="card"><h3>Professional Label</h3><p>${escapeHtml(op.professional_label)}</p></div>
      <div class="card"><h3>Simple Mode Label</h3><p>${escapeHtml(op.simple_label)}</p></div>
      <div class="card"><h3>NATS Subject</h3><p><code>${escapeHtml(op.nats_subject)}</code></p></div>
      <div class="card"><h3>Backend Owner</h3><p>${escapeHtml(op.backend_owner)}</p></div>
    </div>

    <h3>Operation Flow</h3>
    <div class="flow">
      <div class="node">UI</div><div class="arrow">→</div>
      <div class="node">FastAPI</div><div class="arrow">→</div>
      <div class="node">NATS / JetStream</div><div class="arrow">→</div>
      <div class="node">Worker</div><div class="arrow">→</div>
      <div class="node">Events</div>
    </div>

    <div class="cards">
      <div class="card"><h3>UI Entry Points</h3>${list(op.ui_entrypoints)}</div>
      <div class="card"><h3>API Entry Points</h3>${list(op.api_entrypoints)}</div>
      <div class="card"><h3>Success Events</h3>${list(op.success_events)}</div>
      <div class="card"><h3>Failure Events</h3>${list(op.failure_events)}</div>
    </div>

    <div class="card"><h3>Safety Behavior</h3><p>${escapeHtml(op.safety)}</p></div>
    <div class="card"><h3>Notes</h3><p>${escapeHtml(op.notes)}</p></div>

    <h3>Target Shape</h3>
    <pre>${escapeHtml(JSON.stringify(op.target_shape, null, 2))}</pre>

    <h3>Params Shape</h3>
    <pre>${escapeHtml(JSON.stringify(op.params_shape, null, 2))}</pre>

    <h3>Full Operation Contract</h3>
    <pre>${escapeHtml(JSON.stringify(op, null, 2))}</pre>
  `;
}

function list(items) {
  return `<ul>${(items || []).map(i => `<li><code>${escapeHtml(i)}</code></li>`).join("")}</ul>`;
}

function escapeHtml(v) {
  return String(v || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function downloadContract() {
  const blob = new Blob([JSON.stringify(contract, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pocketlab-typed-operations.json";
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
    if not CONTRACT.exists():
        raise SystemExit(f"Missing operations contract: {CONTRACT}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        HTML.replace("__OPERATIONS_JSON__", json.dumps(contract)),
        encoding="utf-8",
    )
    print(f"Wrote interactive operations viewer: {OUT}")


if __name__ == "__main__":
    main()
