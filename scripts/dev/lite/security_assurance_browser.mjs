#!/usr/bin/env node
/**
 * Fixed Chromium security-assurance adapter for Pocket Lab Lite.
 *
 * No CLI target, URL, host, port, path, credential, wordlist, or browser script
 * is accepted. The adapter reads only the operator-approved Caddy SNI marker and
 * uses repository-owned fixed routes plus a fixed loopback hostile origin.
 */
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const VERSION = "1.0.0";
const CADDY_PORT = 18443;
const ATTACKER_PORT = 18991;
const SNI_FILE = path.join(os.homedir(), ".pocketlab-lite", "qualification", "caddy-sni");
const FORBIDDEN_PORTS = new Set(["4222", "8181", "8222", "14222", "18181", "18222"]);
const SECRET_KEY_RE = /(authorization|cookie|token|password|passwd|secret|api.?key|private.?key|credential)/i;

function fixedIdentity() {
  try {
    const value = fs.readFileSync(SNI_FILE, "ascii").trim().toLowerCase();
    if (!/^[a-z0-9](?:[a-z0-9.-]{0,252}[a-z0-9])?$/.test(value) || !value.includes(".") || value.includes("..")) {
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

function scenario(status, evidence, reason = null) {
  const row = { status, evidence };
  if (reason) row.reason = reason;
  return row;
}

function safeUrl(value) {
  try {
    const u = new URL(value);
    return { protocol: u.protocol, hostname: u.hostname, port: u.port || (u.protocol === "https:" ? "443" : u.protocol === "http:" ? "80" : "") };
  } catch {
    return { protocol: "invalid", hostname: "invalid", port: "" };
  }
}

async function run(suite) {
  if (!["standard", "deep", "adversarial"].includes(suite)) {
    throw new Error("suite_not_registered");
  }
  const { chromium } = await import("playwright");
  const identity = fixedIdentity();
  const targetHost = identity || "127.0.0.1";
  const base = `https://${targetHost}:${CADDY_PORT}`;
  const attackerOrigin = `http://127.0.0.1:${ATTACKER_PORT}`;

  const attackerHtml = `<!doctype html><meta charset="utf-8"><title>Pocket Lab fixed hostile origin</title>
<script>
window.__pocketlab = {fetchReadable:null, fetchStatus:null, websocketOpened:null, done:false};
(async () => {
  try {
    const response = await fetch("${base}/api/lite/status", {credentials:"include", mode:"cors"});
    window.__pocketlab.fetchReadable = true;
    window.__pocketlab.fetchStatus = response.status;
  } catch (_) {
    window.__pocketlab.fetchReadable = false;
  }
  try {
    const ws = new WebSocket("${base.replace("https://", "wss://")}/ws/events");
    await new Promise(resolve => {
      const timer = setTimeout(() => { try { ws.close(); } catch (_) {} resolve(); }, 1500);
      ws.onopen = () => { window.__pocketlab.websocketOpened = true; clearTimeout(timer); try { ws.close(); } catch (_) {} resolve(); };
      ws.onerror = () => { if (window.__pocketlab.websocketOpened === null) window.__pocketlab.websocketOpened = false; clearTimeout(timer); resolve(); };
      ws.onclose = () => { if (window.__pocketlab.websocketOpened === null) window.__pocketlab.websocketOpened = false; clearTimeout(timer); resolve(); };
    });
  } catch (_) {
    window.__pocketlab.websocketOpened = false;
  }
  window.__pocketlab.done = true;
})();
</script>`;

  const server = http.createServer((req, res) => {
    res.writeHead(200, {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "content-security-policy": "default-src 'self' 'unsafe-inline' https: wss:",
    });
    res.end(attackerHtml);
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(ATTACKER_PORT, "127.0.0.1", resolve);
  });

  const launchArgs = identity ? [`--host-resolver-rules=MAP ${identity} 127.0.0.1`] : [];
  const browser = await chromium.launch({ headless: true, args: launchArgs });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const requests = [];
  page.on("request", request => {
    if (requests.length < 512) requests.push(safeUrl(request.url()));
  });

  const findings = [];
  const checks = {};
  try {
    let mainResponse = null;
    try {
      mainResponse = await page.goto(base + "/", { waitUntil: "domcontentloaded", timeout: 15000 });
      checks.mainPageStatus = mainResponse?.status() ?? null;
      checks.mainPageHeaders = mainResponse ? {
        csp: Boolean((await mainResponse.allHeaders())["content-security-policy"]),
        frame: Boolean((await mainResponse.allHeaders())["x-frame-options"]),
        nosniff: String((await mainResponse.allHeaders())["x-content-type-options"] || "").toLowerCase() === "nosniff",
        referrer: Boolean((await mainResponse.allHeaders())["referrer-policy"]),
      } : {};
    } catch (error) {
      checks.mainPageFailure = error?.name || "navigation_failed";
    }

    let browserState = { localKeys: [], sessionKeys: [], cacheKeys: [], serviceWorkers: [], indexedDatabases: [] };
    if (checks.mainPageStatus) {
      browserState = await page.evaluate(async () => {
        const indexedDatabases = typeof indexedDB.databases === "function"
          ? (await indexedDB.databases()).map(row => row.name || "").filter(Boolean)
          : [];
        return {
          localKeys: Object.keys(localStorage),
          sessionKeys: Object.keys(sessionStorage),
          cacheKeys: "caches" in self ? await caches.keys() : [],
          serviceWorkers: "serviceWorker" in navigator
            ? (await navigator.serviceWorker.getRegistrations()).map(r => r.active?.scriptURL || r.installing?.scriptURL || r.waiting?.scriptURL || "").filter(Boolean)
            : [],
          indexedDatabases,
        };
      });
    }
    checks.browserState = {
      localKeyCount: browserState.localKeys.length,
      sessionKeyCount: browserState.sessionKeys.length,
      cacheCount: browserState.cacheKeys.length,
      serviceWorkerCount: browserState.serviceWorkers.length,
      indexedDatabaseCount: browserState.indexedDatabases.length,
    };
    const suspiciousKeys = [
      ...browserState.localKeys,
      ...browserState.sessionKeys,
      ...browserState.cacheKeys,
      ...browserState.indexedDatabases,
    ].filter(value => SECRET_KEY_RE.test(String(value)));
    if (suspiciousKeys.length) {
      findings.push({
        scenario_id: "pwa-offline-secret-retention",
        severity: "high",
        title: "Browser persistence contains security-sensitive key names",
        summary: "A fixed browser-state inventory found storage/cache identifiers shaped like credentials or secrets; values were not read.",
      });
    }

    const badServiceWorkers = browserState.serviceWorkers.filter(value => {
      try { return new URL(value).origin !== new URL(base).origin; } catch { return true; }
    });
    if (badServiceWorkers.length) {
      findings.push({
        scenario_id: "service-worker-version-integrity",
        severity: "high",
        title: "Service worker is not bound to the approved Pocket Lab origin",
        summary: "A registered service-worker script URL resolved outside the fixed Caddy origin.",
      });
    }

    const attacker = await context.newPage();
    await attacker.goto(attackerOrigin + "/", { waitUntil: "domcontentloaded", timeout: 10000 });
    await attacker.waitForFunction(() => window.__pocketlab?.done === true, null, { timeout: 5000 }).catch(() => {});
    const hostile = await attacker.evaluate(() => window.__pocketlab || {});
    checks.hostileOrigin = {
      fetchReadable: hostile.fetchReadable === true,
      fetchStatus: Number.isInteger(hostile.fetchStatus) ? hostile.fetchStatus : null,
      websocketOpened: hostile.websocketOpened === true,
    };
    if (hostile.fetchReadable === true) {
      findings.push({
        scenario_id: "cross-origin-session-abuse",
        severity: "high",
        title: "Hostile browser origin can read Pocket Lab API response",
        summary: "A fixed attacker origin obtained a readable CORS response from the approved Pocket Lab status route.",
      });
    }
    if (hostile.websocketOpened === true) {
      findings.push({
        scenario_id: "websocket-auth-boundary",
        severity: "high",
        title: "Hostile browser origin opened Pocket Lab event WebSocket",
        summary: "A fixed attacker origin established /ws/events without a browser identity fixture.",
      });
    }

    const approvedHosts = new Set([targetHost, "127.0.0.1", "localhost"]);
    const unexpected = requests.filter(row => {
      if (FORBIDDEN_PORTS.has(row.port)) return true;
      if (!["http:", "https:", "ws:", "wss:", "data:", "blob:"].includes(row.protocol)) return true;
      if (["data:", "blob:"].includes(row.protocol)) return false;
      if (row.hostname === "127.0.0.1" && row.port === String(ATTACKER_PORT)) return false;
      return !approvedHosts.has(row.hostname);
    });
    checks.network = {
      requestCount: requests.length,
      unexpectedRequestCount: unexpected.length,
      forbiddenInternalPortRequestCount: requests.filter(row => FORBIDDEN_PORTS.has(row.port)).length,
    };
    if (unexpected.length) {
      findings.push({
        scenario_id: "browser-network-egress-contract",
        severity: "high",
        title: "Browser attempted network egress outside approved Pocket Lab origins",
        summary: "Chromium observed one or more requests outside the fixed Caddy/attacker-origin test envelope; raw URLs were not retained.",
      });
    }

    const headers = checks.mainPageHeaders || {};
    if (checks.mainPageStatus && (!headers.csp || !headers.nosniff || !headers.referrer)) {
      findings.push({
        scenario_id: "browser-origin-control-plane-bypass",
        severity: "low",
        title: "Browser-facing security headers are incomplete",
        summary: "The fixed Caddy page response is missing one or more browser hardening headers used by the assurance profile.",
      });
    }
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
    await new Promise(resolve => server.close(resolve));
  }

  const failed = new Set(findings.map(row => row.scenario_id));
  const scenarios = {
    "browser-origin-control-plane-bypass": scenario(failed.has("browser-origin-control-plane-bypass") ? "FAIL" : checks.mainPageStatus ? "PASS" : "PARTIAL", "real Chromium navigation through fixed Caddy HTTPS identity"),
    "cross-origin-session-abuse": scenario(failed.has("cross-origin-session-abuse") ? "FAIL" : "PASS", "fixed hostile HTTP origin plus credentialed browser fetch"),
    "csrf-protected-mutation": scenario("PARTIAL", "hostile-origin mutation rejection is covered by pocketlab-runtime-360; authenticated browser fixture is intentionally absent", "no Owner credential is injected into Chromium"),
    "owner-session-lifecycle": scenario("NOT_ASSESSED", "requires disposable browser identity and revocation fixture", "production Owner/passkey material is never injected into assurance"),
    "authorization-resource-boundary": scenario("NOT_ASSESSED", "requires bounded lower-authority application identity fixture", "external browser lane cannot manufacture application authority"),
    "websocket-auth-boundary": scenario(failed.has("websocket-auth-boundary") ? "FAIL" : "PASS", "real Chromium hostile-origin WebSocket attempt to /ws/events"),
    "pwa-offline-secret-retention": scenario(failed.has("pwa-offline-secret-retention") ? "FAIL" : "PARTIAL", "Chromium LocalStorage/SessionStorage/Cache/IndexedDB key inventory without reading values", "authenticated logout fixture is not registered"),
    "browser-network-egress-contract": scenario(failed.has("browser-network-egress-contract") ? "FAIL" : "PASS", "Chromium request instrumentation with fixed approved host/port envelope"),
    "webauthn-challenge-boundary": scenario("NOT_ASSESSED", "virtual WebAuthn needs an explicitly provisioned disposable application identity", "no production passkey material is used"),
    "service-worker-version-integrity": scenario(failed.has("service-worker-version-integrity") ? "FAIL" : "PASS", "service-worker script origins and cache inventory"),
    "unicode-log-and-ui-injection": scenario("NOT_ASSESSED", "requires a registered synthetic untrusted-name fixture", "no arbitrary UI payload is accepted from the caller"),
  };

  return {
    schema_version: "1.0.0",
    tool: "playwright-runtime",
    version: VERSION,
    suite,
    target: "fixed_caddy_https_runtime",
    caddy_identity: identity ? "fixed_operator_approved_identity" : "fixed_loopback_identity",
    checks,
    scenario_results: scenarios,
    findings,
    raw_urls_persisted: false,
    storage_values_read: false,
    credentials_injected: false,
    sanitized: true,
  };
}

async function main() {
  if (process.argv.includes("--version")) {
    console.log(`pocketlab-playwright-runtime ${VERSION}`);
    return;
  }
  const args = process.argv.slice(2);
  if (args.length !== 1 || !["standard", "deep", "adversarial"].includes(args[0])) {
    throw new Error("one registered suite argument is required");
  }
  const result = await run(args[0]);
  process.stdout.write(JSON.stringify(result) + "\n");
}

main().catch(error => {
  process.stderr.write(JSON.stringify({ status: "FAILED", failure_code: error?.name || "browser_probe_failed", sanitized: true }) + "\n");
  process.exitCode = 1;
});
