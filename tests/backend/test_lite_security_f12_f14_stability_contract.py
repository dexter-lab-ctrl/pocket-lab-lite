import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW_MODELS = ROOT / "src/lib/liteViewModels.js"
STORE = ROOT / "src/stores/liteUiStore.js"
LITE_SECURITY = ROOT / "src/lite/LiteSecurity.jsx"
LITE_QUERY = ROOT / "src/lib/liteQueryClient.js"
LITE_STATUS = ROOT / "src/hooks/useLiteStatus.js"


def _run_node_script(script: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_security_f12_selectors_preserve_identity_for_unchanged_revisions():
    script = r'''
      import assert from 'node:assert/strict';
      import {
        EMPTY_ARRAY,
        selectSecurityScreenView,
        selectSecurityProfileView,
        selectSecurityHistorySummaryView,
        selectSecurityEvidenceSummaryView,
        selectSecurityTimelineView,
      } from './src/lib/liteViewModels.js';

      const payload = {
        revision: 'security-summary-alpha',
        history_revision: 'security-history-alpha',
        profile_revisions: { quick: 'security-profile-quick-alpha', full: 'security-profile-full-alpha', app: 'security-profile-app-alpha' },
        status: 'healthy',
        summary: 'No urgent safety issues',
        score: 96,
        checked_at: '2026-07-09T00:00:00Z',
        last_run: {
          run_id: 'run-quick-alpha',
          scan_profile: 'quick',
          status: 'succeeded',
          score: 96,
          completed_at: '2026-07-09T00:00:00Z',
          coverage_summary: { profile: 'quick', checked_targets: ['Pocket Lab Lite files'], target_statuses: [{ target_id: 'pocketlab', status: 'ready' }] },
          tool_results: { lynis: { status: 'succeeded' }, trivy: { status: 'succeeded', sbom_saved: true } },
          execution_timeline: [{ key: 'request', title: 'Request accepted', status: 'done' }],
          evidence_refs: ['coverage-summary.json'],
        },
        history: [
          { run_id: 'run-quick-alpha', scan_profile: 'quick', status: 'succeeded', score: 96, completed_at: '2026-07-09T00:00:00Z' },
          { run_id: 'run-full-alpha', scan_profile: 'full', status: 'succeeded', score: 91, completed_at: '2026-07-08T00:00:00Z' },
        ],
        evidence_refs: ['coverage-summary.json'],
        finding_delta: { new_count: 0, resolved_count: 1, unchanged_count: 0, updated_at: '2026-07-09T00:00:00Z' },
        findings: [],
        critical_issues: [],
      };

      const screenA = selectSecurityScreenView(payload);
      const screenB = selectSecurityScreenView(payload);
      assert.equal(screenA, screenB);
      assert.equal(screenA.security_profiles, screenB.security_profiles);
      assert.equal(screenA.profile_latest, screenB.profile_latest);
      assert.equal(screenA.history, screenB.history);
      assert.equal(screenA.evidence_summary, screenB.evidence_summary);
      assert.equal(screenA.security_profiles.quick, screenB.security_profiles.quick);
      assert.equal(screenA.security_profiles.quick.coverage_summary, screenB.security_profiles.quick.coverage_summary);
      assert.equal(screenA.security_profiles.quick.execution_timeline, screenB.security_profiles.quick.execution_timeline);
      assert.equal(screenA.security_profiles.quick.evidence_summary, screenB.security_profiles.quick.evidence_summary);

      const quickA = selectSecurityProfileView(payload, 'quick');
      const quickB = selectSecurityProfileView(payload, 'quick');
      assert.equal(quickA, quickB);
      assert.equal(quickA.history, quickB.history);
      assert.equal(quickA.tool_results, quickB.tool_results);

      const historyA = selectSecurityHistorySummaryView(payload);
      const historyB = selectSecurityHistorySummaryView(payload);
      assert.equal(historyA, historyB);

      const evidenceA = selectSecurityEvidenceSummaryView(payload);
      const evidenceB = selectSecurityEvidenceSummaryView(payload);
      assert.equal(evidenceA, evidenceB);

      const emptyPayload = { revision: 'empty-security' };
      assert.equal(selectSecurityHistorySummaryView(emptyPayload), EMPTY_ARRAY);
      assert.equal(selectSecurityTimelineView(emptyPayload), EMPTY_ARRAY);
    '''
    _run_node_script(script)


def test_security_f12_changed_revision_returns_new_references():
    script = r'''
      import assert from 'node:assert/strict';
      import { selectSecurityScreenView, selectSecurityProfileView, selectSecurityHistorySummaryView } from './src/lib/liteViewModels.js';

      const payload = {
        revision: 'security-summary-alpha',
        history_revision: 'security-history-alpha',
        profile_revisions: { quick: 'security-profile-quick-alpha' },
        status: 'healthy',
        last_run: { run_id: 'run-quick-alpha', scan_profile: 'quick', status: 'succeeded', completed_at: '2026-07-09T00:00:00Z' },
        history: [{ run_id: 'run-quick-alpha', scan_profile: 'quick', status: 'succeeded', completed_at: '2026-07-09T00:00:00Z' }],
      };

      const screenA = selectSecurityScreenView(payload);
      const quickA = selectSecurityProfileView(payload, 'quick');
      const historyA = selectSecurityHistorySummaryView(payload);

      payload.revision = 'security-summary-bravo';
      payload.profile_revisions.quick = 'security-profile-quick-bravo';
      payload.history_revision = 'security-history-bravo';
      payload.history = [{ run_id: 'run-quick-bravo', scan_profile: 'quick', status: 'succeeded', completed_at: '2026-07-09T00:01:00Z' }];
      payload.last_run = { run_id: 'run-quick-bravo', scan_profile: 'quick', status: 'succeeded', completed_at: '2026-07-09T00:01:00Z' };

      const screenB = selectSecurityScreenView(payload);
      const quickB = selectSecurityProfileView(payload, 'quick');
      const historyB = selectSecurityHistorySummaryView(payload);

      assert.notEqual(screenA, screenB);
      assert.notEqual(quickA, quickB);
      assert.notEqual(historyA, historyB);
      assert.equal(quickB.run_id, 'run-quick-bravo');
    '''
    _run_node_script(script)


def test_security_f14_zustand_store_has_ui_only_security_manage_state():
    store = STORE.read_text()

    for field in (
        "securityManageOpen",
        "activeSecurityProfile",
        "activeSecurityManageSection",
        "activeSecurityDetailsPanel",
        "expandedSecurityFindingId",
        "lastSecurityRunIdViewed",
        "activeSecurityHistoryLimit",
        "activeSecurityEvidenceRunId",
        "activeSecurityDetailsRunId",
        "setSecurityManageOpen",
        "setActiveSecurityProfile",
        "setActiveSecurityDetailsPanel",
        "setExpandedSecurityFindingId",
        "useLiteSecurityManageState",
    ):
        assert field in store

    assert "localStorage" not in store
    assert "sessionStorage" not in store
    assert "raw FastAPI" not in store
    assert "command_payload" not in store
    assert "token" not in store.lower()
    assert "LITE_UI_STORE_SECURITY_UI_ONLY" in store
    assert "LITE_UI_STORE_DOES_NOT_STORE_SECURITY_PAYLOADS" in store


def test_security_f14_security_screen_uses_zustand_and_preserves_split_reads():
    screen = LITE_SECURITY.read_text()
    query = LITE_QUERY.read_text()
    status = LITE_STATUS.read_text()

    assert "useLiteUiStore" in screen
    assert "state.securityManageOpen" in screen
    assert "state.activeSecurityProfile" in screen
    assert "state.activeSecurityDetailsPanel" in screen
    assert "state.expandedSecurityFindingId" in screen
    assert "setExpandedSecurityFindingId(securityFindingUiId(finding))" in screen
    assert "const [securityManageOpen, setSecurityManageOpen] = useState" not in screen
    assert "const [activeSecurityDetails, setActiveSecurityDetails] = useState" not in screen
    assert "const [selectedFinding, setSelectedFinding] = useState" not in screen

    assert "liteApi.securitySummary" in screen
    assert "liteApi.securityProfile(scanProfile)" in screen
    assert "liteApi.securityHistory(activeSecurityHistoryLimit || 20)" in screen
    assert "liteApi.securityProgress()" in screen
    assert "liteApi.securityEvidenceSummary(runId)" in screen
    assert "liteApi.securityDetails" not in screen.partition("export default function SecurityScreen")[2].partition("return (")[0]
    assert "liteQueryKeys.fleet" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]
    assert "liteQueryKeys.recovery" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]
    assert "liteQueryKeys.catalog" not in screen.partition("lastSecurityFreshnessRef")[2].partition("const [evidence")[0]

    assert "securityFreshness" in query
    assert "securityProfile" in query
    assert "securityHistory" in query
    assert "securityProgress" in query
    assert "securityFreshness" in status


def test_security_f12_f14_frontend_execution_boundaries_hold():
    combined = "\n".join([
        VIEW_MODELS.read_text(),
        STORE.read_text(),
        LITE_SECURITY.read_text(),
    ]).lower()

    assert "nats.connect" not in combined
    assert "child_process" not in combined
    assert "spawn(" not in combined
    assert "exec(" not in combined
    assert "from 'fs'" not in combined
    assert "from \"fs\"" not in combined
    assert "localstorage.setitem" not in combined
    assert "sessionstorage.setitem" not in combined
    assert "lynis" not in STORE.read_text().lower()
    assert "trivy" not in STORE.read_text().lower()
