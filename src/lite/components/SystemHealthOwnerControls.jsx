import React, { useState } from 'react';
import { LiteButton, LiteActionRow } from '../LiteUi.jsx';
import { liteApi } from '../../lib/liteApi.js';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';

const labels = {
  'storage.evidence.preview': 'Preview old evidence',
  'storage.evidence.retention': 'Remove reviewed old evidence records',
  'sqlite.checkpoint.passive': 'Run passive database checkpoint',
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
    queryFn: liteApi.healthMaintenanceHistory, enabled: allowed && section === 'storage',
    staleTime: 0, pollingMode: 'off',
  });
  if (!allowed) return null;
  const available = maintenance.data?.available_operations || [];
  const rows = maintenance.data?.items || [];
  const used = new Set(rows.filter(row => ['queued','executing','verified','uncertain'].includes(row.status)).map(row => row.preview_id));
  const preview = rows.find(row => row.operation_id === 'storage.evidence.preview' && row.status === 'verified' &&
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
  const request = (operation, previewId = '') => review(labels[operation], operation === 'storage.evidence.retention'
    ? 'Remove only the exact reviewed old database evidence records. Personal files and raw evidence files are not removed.'
    : operation === 'storage.evidence.preview' ? 'Prepare a bounded review without deleting records.' : 'Request a passive checkpoint. A busy database does not count as verified.', async () => {
      const key = globalThis.crypto?.randomUUID?.();
      if (!key) throw new Error('secure_request_id_unavailable');
      const result = await liteApi.healthMaintenanceRequest({operation_id:operation,preview_id:previewId,idempotency_key:key,confirm:true});
      await maintenance.refresh(); return states[result.status] || 'Review recorded operation.';
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
      <LiteActionRow label="Recovery preference" value={prefs.recovery_mode === 'assisted' ? 'Assisted' : 'Monitor'} />
      <LiteButton haptic tone="secondary" disabled={busy} onClick={() => preference('recovery_mode', prefs.recovery_mode === 'assisted' ? 'monitor' : 'assisted')}> {prefs.recovery_mode === 'assisted' ? 'Prefer monitoring' : 'Prefer assisted recovery'} </LiteButton>
    </>}
    {section === 'protection' && prefs && <>
      <LiteActionRow label="Saved resource preference" value={{balanced:'Balanced',low_power:'Low power',maintenance:'Maintenance'}[prefs.resource_mode] || 'Not confirmed'} summary="A preference is not proof of active workload deferral." />
      {['balanced','low_power','maintenance'].filter(mode => mode !== prefs.resource_mode).map(mode => <LiteButton key={mode} haptic tone="secondary" disabled={busy} onClick={() => preference('resource_mode',mode)}>{'Prefer ' + mode.replace('_',' ')}</LiteButton>)}
    </>}
    {section === 'storage' && <>
      <LiteButton haptic tone="secondary" disabled={busy || maintenance.refreshing} onClick={() => maintenance.refresh()}>Refresh operation status</LiteButton>
      {maintenance.error ? <p>Maintenance status unavailable.</p> : null}
      {!available.length && <p>No new maintenance operation is enabled.</p>}
      {available.includes('storage.evidence.preview') && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request('storage.evidence.preview')}>Preview old evidence</LiteButton>}
      {available.includes('storage.evidence.retention') && preview && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request('storage.evidence.retention',preview.command_id)}>Review removal of {preview.evidence.candidate_count} records</LiteButton>}
      {available.includes('sqlite.checkpoint.passive') && <LiteButton haptic tone="secondary" disabled={busy} onClick={() => request('sqlite.checkpoint.passive')}>Review passive checkpoint</LiteButton>}
      {rows.slice(0,10).map(row => <LiteActionRow key={row.command_id} label={labels[row.operation_id] || 'Maintenance operation'} value={states[row.status] || 'Not confirmed'} summary={typeof row.evidence?.candidate_count === 'number' ? row.evidence.candidate_count + ' reviewed records; reclaimable bytes not confirmed.' : undefined}/>)}
    </>}
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
