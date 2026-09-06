import { http, HttpResponse } from 'msw';

export const DEVICE_FACT_SCENARIOS = new Set([
  'devices-resource-complete','devices-resource-partial','devices-resource-stale','devices-resource-unsupported','devices-resource-permission-denied','devices-resource-missing',
  'devices-capability-verified','devices-capability-pending','devices-capability-stale','devices-capability-unsupported','devices-capability-blocked','devices-capability-not-applicable','devices-capability-missing','devices-capability-mixed','devices-capability-unknown',
  'devices-services-mixed','devices-services-stale','devices-services-unknown','devices-services-disappeared',
  'devices-software-current','devices-software-outdated','devices-software-incompatible','devices-software-stale',
  'devices-secondary-complete','devices-secondary-offline-saved','devices-long-name',
]);

const now = (minutes = 0) => new Date(Date.now() - minutes * 60_000).toISOString();
const observation = (metric, value, extra = {}) => ({
  metric, value, unit: extra.unit || null, status: extra.status || 'available',
  collection_status: extra.collection_status || extra.status || 'available',
  source: extra.source || 'server_central_telemetry', observed_at: extra.observed_at || now(extra.stale ? 30 : 0),
  freshness: extra.stale ? 'stale' : extra.freshness || 'current', reason_code: extra.reason_code || 'collected',
  support_state: extra.support_state || 'supported', schema_version: 2, revision: 1,
});

function facts(source = 'server_central_telemetry') {
  return { schema_version: 2, revision: 11, device_id: source === 'agent_telemetry' ? 'test-phone-4' : 'pocket-lab-lite-server', sanitized: true, observed_at: now(),
    resources: {
      memory: observation('memory', { total_mb: 4096, free_mb: 2048, used_mb: 2048 }, { unit: 'MB', source }),
      storage: observation('storage', { total_mb: 256000, free_mb: 128000 }, { unit: 'MB', source }),
      cpu_usage: observation('cpu_usage', { usage_percent: 12 }, { unit: 'percent', source }),
      temperature: observation('temperature', { celsius: 42 }, { unit: 'celsius', source }),
      load_average: observation('load_average', { one_minute: .4, five_minute: .3, fifteen_minute: .2 }, { source }),
      uptime: observation('uptime', { seconds: 86400 }, { unit: 'seconds', source }),
    },
    software: {
      node_agent: { component: 'node_agent', version: '2.5.0', status: 'current', source: 'runtime_heartbeat', observed_at: now(), freshness: 'current', reason_code: 'version_reported' },
      supervisor: { component: 'supervisor', version: '2.5.0', status: 'current', source: 'sqlite_supervisor_evidence', observed_at: now(), freshness: 'current', reason_code: 'version_reported' },
    },
  };
}

const capability = (id, status = 'verified', extra = {}) => ({
  id, label: extra.label || id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), category: extra.category || 'execution',
  verification_strategy: extra.verification_strategy || 'runtime_evidence', status, reason_code: extra.reason_code || status,
  source: extra.source || 'runtime_evidence', advertised: extra.advertised !== false, advertised_at: extra.advertised === false ? null : now(),
  evaluated_at: now(status === 'stale' ? 30 : 0), verified_at: status === 'verified' ? now() : null,
  freshness: status === 'stale' ? 'stale' : 'current', expires_at: now(status === 'stale' ? 20 : -3), revision: 1, schema_version: 3,
});
const service = (id, extra = {}) => ({ service_id: id, label: extra.label || id.replace(/[-_.]/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), category: extra.category || 'service', manager: extra.manager || 'process_manager', state: extra.state || 'online', reported_at: now(extra.stale ? 30 : 0), freshness: extra.stale ? 'stale' : 'current', restart_supported: false, restart_reason: 'backend_guard_required', source: 'prepared_service_evidence', schema_version: 1, sanitized: true });

function mutateResources(result, scenario) {
  const r = result.resources;
  if (scenario === 'devices-resource-partial' || scenario === 'devices-resource-unsupported') r.temperature = observation('temperature', null, { status: 'unsupported', source: 'sysfs_thermal', reason_code: 'no_semantic_cpu_sensor', support_state: 'unsupported' });
  if (scenario === 'devices-resource-permission-denied') r.storage = observation('storage', null, { status: 'permission_denied', source: 'statvfs', reason_code: 'permission_denied' });
  if (scenario === 'devices-resource-missing') { delete r.temperature; delete r.load_average; }
  if (scenario === 'devices-resource-stale' || scenario === 'devices-secondary-offline-saved') Object.values(r).forEach(x => { x.status = x.collection_status === 'available' ? 'stale' : x.status; x.freshness = 'stale'; x.observed_at = now(30); });
}
function capabilities(scenario) {
  const verified = [capability('serve_control_plane','verified',{ category:'control_plane', advertised:false, source:'control_plane_runtime_evidence' }), capability('remote_access','verified',{ category:'connectivity', advertised:false, source:'remote_access_health' }), capability('host_apps','verified',{ source:'app_runtime' })];
  const one = {
    'devices-capability-pending': capability('host_apps','verification_pending',{ source:'agent_advertisement', reason_code:'advertised_not_runtime_verified' }),
    'devices-capability-stale': capability('remote_access','stale',{ category:'connectivity', source:'remote_access_health' }),
    'devices-capability-unsupported': capability('backup_target','unsupported',{ category:'recovery', source:'storage_readiness' }),
    'devices-capability-blocked': capability('receive_commands','blocked',{ source:'command_delivery_evidence' }),
    'devices-capability-not-applicable': capability('access_phone_media','not_applicable',{ category:'media', advertised:false }),
    'devices-capability-missing': capability('host_apps','not_advertised',{ advertised:false, source:'agent_advertisement' }),
    'devices-capability-unknown': capability('future_accelerator','verification_pending',{ label:'Future Accelerator', category:'custom', source:'agent_advertisement' }),
  }[scenario];
  if (one) return [one];
  if (scenario === 'devices-capability-mixed') return [...verified, capability('receive_commands','verification_pending'), capability('backup_target','unsupported',{category:'recovery'}), capability('future_accelerator','verification_pending',{label:'Future Accelerator',category:'custom'})];
  return verified;
}
function services(scenario) {
  if (scenario === 'devices-services-disappeared') return [];
  const rows = [service('gateway-alpha'), service('queue-beta',{ stale: scenario === 'devices-services-stale' }), service('future-sidecar',{ state:'unknown' })];
  if (scenario === 'devices-services-unknown') return [rows[2]];
  return rows;
}
function healthFor(device, softwareStatus = 'current') {
  const f = device.device_facts; const resources = {};
  for (const [key, o] of Object.entries(f.resources)) if (['memory','storage','cpu_usage','temperature'].includes(key)) resources[key === 'cpu_usage' ? 'load' : key] = { status: o.status === 'stale' ? 'watch' : o.collection_status === 'available' ? 'healthy' : o.status, summary: `Resource signal: ${o.status}.`, available_mb: o.value?.free_mb, total_mb: o.value?.total_mb, usage_percent: o.value?.usage_percent, celsius: o.value?.celsius, observation_status: o.status, collection_status: o.collection_status, observed_at: o.observed_at, freshness: o.freshness, source: o.source, reason_code: o.reason_code, support_state: o.support_state };
  return { status: device.connection === 'offline' ? 'degraded' : 'healthy', severity: device.connection === 'offline' ? 'review' : 'none', summary: device.connection === 'offline' ? 'Saved health is visible while this device is offline.' : 'Device health is current.', health_revision: 'device-facts-mock-v2', resources, resource_observations: f.resources, device_facts: f, versions: { status: softwareStatus }, software_posture: { status: softwareStatus, summary: `Software posture: ${softwareStatus}.` }, connection: { status: device.connection === 'offline' ? 'offline' : 'healthy', summary: 'Connection state is explicit.' }, recovery: { status:'healthy', summary:'Recovery posture available.' }, dependency_impact:{ status:'healthy', impact_summary:'No dependency impact is reported.' }, recommended_action: device.connection === 'offline' ? 'review_device' : 'none', attention_items:[], attention_count:0 };
}

export function buildDeviceFactsScenario(scenario) {
  const selected = DEVICE_FACT_SCENARIOS.has(scenario) ? scenario : 'devices-resource-complete';
  const secondaryScenario = selected.startsWith('devices-secondary-'); const offline = selected === 'devices-secondary-offline-saved';
  const serverFacts = facts(); mutateResources(serverFacts, selected);
  const secondaryFacts = facts('agent_telemetry'); if (offline) mutateResources(secondaryFacts, selected);
  const softwareStatus = selected.replace('devices-software-','');
  if (selected === 'devices-software-outdated') serverFacts.software.node_agent.version = '2.4.0';
  if (selected === 'devices-software-incompatible') serverFacts.software.node_agent.status = 'incompatible';
  if (selected === 'devices-software-stale') Object.values(serverFacts.software).forEach(x => { x.status='stale'; x.freshness='stale'; x.observed_at=now(48*60); });
  const base = (id,name,role,f,connection='online') => ({ id,node_id:id,name,hostname:name,role,role_label:role==='server_host'?'Server Host':'App Host',status:connection==='offline'?'offline':'healthy',connection,is_current:role==='server_host',protected_server_host:role==='server_host',last_seen_at:connection==='offline'?now(30):now(),agent_status:connection==='offline'?'offline':'healthy',agent_process_status:connection==='offline'?'stopped':'online',supervisor_status:'healthy',supervisor_status_freshness:connection==='offline'?'stale':'fresh',system_profile:{os_family:'android',os_name:'Android',os_version:'16',android_api_level:36,architecture:'arm64',android_abi:'arm64-v8a',technical_model:'PocketLab-Test',display_model:'PocketLab Test Device',runtime_type:'termux',agent_version:f.software.node_agent.version,supervisor_version:f.software.supervisor.version,collection_status:connection==='offline'?'stale':'current',freshness:connection==='offline'?'stale':'current',collected_at:connection==='offline'?now(48*60):now(1)},system_health:{uptime_seconds:86400,uptime_label:'1 day',load_status:'healthy',load_average:[.4,.3,.2]},device_facts:f,resource_observations:f.resources,identity:{status:'verified',blocked_join_count:0},enrollment:{enrolled_at:now(7*24*60),first_heartbeat_at:now(7*24*60)},dependencies:{hosted_apps:role==='server_host'?[{app_id:'photoprism',label:'PhotoPrism',status:'running'}]:[],hosted_app_count:role==='server_host'?1:0,backup_set_count:0,recovery_available:true},removal_assessment:{protected:role==='server_host',allowed:false,safe_to_remove:false,blockers:role==='server_host'?[{code:'protected_server_host',summary:'This control device cannot be removed.'}]:[]}});
  const server = base('pocket-lab-lite-server', selected === 'devices-long-name' ? 'Pocket Lab Edge Device With A Very Long Friendly Name For Layout Resilience Validation' : 'Pocket Lab Lite Server','server_host',serverFacts);
  server.capability_states=capabilities(selected); server.runtime_services=services(selected); server.restart_agent_assessment={allowed:false,reason_code:'server_host_protected',summary:'The protected server host uses local guarded recovery.',command_deliverable:false,supervisor_fresh:true,agent_state:'online'}; server.proactive_health=healthFor(server, selected.startsWith('devices-software-') ? softwareStatus : 'current');
  const secondary = base('test-phone-4','Test-Phone-4','compute',secondaryFacts,offline?'offline':'online'); secondary.capability_states=[capability('host_apps','verification_pending',{source:'agent_advertisement'})]; secondary.runtime_services=[]; secondary.restart_agent_assessment={allowed:!offline,reason_code:offline?'device_unreachable':'allowed',summary:offline?'Reconnect the device before sending a command.':'Pocket Lab can request a guarded device-agent restart.',command_deliverable:!offline,supervisor_fresh:!offline,agent_state:offline?'stopped':'online'}; secondary.proactive_health=healthFor(secondary,'current');
  const target = secondaryScenario ? secondary : server; const devices=[server,secondary];
  return { target, devices, health:target.proactive_health, status:{overall:'healthy',checked_at:now(),updated_at:now(),device:{name:'Pocket Lab Lite Server',mode:'lite',resource_profile:'low-power',device_facts:serverFacts},device_facts:serverFacts,resource_observations:serverFacts.resources,summary:{apps_available:1,devices_known:2,device_health_attention:offline?1:0,device_health_attention_current:!offline,device_health_summary:{by_status:{healthy:offline?1:2,degraded:offline?1:0},by_severity:{}},security_findings:0,nats_connected:true,jetstream_enabled:true,live_sampler_running:true,remote_access_ready:true},telemetry:{status:'healthy',sampled_at:serverFacts.observed_at,resource_observations:serverFacts.resources,memory_total_mb:4096,memory_free_mb:2048,cpu_usage_percent:12,cpu_temp_c:42,total_space_mb:256000,free_space_mb:128000},services:[{name:'Control API',status:'healthy',summary:'Workspace services are ready.'},{name:'Remote Access',status:'healthy',summary:'Private remote access is ready.'}],system_current_state:{},projection_only:true,sanitized:true} };
}

export function deviceFactsScenarioHandlers(scenario='') {
  if (!DEVICE_FACT_SCENARIOS.has(String(scenario))) return [];
  const state=buildDeviceFactsScenario(String(scenario)); const find=id=>state.devices.find(d=>d.id===String(id||''))||state.target;
  return [
    http.get('/api/lite/status',()=>HttpResponse.json(state.status)),
    http.get('/api/lite/fleet',()=>HttpResponse.json({status:'healthy',devices:state.devices,count:state.devices.length,source_revision:2,sanitized:true})),
    http.get('/api/lite/devices/:deviceId',({params})=>HttpResponse.json({status:'ready',device:find(params.deviceId),source_revision:2,sanitized:true})),
    http.get('/api/lite/devices/:deviceId/health',({params})=>{const d=find(params.deviceId),h=d.proactive_health;return HttpResponse.json({status:'ready',health:h,device_facts:d.device_facts,resource_observations:d.device_facts.resources,capability_states:d.capability_states||[],runtime_services:d.runtime_services||[],software_posture:h.software_posture||{},source_revision:2,sanitized:true});}),
    http.get('/api/lite/devices/:deviceId/history',()=>HttpResponse.json({status:'ready',items:[],total_count:0,sanitized:true})),
    http.get('/api/lite/devices/:deviceId/health/history',()=>HttpResponse.json({status:'ready',items:[],total_count:0,sanitized:true})),
  ];
}
