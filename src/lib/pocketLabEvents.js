import { enterpriseDisplayText, enterpriseOperationLabel, enterpriseStatusLabel } from './enterpriseLabels.js';
const DEFAULT_LIMIT = 50;

export function eventSocketUrl(path = '/ws/events') {
  if (typeof window === 'undefined') return path;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

export function eventKey(event) {
  return String(event?.id || `${event?.subject || 'event'}:${event?.time || ''}:${JSON.stringify(event?.data || {})}`);
}

export function matchesPocketLabEvent(event, {
  subjectPrefixes = [],
  eventTypes = [],
  operations = [],
  jobId = '',
} = {}) {
  if (!event) return false;
  const subject = String(event.subject || '');
  const type = String(event.type || '');
  const data = event.data || {};
  if (subjectPrefixes.length > 0 && !subjectPrefixes.some((prefix) => subject.startsWith(prefix))) return false;
  if (eventTypes.length > 0 && !eventTypes.includes(type)) return false;
  if (operations.length > 0 && !operations.includes(String(data.operation || event.operation || ''))) return false;
  if (jobId && String(data.job_id || event.job_id || '') !== String(jobId)) return false;
  return true;
}

export function mergeEvents(previous, incoming, limit = DEFAULT_LIMIT) {
  const seen = new Set();
  const merged = [];
  [...incoming, ...previous].forEach((event) => {
    const key = eventKey(event);
    if (seen.has(key)) return;
    seen.add(key);
    merged.push(event);
  });
  return merged
    .sort((a, b) => new Date(b.time || 0).getTime() - new Date(a.time || 0).getTime())
    .slice(0, limit);
}

function subjectIncludes(event, token) {
  return String(event?.subject || '').includes(token) || String(event?.type || '').includes(token);
}

export function eventTone(event) {
  const text = `${event?.subject || ''} ${event?.type || ''} ${event?.data?.status || ''} ${event?.data?.level || ''}`.toLowerCase();
  if (text.includes('dead_letter') || text.includes('failed') || text.includes('error') || text.includes('unhealthy') || text.includes('blocked')) return 'danger';
  if (text.includes('retry') || text.includes('warning') || text.includes('drift') || text.includes('degraded') || text.includes('pending')) return 'warning';
  if (text.includes('succeeded') || text.includes('healthy') || text.includes('completed') || text.includes('started')) return 'success';
  return 'info';
}

export function friendlyEvent(event, simpleMode = false) {
  const data = event?.data || {};
  const subject = String(event?.subject || '');
  const type = String(event?.type || '');
  const operation = String(data.operation || event?.operation || '');
  const operationLabel = enterpriseOperationLabel(operation, 'Operation');
  const status = String(data.status || '');
  const jobId = String(data.job_id || event?.job_id || '');

  if (subjectIncludes(event, 'operation.log')) {
    const step = String(data.step || data.stream || '').replace(/_/g, ' ');
    const message = String(data.message || data.event?.message || type || 'Progress update');
    return {
      title: simpleMode ? 'Action progress updated' : `Operation activity${operation ? `: ${operationLabel}` : ''}`,
      detail: simpleMode
        ? message
        : enterpriseDisplayText(`${jobId ? `Reference ${jobId}: ` : ''}${step ? `[${step}] ` : ''}${message}`),
    };
  }


  if (subject.includes('pocketlab.events.workflow') || type.includes('workflow.') || subject.includes('pocketlab.dlq.')) {
    if (type.includes('replay_requested') || type.includes('dead_letter_replayed')) {
      return {
        title: simpleMode ? 'Action restarted safely' : 'Workflow replay requested',
        detail: simpleMode
          ? 'Pocket Lab started a fresh safe attempt from the saved recovery history.'
          : `workflow=${data.workflow_id || data.replay_of || 'unknown'} replayed_as=${data.replayed_as || data.command_id || 'pending'}`,
      };
    }
    if (type.includes('recovery_completed')) {
      return {
        title: simpleMode ? 'Recovery check completed' : 'Workflow recovery completed',
        detail: simpleMode
          ? 'Pocket Lab checked interrupted actions and restarted anything safe to retry.'
          : `operation_recovered=${data.operation_recovered_count || 0}, workflow_recovered=${data.workflow_recovered_count || 0}`,
      };
    }
    if (type.includes('state_reconstructed') || type.includes('reconstructed')) {
      return {
        title: simpleMode ? 'Action history rebuilt' : 'Workflow state reconstructed',
        detail: simpleMode
          ? 'Pocket Lab rebuilt action history from saved events.'
          : `workflow=${data.workflow_id || 'unknown'} events=${data.event_count || 'unknown'}`,
      };
    }
    return {
      title: simpleMode ? 'Recovery workflow updated' : 'Workflow activity received',
      detail: simpleMode
        ? 'Pocket Lab updated its saved action recovery state.'
        : (data.workflow_id || data.status || type || subject),
    };
  }

  if (subjectIncludes(event, 'command.retry_scheduled')) {
    return {
      title: simpleMode ? 'Action will retry' : 'Retry scheduled',
      detail: simpleMode
        ? 'Pocket Lab hit a temporary problem and will try the action again safely.'
        : `${data.command_subject || data.subject || 'command'} retry ${data.attempt || 'next'} in ${data.retry_delay_seconds || 'a few'}s: ${data.error || ''}`,
    };
  }
  if (subjectIncludes(event, 'command.dead_lettered') || subject.startsWith('pocketlab.dlq.')) {
    return {
      title: simpleMode ? 'Action paused for review' : 'Action moved to recovery queue',
      detail: simpleMode
        ? 'Pocket Lab stopped retrying this action to avoid unsafe repeated changes.'
        : `${data.original_subject || data.command_subject || subject} failed after ${data.attempt || 'several'} attempts: ${data.error || 'unknown error'}`,
    };
  }

  if (subjectIncludes(event, 'operation.failed')) {
    return {
      title: simpleMode ? 'Action needs attention' : `Operation needs attention${operation ? `: ${operationLabel}` : ''}`,
      detail: simpleMode ? 'The requested action could not finish. Open advanced details or try again.' : enterpriseDisplayText(data.error || data.stderr || `Reference ${jobId || 'unknown'} failed.`),
    };
  }
  if (subjectIncludes(event, 'operation.succeeded')) {
    return {
      title: simpleMode ? 'Action completed' : `Operation completed${operation ? `: ${operationLabel}` : ''}`,
      detail: simpleMode ? 'The requested change finished successfully.' : `Reference ${jobId || 'unknown'} completed successfully.`,
    };
  }
  if (subjectIncludes(event, 'operation.started') || subjectIncludes(event, 'operation.worker_claimed')) {
    return {
      title: simpleMode ? 'Action is running' : `Operation in progress${operation ? `: ${operationLabel}` : ''}`,
      detail: simpleMode ? 'Pocket Lab is applying the requested change now.' : `Executor is processing reference ${jobId || 'unknown'}.`,
    };
  }
  if (subjectIncludes(event, 'operation.created') || subjectIncludes(event, 'operation.execute')) {
    return {
      title: simpleMode ? 'Action queued' : `Operation queued${operation ? `: ${operationLabel}` : ''}`,
      detail: simpleMode ? 'Pocket Lab accepted the request and is preparing it.' : `Queued reference ${jobId || 'unknown'} for governed execution.`,
    };
  }
  if (subject.includes('pocketlab.events.health')) {
    const snapshot = data.snapshot || data.health || {};
    const healthStatus = data.status || snapshot.status || status;
    if (type.includes('service_changed')) {
      return {
        title: simpleMode ? 'A service changed status' : `Health service changed: ${data.service || 'service'}`,
        detail: simpleMode
          ? `${data.service || 'A service'} is now ${data.current || 'updated'}.`
          : `${data.service || 'service'}: ${data.previous || 'unknown'} → ${data.current || 'unknown'}`,
      };
    }
    if (type.includes('checked')) {
      return {
        title: simpleMode ? 'System check completed' : 'Health check sampled',
        detail: simpleMode ? `Overall status: ${healthStatus || 'unknown'}.` : JSON.stringify(data.summary || snapshot.summary || {}),
      };
    }
    return {
      title: simpleMode ? 'System health updated' : 'Health activity received',
      detail: simpleMode ? `Overall status: ${healthStatus || 'unknown'}.` : (JSON.stringify(data.summary || snapshot.summary || {}) || type || subject),
    };
  }
  if (subject.includes('pocketlab.events.telemetry')) {
    const sample = data.sample || data.telemetry || {};
    const cpu = sample.cpu_usage_percent ?? sample.cpuUsagePercent;
    const temp = sample.cpu_temp_c ?? sample.cpuTemp;
    const detail = cpu !== undefined || temp !== undefined
      ? `CPU ${cpu ?? '—'}%, temp ${temp ?? '—'}°C`
      : (status || 'New telemetry sample available.');
    return {
      title: simpleMode ? (type.includes('changed') ? 'System status changed' : 'System status updated') : `Telemetry ${type.includes('changed') ? 'changed' : 'sample'} received`,
      detail: simpleMode ? 'Device power, memory, or storage was refreshed.' : detail,
    };
  }
  if (subject.includes('pocketlab.events.live_status')) {
    return {
      title: simpleMode ? 'Live monitoring updated' : 'Live monitoring activity',
      detail: simpleMode ? 'Pocket Lab live monitoring is running.' : (data.component || data.error || status || type),
    };
  }
  if (subject.includes('pocketlab.events.drift')) {
    return {
      title: simpleMode ? 'Change check updated' : 'Configuration health activity received',
      detail: simpleMode ? 'Pocket Lab updated what changed versus what should be installed.' : (data.summary || status || type),
    };
  }
  if (subject.includes('pocketlab.events.fleet.node_command_result')) {
    return {
      title: simpleMode ? 'Device check completed' : 'Device command result',
      detail: simpleMode
        ? `${data.name || data.hostname || data.node_id || 'A device'} responded to a device check.`
        : `${data.node_id || 'node'} · ${data.command || 'command'} · ${data.status || status || 'completed'}`,
    };
  }
  if (subject.includes('pocketlab.events.fleet.node_heartbeat') || subject.includes('pocketlab.events.fleet.node_seen')) {
    return {
      title: simpleMode ? 'Device checked in' : 'Device heartbeat',
      detail: simpleMode
        ? `${data.name || data.hostname || data.node_id || 'A device'} is connected.`
        : `${data.node_id || 'node'} · ${data.role || 'role'} · ${data.agent_version || 'agent'}`,
    };
  }
  if (subject.includes('pocketlab.events.fleet.node_telemetry')) {
    const t = data.telemetry || {};
    return {
      title: simpleMode ? 'Device status updated' : 'Device telemetry',
      detail: simpleMode
        ? `${data.name || data.node_id || 'A device'} sent a live status update.`
        : `${data.node_id || 'node'} CPU ${t.cpu_usage_percent ?? '—'}%, temp ${t.cpu_temp_c ?? '—'}°C`,
    };
  }
  if (subject.includes('pocketlab.events.fleet.node_health')) {
    const h = data.health || {};
    return {
      title: simpleMode ? 'Device health updated' : 'Device health',
      detail: simpleMode
        ? `${data.name || data.node_id || 'A device'} is ${h.status || data.status || 'updated'}.`
        : `${data.node_id || 'node'} health=${h.status || 'unknown'}`,
    };
  }
  if (subject.includes('pocketlab.events.fleet')) {
    return {
      title: simpleMode ? 'Device status changed' : 'Device fleet activity received',
      detail: simpleMode ? 'A device invite, device agent, or device health state changed.' : (data.hostname || data.node_id || data.role || status || type),
    };
  }
  if (subject.includes('pocketlab.events.release')) {
    const stageTitle = data.title || data.stage || data.workflow || '';
    if (type.includes('stage.started')) {
      return {
        title: simpleMode ? 'Update step started' : `Release stage started${stageTitle ? `: ${stageTitle}` : ''}`,
        detail: simpleMode ? (data.detail || 'Pocket Lab started the next safe update step.') : (data.detail || data.stage || subject),
      };
    }
    if (type.includes('stage.completed')) {
      return {
        title: simpleMode ? 'Update step completed' : `Release stage completed${stageTitle ? `: ${stageTitle}` : ''}`,
        detail: simpleMode ? 'One update step finished successfully.' : (data.stage || status || type),
      };
    }
    if (type.includes('stage.failed') || type.includes('workflow.failed')) {
      return {
        title: simpleMode ? 'Update needs attention' : 'Release workflow failed',
        detail: simpleMode ? 'Pocket Lab stopped the update because one step failed.' : (data.error || data.stage || status || type),
      };
    }
    if (type.includes('workflow.started')) {
      return {
        title: simpleMode ? 'Safe update started' : 'Release workflow started',
        detail: simpleMode ? 'Pocket Lab is backing up, updating, and checking the system.' : (data.workflow || subject),
      };
    }
    if (type.includes('workflow.completed') || type.includes('applied')) {
      return {
        title: simpleMode ? 'Update workflow completed' : 'Release workflow completed',
        detail: simpleMode ? 'The update workflow finished and the app can refresh when ready.' : (data.latest_tag || data.workflow || status || type),
      };
    }
    if (type.includes('available')) {
      return {
        title: simpleMode ? 'Update available' : 'Release available',
        detail: simpleMode ? 'An approved Pocket Lab update is available.' : `${data.current_tag || 'unknown'} → ${data.latest_tag || 'unknown'}`,
      };
    }
    return {
      title: simpleMode ? 'Update workflow changed' : 'Release event received',
      detail: simpleMode ? 'The update workflow has new progress.' : (stageTitle || status || type),
    };
  }
  if (subject.includes('pocketlab.events.security') || subject.includes('pocketlab.audit')) {
    return {
      title: simpleMode ? 'Safety status changed' : 'Security and audit activity received',
      detail: simpleMode ? 'A safety check or policy event was recorded.' : (data.rule || data.policy || status || type),
    };
  }
  if (subject.includes('pocketlab.events.catalog') || subject.includes('pocketlab.events.blueprint')) {
    return {
      title: simpleMode ? 'Apps & Services updated' : 'Catalog and service package activity received',
      detail: simpleMode ? 'App list or install progress changed.' : (data.name || data.ref || status || type),
    };
  }
  if (subject.includes('pocketlab.events.worker')) {
    return {
      title: simpleMode ? 'Helper service updated' : 'Execution activity received',
      detail: simpleMode ? 'The background helper service reported its status.' : (status || data.worker || type),
    };
  }
  if (type === 'bus.status') {
    return {
      title: simpleMode ? 'Live updates connected' : 'Activity stream status',
      detail: simpleMode ? 'Pocket Lab can stream progress updates.' : `Activity mode: ${data?.mode || event?.data?.mode || 'unknown'}`,
    };
  }
  return {
    title: simpleMode ? 'Pocket Lab update' : enterpriseDisplayText(type || subject || 'Pocket Lab activity'),
    detail: simpleMode ? 'A background update was received.' : enterpriseDisplayText(subject),
  };
}

export function formatEventTime(event) {
  if (!event?.time) return 'now';
  try {
    return new Date(event.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return 'now';
  }
}
