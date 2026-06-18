export function eventMotionFlags(event = {}) {
  const data = event.data || {};
  const text = [
    event.subject,
    event.type,
    data.status,
    data.phase,
    data.decision,
    data.event,
    data.reason,
  ].filter(Boolean).join(' ').toLowerCase();

  return {
    workerClaimed: text.includes('worker_claimed') || text.includes('worker claimed') || text.includes('worker.claimed'),
    approvalRequired: text.includes('approval_required') || text.includes('approval required') || text.includes('pending_approval') || text.includes('waiting_for_approval'),
    autoApproved: text.includes('auto_approved') || text.includes('auto approved') || text.includes('auto-approved'),
  };
}

export function animatedEventStatus(event, fallbackStatus = 'running') {
  const flags = eventMotionFlags(event);
  if (flags.autoApproved) return 'auto_approved';
  if (flags.approvalRequired) return 'approval_required';
  if (flags.workerClaimed) return 'worker_claimed';
  return fallbackStatus;
}

export function animatedEventClass(event, isNew = false) {
  const flags = eventMotionFlags(event);
  return [
    isNew ? 'event-pulse-row' : '',
    flags.workerClaimed ? 'worker-claim-row' : '',
    flags.approvalRequired ? 'approval-gate-row' : '',
    flags.autoApproved ? 'auto-approval-receipt-row' : '',
  ].filter(Boolean).join(' ');
}

export function eventIdentity(event) {
  return String(event?.id || `${event?.subject || 'event'}:${event?.time || ''}:${JSON.stringify(event?.data || {})}`);
}
