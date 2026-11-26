import React, { useState } from 'react';
import { LiteButton, LiteActionRow } from '../LiteUi.jsx';
import { liteApi } from '../../lib/liteApi.js';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';

const labels = {
  'storage.evidence.preview': 'Preview old evidence',
  'storage.evidence.retention': 'Remove reviewed old evidence records',
  'sqlite.checkpoint.passive': 'Run passive database checkpoint',
  'storage.logs.preview': 'Preview expired managed log archives',
  'storage.logs.cleanup': 'Remove reviewed log archives',
  'storage.temp.preview': 'Preview abandoned rehearsal files',
  'storage.temp.cleanup': 'Remove reviewed rehearsal files',
  'recovery.database.rehearse': 'Rehearse database compatibility',
  'projection.reconcile': 'Refresh optional activity history',
  'runtime.telemetry.recover': 'Review stopped monitoring recovery',
  'runtime.server_agent.recover': 'Review stopped server agent recovery',
  'runtime.configuration.restore': 'Review gateway desired-state restoration',
};
const states = { queued: 'Queued', executing: 'Working', verified: 'Verified', blocked: 'Blocked', uncertain: 'Outcome not confirmed', expired: 'Expired', cancelled: 'Cancelled' };

export default function SystemHealthOwnerControls({ section, policy, history, refreshPolicy, refreshHistory, readOnly }) {
  const allowed = !readOnly && policy?.owner_controls_available === true;
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const prefs = policy?.activation_policy?.preferences;
  const maintenance = useLiteQuery({
    queryKey: ['lite', 'system-health', 'maintenance'], path: '/api/lite/system-health/maintenance',
    queryFn: liteApi.healthMaintenanceHistory, enabled: allowed && ['storage','backup','services','operations','history'].includes(section),
    staleTime: 0, pollingMode: 'off',
  });
  if (!allowed) return null;
  const available = maintenance.data?.available_operations || [];
  const rows = maintenance.data?.items || [];
  const catalog = Array.isArray(policy?.repair_catalog) ? policy.repair_catalog : [];
  const qualified = catalog.filter(item => item?.source_qualified);
  const activation = policy?.activation_policy || {};
  const assistedFence = activation.activation_confirmation?.assisted;
  const policyAuthority = policy?.policy_authority;
  const used = new Set(rows.filter(row => ['queued','executing','verified','uncertain'].includes(row.status)).map(row => row.preview_id));
  const previewFor = operation => rows.find(row => row.operation_id === operation && row.status === 'verified' &&
    row.evidence?.candidate_count > 0 && Date.parse(row.expires_at) > Date.now() && !used.has(row.command_id));
  const review = (title, detail, execute) => { setMessage(''); setPending({ title, detail, execute }); };
  const confirm = async () => {
    if (!pending || busy || !allowed) return;
    setBusy(true); setMessage('');
    try { setMessage(await pending.execute()); }
    catch { setMessage('The request was not confirmed. Refresh the recorded state before trying again.'); }
    finally { setPending(null); setBusy(false); }
  };
  const preference = (key, value) => review('Save preference', 'This records your preference. It cannot activate an unqualified operation.', async () => {
    await liteApi.healthPreferences({ expected_revision: prefs.revision, recovery_mode: prefs.recovery_mode, resource_mode: prefs.resource_mode, [key]: value });
    await refreshPolicy(); return 'Preference saved.';
  });
  const request = (operation, previewId = '') => review(labels[operation], operation.endsWith('.preview')
    ? 'Prepare a bounded review without deleting records.'
    : operation.endsWith('.cleanup') || operation === 'storage.evidence.retention'
      ? 'Remove only the exact reviewed owner-approved candidates. Personal files and active data are protected.'
      : operation === 'recovery.database.rehearse' ? 'Verify and migrate the latest verified database package on a private copy. No live restore or service interruption.'
      : operation === 'runtime.configuration.restore' ? 'Reconcile only a confirmed gateway desired-state mismatch through the existing runtime owner. No arbitrary configuration or secrets are accepted.'
      : operation.startsWith('runtime.') ? 'Request recovery of a confirmed stopped service through its existing supervisor. Current authority and restart budget must permit it.'
      : operation === 'projection.reconcile' ? 'Ask the existing scheduler to refresh optional activity history.'
      : 'Request a passive checkpoint. A busy database does not count as verified.', async () => {
      const key = globalThis.crypto?.randomUUID?.();
      if (!key) throw new Error('secure_request_id_unavailable');
      const result = await liteApi.healthMaintenanceRequest({operation_id:operation,preview_id:previewId,idempotency_key:key,confirm:true});
      await maintenance.refresh(); return states[result.status] || 'Review recorded operation.';
    });
  const resolveMaintenance = row => review('Close uncertain outcome', 'Acknowledge that the result could not be verified. This does not mark the operation successful or authorize replay.', async () => {
    await liteApi.healthResolveMaintenance(row.command_id); await maintenance.refresh(); return 'Closed without verification.';
  });
  const cancelMaintenance = row => review('Cancel queued maintenance', 'Only work that has not started can be cancelled.', async () => {
    await liteApi.healthCancelMaintenance(row.command_id); await maintenance.refresh(); return 'Review recorded cancellation.';
  });
  const automatic = policy?.selective_automation;
  const changeAutomatic = () => review('Save selective automation preference', 'Only optional activity history reconciliation is eligible. Production qualification and explicit activation are separate requirements.', async () => {
    await liteApi.healthAutomaticPolicy({expected_revision:automatic.revision,enabled:!automatic.preference_enabled,confirm:true});
    await refreshPolicy(); return 'Preference saved. Execution remains subject to backend gates.';
  });
  const exportScope = (scope) => review('Export diagnostic summary', 'Download only the selected sanitized summary, not raw logs or credentials.', async () => {
    const result = await liteApi.healthDiagnosticExport({ scope, confirm: true });
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'pocketlab-system-health.json';
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    return 'Diagnostic summary exported.';
  });
  const cancel = row => review('Cancel recovery request', 'Cancel only before the execution owner starts. Running work cannot be interrupted here.', async () => {
    const result = await liteApi.healthCancelRecovery(row.request_id);
    await refreshHistory(); return result.status === 'cancelled' ? 'Recovery request cancelled.' : 'Review recorded request.';
  });
  return <section className="lite-system-health-manage-section" aria-label="Owner controls">
    <h3>Owner controls</h3>
    {section === 'policies' && prefs && <>
      <LiteActionRow label="Built-in protection" value="Always on" summary="System Health remains fail-closed; the browser is not an execution or authorization authority." />
      <LiteActionRow label="Recovery preference" value={prefs.recovery_mode === 'assisted' ? 'Assisted' : 'Monitor'} />
      <LiteActionRow label="Assisted production activation" value={activation.production_assisted_enabled ? 'Enabled' : 'Default-off'} summary={assistedFence?.valid ? 'The current Owner confirmation fence matches this runtime.' : (assistedFence?.reason_codes?.[0] || 'A current Owner confirmation is required after promotion or runtime revision changes.')} />
      <LiteActionRow label="Current Safety Rules" value={policyAuthority?.ready ? 'Authorized' : 'Pending authorization'} summary={policyAuthority?.summary || 'Protected recovery fails closed until the active known-good revision is confirmed.'} />
      <LiteActionRow label="Source-qualified assisted operations" value={qualified.length ? `${qualified.length} reviewed` : 'None'} summary={qualified.length ? qualified.map(item => item.operation_id).join(', ') : 'No operation is available from source qualification alone.'} />
      <LiteButton haptic tone="secondary" disabled={busy} onClick={() => preference('recovery_mode', prefs.recovery_mode === 'assisted' ? 'monitor' : 'assisted')}> {prefs.recovery_mode === 'assisted' ? 'Prefer monitoring' : 'Prefer assisted recovery'} </LiteButton>
    </>}
    {section === 'policies' && automatic && <>
      <LiteActionRow label="Selective history reconciliation" value={automatic.runtime_enabled ? 'Enabled' : automatic.preference_enabled ? 'Preferred · gated' : 'Off'} summary={automatic.reason_codes?.[0] || (automatic.source_qualified ? 'Activation requires current policy and runtime readiness.' : 'Production qualification pending.')} />
      <LiteButton haptic tone="secondary" disabled={busy} onClick={changeAutomatic}>{automatic.preference_enabled ? 'Disable automatic preference' : 'Prefer automatic history reconciliation'}</LiteButton>
    </>}
    {section === 'protection' && prefs && <>
      <LiteActionRow label="Saved resource preference" value={{balanced:'Balanced',low_power:'Low power',maintenance:'Maintenance'}[prefs.resource_mode] || 'Not confirmed'} summary="A preference is not proof of active workload deferral." />
      {['balanced','low_power','maintenance'].filter(mode => mode !== prefs.resource_mode).map(mode => <LiteButton key={mode} haptic tone="secondary" disabled={busy} onClick={() => preference('resource_mode',mode)}>{'Prefer ' + mode.replace('_',' ')}</LiteButton>)}
    </>}
    {section === 'storage' && <>
      <LiteButton haptic tone="secondary" disabled={busy || maintenance.refreshing} onClick={() => maintenance.refresh()}>Refresh operation status</LiteButton>
      {maintenance.error ? <p>Maintenance status unavailable.</p> : null}
      {!available.length && <p>No new maintenance operation is enabled.</p>}
      {['evidence','logs','temp'].map(scope => {
        const previewOp = 'storage.' + scope + '.preview';
        const applyOp = 'storage.' + scope + (scope === 'evidence' ? '.retention' : '.cleanup');
        const preview = previewFor(previewOp);
        return <React.Fragment key={scope}>
          {available.includes(previewOp) && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request(previewOp)}>{labels[previewOp]}</LiteButton>}
          {available.includes(applyOp) && preview && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request(applyOp,preview.command_id)}>{labels[applyOp]} ({preview.evidence.candidate_count})</LiteButton>}
        </React.Fragment>;
      })}
      {available.includes('sqlite.checkpoint.passive') && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request('sqlite.checkpoint.passive')}>Review passive checkpoint</LiteButton>}
    </>}
    {['backup','services','operations'].includes(section) && <>
      <LiteButton haptic tone="secondary" disabled={busy || maintenance.refreshing} onClick={() => maintenance.refresh()}>Refresh operation status</LiteButton>
      {(section === 'backup' ? ['recovery.database.rehearse'] : section === 'services' ? ['runtime.telemetry.recover','runtime.server_agent.recover','runtime.configuration.restore'] : ['projection.reconcile']).filter(op => available.includes(op)).map(op => <LiteButton key={op} haptic tone="secondary" disabled={busy} onClick={() => request(op)}>{labels[op]}</LiteButton>)}
    </>}
    {['storage','backup','services','operations','history'].includes(section) && rows.slice(0,10).map(row => <LiteActionRow key={row.command_id} label={labels[row.operation_id] || 'Maintenance operation'} value={row.resolution === 'closed_unverified' ? 'Closed · not verified' : states[row.status] || 'Not confirmed'}
      summary={typeof row.evidence?.allocated_candidate_bytes === 'number' ? row.evidence.allocated_candidate_bytes + ' allocated bytes in reviewed candidates; actual freed space not confirmed.' : typeof row.evidence?.candidate_count === 'number' ? row.evidence.candidate_count + ' reviewed records' : undefined}
      action={row.status === 'queued' ? {label:'Review cancellation',haptic:true,onClick:()=>cancelMaintenance(row)} : row.status === 'uncertain' && !row.resolution ? {label:'Review closure',haptic:true,onClick:()=>resolveMaintenance(row)} : undefined}/>)}
    {section === 'history' && (history?.recovery_requests || []).filter(row => row.attempt === 0 && ['requested','preflight_checked','approval_required','approved','admitted'].includes(row.status)).map(row => <LiteActionRow key={row.request_id} label="Pending recovery request" value="Not started" action={{ label:'Review cancellation', haptic:true, onClick:() => cancel(row) }}/>)}
    {section === 'details' && <>
      <LiteButton haptic tone="secondary" disabled={busy} onClick={() => exportScope('infrastructure')}>Review infrastructure export</LiteButton>
      <LiteButton haptic tone="secondary" disabled={busy} onClick={() => exportScope('recovery_statistics')}>Review recovery statistics export</LiteButton>
    </>}
    {pending && <div className="lite-system-health-detail-block" role="group" aria-label={pending.title}>
      <h4>{pending.title}</h4><p>{pending.detail}</p>
      <LiteButton haptic tone="primary" disabled={busy} onClick={confirm}>{busy ? 'Submitting…' : 'Confirm'}</LiteButton>
      <LiteButton haptic tone="secondary" disabled={busy} onClick={() => setPending(null)}>Cancel</LiteButton>
    </div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
