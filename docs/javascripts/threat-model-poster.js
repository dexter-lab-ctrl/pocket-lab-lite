(() => {
  const ROOT = '[data-pl-threat-poster="true"]';
  const SVG = '#pl-threat-model-svg';
  const CATALOG_ONLY = ['boundary', 'threat', 'evidence', 'posture'];

  const svgRoot = (root) => root.querySelector(SVG)?.contentDocument?.documentElement || null;
  const svgAll = (root, selector) => Array.from(root.querySelector(SVG)?.contentDocument?.querySelectorAll(selector) || []);

  const catalogOnlySelection = () => {
    const url = new URL(window.location.href);
    for (const kind of CATALOG_ONLY) {
      const target = url.searchParams.get(`atlas-${kind}`);
      if (target) return { kind, target };
    }
    const raw = url.hash.replace(/^#/, '');
    if (!raw.includes('=')) return null;
    const params = new URLSearchParams(raw);
    for (const kind of CATALOG_ONLY) {
      const target = params.get(kind);
      if (target) return { kind, target };
    }
    return null;
  };

  const forwardCatalogOnlySelection = () => {
    const selected = catalogOnlySelection();
    if (!selected) return false;
    const url = new URL('catalog/', window.location.href);
    url.searchParams.set(`atlas-${selected.kind}`, selected.target);
    url.hash = '#security-atlas';
    window.location.replace(url);
    return true;
  };

  const setPressed = (buttons, selected, dataKey) => {
    buttons.forEach((button) => {
      const active = button.dataset[dataKey] === selected;
      button.setAttribute('aria-pressed', String(active));
      button.classList.toggle('md-button--primary', active);
    });
  };

  const applyMode = (root, mode) => {
    const svg = svgRoot(root);
    if (!svg) return;
    ['understand', 'threats', 'controls'].forEach((name) => svg.classList.toggle(`mode-${name}`, name === mode));
    svg.dataset.posterMode = mode;
  };

  const applyStride = (root, stride) => {
    const svg = svgRoot(root);
    if (!svg) return;
    svg.dataset.strideLens = stride;
    svgAll(root, '.node,.control,.attack').forEach((element) => {
      const values = (element.dataset.stride || '').split(/\s{2,}|\|/).filter(Boolean);
      const raw = element.dataset.stride || '';
      const matches = stride === 'all' || values.includes(stride) || raw.includes(stride);
      element.classList.toggle('is-filtered-out', !matches);
    });
  };

  const enhance = () => {
    const root = document.querySelector(ROOT);
    if (!root || root.dataset.plPosterBound === 'true') return;
    root.dataset.plPosterBound = 'true';
    if (forwardCatalogOnlySelection()) return;

    const object = root.querySelector(SVG);
    const modeButtons = Array.from(root.querySelectorAll('[data-threat-poster-mode]'));
    const strideButtons = Array.from(root.querySelectorAll('[data-stride-lens]'));
    const guardrail = root.querySelector('[data-threat-guardrails="toggle"]');
    let mode = 'understand';
    let stride = 'all';

    const replay = () => {
      applyMode(root, mode);
      applyStride(root, stride);
      const svg = svgRoot(root);
      if (svg && guardrail) svg.classList.toggle('show-guardrails', guardrail.getAttribute('aria-pressed') === 'true');
    };

    modeButtons.forEach((button) => button.addEventListener('click', () => {
      mode = button.dataset.threatPosterMode || 'understand';
      setPressed(modeButtons, mode, 'threatPosterMode');
      applyMode(root, mode);
    }));

    strideButtons.forEach((button) => button.addEventListener('click', () => {
      stride = button.dataset.strideLens || 'all';
      setPressed(strideButtons, stride, 'strideLens');
      applyStride(root, stride);
    }));

    guardrail?.addEventListener('click', () => {
      const active = guardrail.getAttribute('aria-pressed') !== 'true';
      guardrail.setAttribute('aria-pressed', String(active));
      guardrail.textContent = active ? 'Hide guardrails' : 'Show guardrails';
      svgRoot(root)?.classList.toggle('show-guardrails', active);
    });

    object?.addEventListener('load', replay);
    if (object?.contentDocument) replay();
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();

/* Enterprise Threat Model console. It reads only the deterministic, generated
 * projection embedded in the page; no timers, polling, network access or runtime I/O. */
(() => {
  const ROOT = '[data-pl-security-console="true"]';
  const SVG = '#pl-threat-model-svg';
  const KEYS = ['security-lens', 'security-stride', 'security-entity', 'security-story', 'security-step', 'security-blast', 'security-isolate', 'security-gaps', 'security-compare', 'security-view'];
  const onPage = () => document.querySelector(ROOT);
  const text = (tag, value, className = '') => { const el = document.createElement(tag); el.textContent = value; if (className) el.className = className; return el; };
  const objectDocument = () => document.querySelector(SVG)?.contentDocument || null;
  const all = (selector) => Array.from(objectDocument()?.querySelectorAll(selector) || []);
  const data = () => { try { return JSON.parse(document.querySelector('#pl-threat-enterprise-data')?.textContent || '{}'); } catch (_) { return {}; } };
  const stateFromUrl = () => {
    const url = new URL(window.location.href);
    return {
      lens: url.searchParams.get('security-lens') || 'architecture', stride: url.searchParams.get('security-stride') || 'all',
      selected: url.searchParams.get('security-entity') || (url.searchParams.get('atlas-system') ? `system:${url.searchParams.get('atlas-system')}` : '') || (url.searchParams.get('atlas-control') ? `control:${url.searchParams.get('atlas-control')}` : '') || (url.searchParams.get('atlas-boundary') ? `boundary:${url.searchParams.get('atlas-boundary')}` : '') || (url.searchParams.get('atlas-attack-path') ? `path:${url.searchParams.get('atlas-attack-path')}` : ''), story: url.searchParams.get('security-story') || url.searchParams.get('atlas-attack-path') || '',
      step: Number(url.searchParams.get('security-step') || 0), blast: url.searchParams.get('security-blast') === '1',
      isolate: url.searchParams.get('security-isolate') === '1', gaps: url.searchParams.get('security-gaps') === '1',
      compare: url.searchParams.get('security-compare') || '', view: url.searchParams.get('security-view') || 'executive', workspace: false, coverage: false,
    };
  };
  const writeUrl = (state) => {
    const url = new URL(window.location.href); KEYS.forEach((key) => url.searchParams.delete(key));
    const values = { 'security-lens': state.lens, 'security-stride': state.stride, 'security-entity': state.selected, 'security-story': state.story, 'security-step': state.story ? state.step : '', 'security-blast': state.blast ? '1' : '', 'security-isolate': state.isolate ? '1' : '', 'security-gaps': state.gaps ? '1' : '', 'security-compare': state.compare, 'security-view': state.view };
    Object.entries(values).forEach(([key, value]) => { if (value && value !== 'all' && value !== 'executive') url.searchParams.set(key, value); });
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  };
  const pathFor = (model, id) => (model.story_paths || []).find((row) => row.id === id);
  const entity = (model, id) => {
    if (!id) return null;
    const [kind, key] = id.split(':', 2);
    if (kind === 'path') return { kind, row: pathFor(model, key) };
    if (kind === 'control') return { kind, row: (model.control_interceptions || []).find((row) => row.control === key) };
    if (kind === 'boundary') return { kind, row: (model.boundary_summaries || []).find((row) => row.id === key) };
    if (kind === 'evidence') return { kind, row: (model.evidence_lineage || []).find((row) => row.id === key) };
    return { kind: 'system', row: (model.blast_radius || []).find((row) => row.entity === key) };
  };
  const button = (label, action, value = '') => { const el = text('button', label); el.type = 'button'; el.dataset.plEnterprisePick = action; el.dataset.plEnterpriseValue = value; return el; };
  const selectedNodes = (model, state) => {
    const item = entity(model, state.selected); if (!item?.row) return [];
    if (item.kind === 'path') return (item.row.stages || []).flatMap((stage) => [stage.source, stage.destination]);
    if (item.kind === 'system') return item.row.selected || [];
    if (item.kind === 'boundary') return item.row.members || [];
    return [];
  };
  const applyDiagram = (root, model, state) => {
    const doc = objectDocument(); if (!doc) return;
    all('.node,.control,.flow,.attack').forEach((el) => el.classList.remove('enterprise-muted', 'enterprise-focus', 'enterprise-direct', 'enterprise-transitive', 'enterprise-gap', 'enterprise-stage', 'enterprise-isolated', 'enterprise-consequence', 'enterprise-story-past', 'enterprise-story-future'));
    const focused = new Set(selectedNodes(model, state));
    const blast = state.blast ? (model.blast_radius || []).find((row) => row.subject === state.selected || (state.selected === `system:${row.entity}`)) : null;
    const isolated = state.isolate && entity(model, state.selected)?.kind === 'boundary' ? entity(model, state.selected).row : null;
    if (state.lens === 'attack-paths' || state.story) all('.node,.control,.flow').forEach((el) => el.classList.add('enterprise-muted'));
    if (state.lens === 'controls') all('.flow').forEach((el) => el.classList.add('enterprise-muted'));
    if (state.lens === 'evidence') all('.flow').forEach((el) => el.classList.add('enterprise-muted'));
    if (state.gaps) all('.node,.control,.flow').forEach((el) => el.classList.add('enterprise-muted'));
    if (state.stride !== 'all') all('.node,.control,.attack').forEach((el) => {
      const raw = el.dataset.stride || '';
      if (!raw.includes(state.stride)) el.classList.add('enterprise-muted');
    });
    all('.node').forEach((el) => {
      if (focused.has(el.dataset.node)) el.classList.add('enterprise-focus');
      if (blast?.direct?.includes(el.dataset.node)) el.classList.add('enterprise-direct');
      if (blast?.transitive?.includes(el.dataset.node)) el.classList.add('enterprise-transitive');
      if (isolated?.members?.includes(el.dataset.node)) el.classList.add('enterprise-isolated');
      if (state.gaps && ['control-partial', 'evidence-stale', 'control-unvalidated'].includes(el.dataset.state)) el.classList.add('enterprise-gap');
    });
    if (isolated) all('.node').filter((el) => !isolated.members.includes(el.dataset.node)).forEach((el) => el.classList.add('enterprise-muted'));
    const story = pathFor(model, state.story);
    all('.attack').forEach((el) => {
      if (!story || el.dataset.attackPath !== story.id) return;
      const stage = Number(el.dataset.stage || 1); const current = state.step + 1;
      el.classList.add(stage === current ? 'enterprise-stage' : stage < current ? 'enterprise-story-past' : 'enterprise-story-future');
    });
    all('.control').forEach((el) => {
      if (state.selected === `control:${el.dataset.control}`) el.classList.add('enterprise-focus');
      if (state.gaps && ['control-partial', 'evidence-stale', 'control-unvalidated'].includes(el.dataset.state)) el.classList.add('enterprise-gap');
      if (story?.stages?.[state.step]?.controls?.includes(el.dataset.control)) el.classList.add('enterprise-stage');
    });
  };
  const summary = (root, model, state) => {
    const panel = root.querySelector('.pl-security-summary'); panel.replaceChildren();
    const title = text('h3', state.lens.replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())); panel.append(title);
    const description = { architecture: 'Canonical components, allowed flows and trust-boundary ownership remain the map.', 'trust-boundaries': 'Select a saved boundary to isolate its ingress, egress, controls, STRIDE candidates and evidence posture.', 'attack-paths': 'Choose a source-derived modeled path. Story steps explain saved relationships, never an active attack.', stride: 'Use the full named STRIDE filter. Color is supplemental to visible labels and selection.', controls: 'Control gates show modeled interception and canonical evidence state; prevention is never implied without evidence.', evidence: 'Confidence markers distinguish observed, source-derived, partial or stale, and unvalidated saved evidence.', consequences: 'Modeled consequence projection only. This is not live compromise or exploitability.' }[state.lens] || model.truth;
    panel.append(text('p', description));
    const list = document.createElement('div'); list.className = 'pl-security-choice-list';
    if (state.lens === 'attack-paths') (model.story_paths || []).forEach((row) => list.append(button(`${row.id} · ${row.name}`, 'path', row.id)));
    else if (state.lens === 'trust-boundaries') (model.boundary_summaries || []).forEach((row) => list.append(button(`${row.label} · ${row.evidence.symbol} ${row.evidence.label}`, 'boundary', row.id)));
    else if (state.lens === 'controls') [...new Set((model.control_interceptions || []).map((row) => row.control))].forEach((id) => list.append(button(id, 'control', id)));
    else if (state.lens === 'evidence') { (model.evidence_states || []).forEach((row) => list.append(text('span', `${row.symbol} ${row.label}`, 'pl-security-evidence-state'))); (model.evidence_lineage || []).forEach((row) => list.append(button(`${row.label} · ${row.source}`, 'evidence', row.id))); }
    else if (state.lens === 'consequences') (model.story_paths || []).forEach((row) => list.append(text('span', `${row.id}: ${row.stages?.at(-1)?.consequences?.join('; ') || 'No modeled consequence.'}`)));
    else (model.boundary_summaries || []).forEach((row) => list.append(button(`${row.label} · ${row.members.length} systems`, 'boundary', row.id)));
    panel.append(list);
    if (state.lens === 'controls' && state.coverage) {
      const coverage = document.createElement('div'); coverage.className = 'pl-security-coverage'; coverage.append(text('h4', 'Modeled control coverage'));
      (model.control_coverage || []).forEach((row) => coverage.append(text('p', `${row.label}: ${row.markers} · ${Object.entries(row.counts).map(([key, value]) => `${key} ${value}`).join(', ') || 'no modeled controls'}. ${row.truth}`)));
      panel.append(coverage);
    }
    if (state.gaps) {
      const gaps = document.createElement('div'); gaps.className = 'pl-security-gaps'; gaps.append(text('h4', 'Evidence-gap summary'));
      (model.evidence_gaps || []).forEach((row) => gaps.append(text('p', `${row.state.symbol} ${row.state.label}: ${row.kind} ${row.id}; affected boundaries: ${row.boundaries.join(', ') || 'unvalidated'}.`)));
      const affectedPaths = (model.story_paths || []).filter((path) => (path.stages || []).some((stage) => (model.evidence_gaps || []).some((gap) => gap.boundaries.includes(stage.boundary)))).map((path) => path.id);
      gaps.append(text('p', `Affected modeled attack paths: ${affectedPaths.join(', ') || 'none mapped'}. Gaps are not vulnerabilities.`)); panel.append(gaps);
    }
  };
  const detail = (root, model, state) => {
    const panel = root.querySelector('.pl-security-detail'); const item = entity(model, state.selected); panel.replaceChildren();
    panel.append(text('span', 'Saved model detail', 'pl-card-kicker'));
    if (!item?.row) { panel.append(text('p', 'Select a system, control, boundary or modeled attack path. Local interactions never retrieve runtime data.')); return; }
    if (item.kind === 'system') { panel.append(text('h3', item.row.entity)); panel.append(text('p', `Modeled blast radius: ${item.row.direct.length} directly affected and ${item.row.transitive.length} transitively affected components.`)); panel.append(text('p', item.row.truth)); }
    if (item.kind === 'boundary') { panel.append(text('h3', item.row.label)); panel.append(text('p', `Ingress: ${item.row.ingress.join(', ') || 'none modeled'}; egress: ${item.row.egress.join(', ') || 'none modeled'}.`)); panel.append(text('p', `Controls: ${item.row.controls.join(', ') || 'none modeled'}. STRIDE: ${item.row.stride.join(', ') || 'none modeled'}.`)); }
    if (item.kind === 'control') { panel.append(text('h3', item.row.control)); panel.append(text('p', `${item.row.status.symbol} ${item.row.status.label} · boundary ${item.row.boundary}.`)); panel.append(text('p', `Threats mitigated: ${item.row.threats.join(', ') || 'source-derived control scope'}.`)); panel.append(text('p', `Effect: ${item.row.effect}. Prevention claim: ${item.row.prevention_claim ? 'supported' : 'not claimed'}.`)); panel.append(text('p', `Failure consequence: ${item.row.failure_consequences.join('; ') || 'Human review required.'}`)); panel.append(text('p', `Source references: ${item.row.source_refs.join(', ') || 'No additional source reference projected.'}`)); }
    if (item.kind === 'path') { panel.append(text('h3', `${item.row.id} · ${item.row.name}`)); panel.append(text('p', `${item.row.evidence.symbol} ${item.row.evidence.label}. ${item.row.review_status}.`)); panel.append(text('p', 'Use Start to enter the controlled explanatory choreography.')); }
    if (item.kind === 'evidence') { panel.append(text('h3', item.row.label)); panel.append(text('p', `Canonical lineage source: ${item.row.source}.`)); panel.append(text('p', 'This is saved provenance. It does not retrieve runtime, operational or supply-chain evidence.')); }
    const blast = (model.blast_radius || []).find((row) => row.subject === state.selected || (state.selected === `system:${row.entity}`));
    if (state.blast && blast) panel.append(text('p', `Blast scope: flows ${blast.flows.length}; boundaries ${blast.boundaries.join(', ') || 'none'}; controls ${blast.controls.join(', ') || 'none'}; paths ${blast.attack_paths.join(', ') || 'none'}. ${blast.truth}`));
    if (item.kind === 'system') { const navigation = (model.architecture_navigation || []).find((row) => row.system === item.row.entity); if (navigation) { const link = document.createElement('a'); link.href = navigation.href; link.className = 'pl-intent-link'; link.textContent = `Open canonical architecture component · ${navigation.architecture_component} →`; panel.append(link); } }
  };
  const story = (root, model, state) => {
    const box = root.querySelector('.pl-security-story'); const path = pathFor(model, state.story); box.hidden = !path;
    if (!path) return; state.step = Math.max(0, Math.min(state.step, path.stages.length - 1)); const stage = path.stages[state.step];
    const output = box.querySelector('.pl-security-story-stage'); output.replaceChildren(text('strong', `Stage ${state.step + 1} of ${path.stages.length} · ${stage.title}`), text('p', `${stage.source} → ${stage.destination}; boundary: ${stage.boundary}.`), text('p', `Threat class: ${stage.stride.join(', ') || 'Unvalidated'}. Controls: ${stage.controls.join(', ') || 'No mapped control'}.`), text('p', `${stage.evidence.symbol} ${stage.evidence.label}. ${stage.truth}`), text('p', `Modeled consequence: ${stage.consequences.join('; ') || 'No modeled consequence recorded.'}`));
  };
  const compare = (root, model, state) => {
    const detailPanel = root.querySelector('.pl-security-detail'); if (!state.compare) return;
    detailPanel.append(text('h4', 'Modeled Scenario Comparison'), text('p', `${model.scenario_comparison.baseline} vs ${state.compare} unavailable.`), text('p', model.scenario_comparison.truth));
  };
  const render = (root, model, state) => {
    root.dataset.securityView = state.view; root.dataset.securityLens = state.lens;
    root.querySelectorAll('[data-pl-security-lens]').forEach((el) => { const active = el.dataset.plSecurityLens === state.lens; el.setAttribute('aria-selected', String(active)); el.tabIndex = active ? 0 : -1; });
    root.querySelectorAll('[data-pl-enterprise-stride]').forEach((el) => el.setAttribute('aria-pressed', String(el.dataset.plEnterpriseStride === state.stride)));
    root.querySelectorAll('[data-pl-security-view]').forEach((el) => el.setAttribute('aria-pressed', String(el.dataset.plSecurityView === state.view)));
    [['blast', state.blast], ['isolate', state.isolate], ['gaps', state.gaps], ['coverage', state.coverage], ['compare', Boolean(state.compare)]].forEach(([action, active]) => root.querySelector(`[data-pl-security-action="${action}"]`)?.setAttribute('aria-pressed', String(active)));
    root.querySelector('[data-pl-security-action="workspace"]')?.setAttribute('aria-expanded', String(state.workspace));
    root.querySelector('.pl-security-workspace').hidden = !state.workspace; summary(root, model, state); detail(root, model, state); story(root, model, state); compare(root, model, state); applyDiagram(root, model, state); writeUrl(state);
  };
  const bindSvg = (root, model, state) => {
    const object = document.querySelector(SVG); const attach = () => { const doc = object?.contentDocument; if (!doc || doc.documentElement.dataset.plEnterpriseBound) return; doc.documentElement.dataset.plEnterpriseBound = 'true';
      const select = (target) => { if (target.classList.contains('node')) state.selected = `system:${target.dataset.node}`; if (target.classList.contains('control')) state.selected = `control:${target.dataset.control}`; if (target.classList.contains('attack')) { state.selected = `path:${target.dataset.attackPath}`; state.story = target.dataset.attackPath; state.step = 0; } render(root, model, state); };
      doc.addEventListener('click', (event) => { const target = event.target?.closest?.('.node,.control,.attack'); if (target) select(target); });
      doc.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { const target = event.target?.closest?.('.node,.control,.attack'); if (target) select(target); } }); };
    object?.addEventListener('load', attach); attach();
  };
  const enhance = () => {
    const root = onPage(); if (!root || root.dataset.plSecurityConsoleBound) return; root.dataset.plSecurityConsoleBound = 'true'; const model = data(); const state = stateFromUrl();
    const reviewKey = `pocket-lab-threat-review:${window.location.pathname}`;
    let review = {}; try { review = JSON.parse(sessionStorage.getItem(reviewKey) || '{}'); } catch (_) { review = {}; }
    root.querySelectorAll('[data-pl-review]').forEach((input) => { input.value = review[input.dataset.plReview] || ''; input.addEventListener('input', () => { review[input.dataset.plReview] = input.value; try { sessionStorage.setItem(reviewKey, JSON.stringify(review)); } catch (_) { /* local persistence is optional */ } }); });
    root.addEventListener('click', (event) => { const target = event.target?.closest?.('button'); if (!target) return;
      if (target.dataset.plSecurityLens) state.lens = target.dataset.plSecurityLens;
      if (target.dataset.plEnterpriseStride) state.stride = target.dataset.plEnterpriseStride;
      if (target.dataset.plSecurityView) state.view = target.dataset.plSecurityView;
      if (target.dataset.plEnterprisePick) { const value = target.dataset.plEnterpriseValue; state.selected = `${target.dataset.plEnterprisePick}:${value}`; if (target.dataset.plEnterprisePick === 'path') { state.story = value; state.step = 0; } }
      const action = target.dataset.plSecurityAction; if (action === 'blast') state.blast = !state.blast; if (action === 'isolate') state.isolate = !state.isolate; if (action === 'gaps') { state.gaps = !state.gaps; state.lens = 'evidence'; } if (action === 'coverage') { state.lens = 'controls'; state.coverage = !state.coverage; } if (action === 'compare') { const control = entity(model, state.selected)?.kind === 'control' ? entity(model, state.selected).row.control : model.control_interceptions?.[0]?.control; state.compare = state.compare ? '' : control || ''; } if (action === 'workspace') state.workspace = !state.workspace; if (action === 'share') navigator.clipboard?.writeText(window.location.href);
      const control = target.dataset.plStory; if (control === 'start') { const path = state.story || model.story_paths?.[0]?.id; state.story = path || ''; state.step = 0; } if (control === 'previous') state.step -= 1; if (control === 'next') state.step += 1; if (control === 'replay') state.step = 0; if (control === 'exit') { state.story = ''; state.step = 0; } render(root, model, state); });
    root.querySelector('[role="tablist"]')?.addEventListener('keydown', (event) => { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; const buttons = Array.from(root.querySelectorAll('[data-pl-security-lens]')); const index = buttons.indexOf(document.activeElement); const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : buttons.length - 1)) % buttons.length; event.preventDefault(); buttons[next].focus(); buttons[next].click(); });
    bindSvg(root, model, state); render(root, model, state);
  };
  if (typeof document$ !== 'undefined') document$.subscribe(enhance); else document.addEventListener('DOMContentLoaded', enhance);
})();

/* Threat Model polish: deterministic responsive asset selection, explicit state affordances,
 * visual legends, and dismissible focus. No polling, observers, animation loops, or runtime I/O. */
(() => {
  const ROOT = '[data-pl-threat-poster="true"]';
  const MOBILE = '(max-width: 44.9844em)';
  const SEMANTIC_KEYS = ['attack-path', 'control', 'system'];

  const responsiveSrc = (value, mobile) => {
    if (!value || !value.endsWith('.svg')) return value;
    const base = value.replace(/-mobile\.svg$/, '.svg');
    return mobile ? base.replace(/\.svg$/, '-mobile.svg') : base;
  };

  const chooseResponsiveAssets = () => {
    const mobile = Boolean(window.matchMedia?.(MOBILE).matches);
    document.querySelectorAll('object#pl-threat-model-svg').forEach((object) => {
      const original = object.dataset.plBaseSrc || object.getAttribute('data') || '';
      object.dataset.plBaseSrc = original.replace(/-mobile\.svg$/, '.svg');
      const next = responsiveSrc(object.dataset.plBaseSrc, mobile);
      object.dataset.plLayout = mobile ? 'stacked' : 'wide';
      if (next && next !== object.getAttribute('data')) object.setAttribute('data', next);
      const fallback = object.querySelector('img');
      if (fallback) {
        const fallbackBase = fallback.dataset.plBaseSrc || fallback.getAttribute('src') || '';
        fallback.dataset.plBaseSrc = fallbackBase.replace(/-mobile\.svg$/, '.svg');
        fallback.setAttribute('src', responsiveSrc(fallback.dataset.plBaseSrc, mobile));
      }
    });
  };

  const legendMarkup = () => {
    const legend = document.createElement('div');
    legend.className = 'pl-threat-legend';
    legend.setAttribute('role', 'list');
    legend.setAttribute('aria-label', 'Threat Model diagram legend');
    const items = [
      ['flow', 'Modeled allowed/control flow'],
      ['attack', 'Selected modeled attack path'],
      ['shield', 'Security control'],
      ['zone', 'Trust zone / boundary'],
      ['motion', 'Motion explains a saved relationship only'],
    ];
    items.forEach(([kind, label]) => {
      const item = document.createElement('span');
      item.className = 'pl-threat-legend-item';
      item.setAttribute('role', 'listitem');
      const symbol = document.createElement('i');
      symbol.className = `pl-threat-legend-symbol pl-threat-legend-symbol--${kind}`;
      symbol.setAttribute('aria-hidden', 'true');
      const text = document.createElement('span');
      text.textContent = label;
      item.append(symbol, text);
      legend.append(item);
    });
    const note = document.createElement('strong');
    note.className = 'pl-threat-legend-note';
    note.textContent = 'Static saved model · never live traffic';
    legend.append(note);
    return legend;
  };

  const enhanceLegends = () => {
    document.querySelectorAll('.pl-threat-poster-canvas,.pl-threat-canvas').forEach((canvas) => {
      if (canvas.querySelector(':scope > .pl-threat-legend')) return;
      const prose = canvas.querySelector(':scope > p');
      prose?.replaceWith(legendMarkup());
    });
    document.querySelectorAll('.pl-threat-detail-diagram,.pl-security-atlas-poster').forEach((figure) => {
      if (figure.nextElementSibling?.classList.contains('pl-threat-legend')) return;
      figure.insertAdjacentElement('afterend', legendMarkup());
    });
  };

  const syncButtonState = (root) => {
    root.querySelectorAll('[data-threat-poster-mode],[data-stride-lens]').forEach((button) => {
      const selected = button.getAttribute('aria-pressed') === 'true';
      button.dataset.selected = String(selected);
      button.classList.toggle('pl-is-selected', selected);
    });
  };

  const svgDocument = (root) => root.querySelector('#pl-threat-model-svg')?.contentDocument || null;
  const svgAll = (root, selector) => Array.from(svgDocument(root)?.querySelectorAll(selector) || []);

  const clearSemanticUrl = () => {
    const url = new URL(window.location.href);
    SEMANTIC_KEYS.forEach((key) => url.searchParams.delete(`atlas-${key}`));
    if (url.hash.includes('=')) url.hash = '#security-atlas';
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const resetPosterFocus = (root) => {
    svgAll(root, '.node,.flow,.control').forEach((element) => element.classList.remove('is-active', 'is-muted'));
    svgAll(root, '.attack').forEach((element) => element.classList.remove('is-active'));
    clearSemanticUrl();
    const detail = root.querySelector('#threat-selection');
    if (detail) {
      detail.replaceChildren();
      const kicker = document.createElement('span');
      kicker.className = 'pl-card-kicker';
      kicker.textContent = 'Select the poster';
      const strong = document.createElement('strong');
      strong.textContent = 'Start with the architecture story';
      const p = document.createElement('p');
      p.textContent = 'Choose a component or shield to focus the saved model. Click empty diagram space or press Escape to clear focus.';
      detail.append(kicker, strong, p);
    }
    root.dataset.focused = 'false';
  };

  const bindSvgReset = (root) => {
    const object = root.querySelector('#pl-threat-model-svg');
    const bind = () => {
      const doc = object?.contentDocument;
      if (!doc || doc.documentElement.dataset.plResetBound === 'true') return;
      doc.documentElement.dataset.plResetBound = 'true';
      const onDiagramPointer = (event) => {
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if (target.closest('.node,.control')) {
          root.dataset.focused = 'true';
          return;
        }
        if (target.closest('[data-reset-target="true"],.bg,.grid') || target === doc.documentElement) {
          resetPosterFocus(root);
        }
      };
      doc.documentElement.addEventListener('pointerdown', onDiagramPointer);
      doc.documentElement.addEventListener('click', onDiagramPointer);
      doc.documentElement.addEventListener('keydown', (event) => {
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if ((event.key === 'Enter' || event.key === ' ') && target.closest('.node,.control')) {
          root.dataset.focused = 'true';
        }
      });
    };
    object?.addEventListener('load', bind);
    bind();
  };

  const enhance = () => {
    chooseResponsiveAssets();
    enhanceLegends();
    const media = window.matchMedia?.(MOBILE);
    if (media && document.documentElement.dataset.plThreatMediaBound !== 'true') {
      document.documentElement.dataset.plThreatMediaBound = 'true';
      media.addEventListener?.('change', chooseResponsiveAssets);
    }
    const root = document.querySelector(ROOT);
    if (!root || root.dataset.plPolishBound === 'true') return;
    root.dataset.plPolishBound = 'true';
    syncButtonState(root);
    root.querySelectorAll('[data-threat-poster-mode],[data-stride-lens]').forEach((button) => {
      button.addEventListener('click', () => syncButtonState(root));
    });
    bindSvgReset(root);
    if (!window.__plThreatPosterPolishNavigationBound) {
      window.__plThreatPosterPolishNavigationBound = true;
      document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        const current = document.querySelector(ROOT);
        if (current) resetPosterFocus(current);
      });
      document.addEventListener('pointerdown', (event) => {
        const current = document.querySelector(ROOT);
        if (!current || current.dataset.focused !== 'true') return;
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if (target.closest(ROOT) || target.closest('[data-catalog-id],[data-attack-path-id]')) return;
        resetPosterFocus(current);
      });
    }
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();

/* Fullscreen Security Architecture Poster.
 * Desktop uses the native target=_blank link; mobile keeps the user on the same
 * page. The query-param view in the new desktop tab enters the same local overlay.
 */
(() => {
  const ROOT = '[data-pl-threat-poster="true"]';
  const MOBILE = '(max-width: 44.9844em)';
  const QUERY = 'poster-fullscreen';
  let previousFocus = null;

  const setFullscreen = (root, active) => {
    if (!root) return;
    root.classList.toggle('is-fullscreen', active);
    document.documentElement.dataset.plThreatFullscreen = String(active);
    if (active) {
      previousFocus = document.activeElement;
      root.setAttribute('role', 'dialog');
      root.setAttribute('aria-modal', 'true');
      root.setAttribute('aria-label', 'Pocket Lab Lite Security Architecture Poster full screen');
      root.querySelector('[data-threat-fullscreen="close"]')?.focus();
    } else {
      root.removeAttribute('role');
      root.removeAttribute('aria-modal');
      root.removeAttribute('aria-label');
      previousFocus?.focus?.();
    }
  };

  const closeFullscreen = (root) => {
    const url = new URL(window.location.href);
    const standalone = url.searchParams.get(QUERY) === '1';
    if (standalone && !window.matchMedia?.(MOBILE).matches) window.close();
    url.searchParams.delete(QUERY);
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
    setFullscreen(root, false);
  };

  const enhance = () => {
    const root = document.querySelector(ROOT);
    if (!root || root.dataset.plFullscreenBound === 'true') return;
    root.dataset.plFullscreenBound = 'true';
    const open = root.querySelector('[data-threat-fullscreen="open"]');
    if (!open) return;

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'md-button pl-threat-fullscreen-close';
    close.dataset.threatFullscreen = 'close';
    close.textContent = 'Close ×';
    close.addEventListener('click', () => closeFullscreen(root));
    root.querySelector('.pl-threat-poster-head')?.append(close);

    open.addEventListener('click', (event) => {
      if (!window.matchMedia?.(MOBILE).matches) return;
      event.preventDefault();
      setFullscreen(root, true);
    });

    const url = new URL(window.location.href);
    if (url.searchParams.get(QUERY) === '1') setFullscreen(root, true);
  };

  if (!window.__plThreatFullscreenEscapeBound) {
    window.__plThreatFullscreenEscapeBound = true;
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      const root = document.querySelector(`${ROOT}.is-fullscreen`);
      if (root) closeFullscreen(root);
    });
  }

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();


/* Threat Model fullscreen routing guard.
 * Desktop always opens a new named tab; mobile/touch keeps the existing in-page overlay.
 * This corrects viewport-only classification without adding polling or runtime I/O.
 */
(() => {
  const ROOT = '[data-pl-threat-poster="true"]';
  const OPEN = '[data-threat-fullscreen="open"]';
  const CLOSE = '[data-threat-fullscreen="close"]';
  const MOBILE_WIDTH = '(max-width: 44.9844em)';
  const COARSE_POINTER = '(pointer: coarse)';
  const QUERY = 'poster-fullscreen';
  const POPUP_PREFIX = 'pocketlab-threat-poster-';
  let popupSequence = 0;

  const isMobilePresentation = () => (
    Boolean(window.matchMedia?.(MOBILE_WIDTH).matches)
    && (
      Number(navigator.maxTouchPoints || 0) > 0
      || Boolean(window.matchMedia?.(COARSE_POINTER).matches)
    )
  );

  const isDesktopPosterPopup = () => window.name.startsWith(POPUP_PREFIX);

  const updateOpenLabel = () => {
    const open = document.querySelector(OPEN);
    if (!open) return;
    open.textContent = isMobilePresentation() ? 'Full screen' : 'Open in new tab';
    open.setAttribute(
      'aria-label',
      isMobilePresentation()
        ? 'View Security Architecture Poster full screen'
        : 'Open Security Architecture Poster full screen in a new tab',
    );
  };

  const cancelSameTabDesktopFullscreen = () => {
    if (isMobilePresentation() || isDesktopPosterPopup()) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get(QUERY) !== '1') return;
    const root = document.querySelector(ROOT);
    root?.classList.remove('is-fullscreen');
    root?.removeAttribute('role');
    root?.removeAttribute('aria-modal');
    root?.removeAttribute('aria-label');
    document.documentElement.dataset.plThreatFullscreen = 'false';
    url.searchParams.delete(QUERY);
    window.history.replaceState(
      window.history.state,
      '',
      `${url.pathname}${url.search}${url.hash}`,
    );
  };

  const openDesktopPoster = (link) => {
    popupSequence += 1;
    const name = `${POPUP_PREFIX}${Date.now()}-${popupSequence}`;
    window.open(link.href, name, 'noopener,noreferrer');
  };

  if (!window.__plThreatFullscreenRoutingBound) {
    window.__plThreatFullscreenRoutingBound = true;
    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!target || typeof target.closest !== 'function') return;
      const close = target.closest(CLOSE);
      if (close && !isMobilePresentation() && isDesktopPosterPopup()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.close();
        return;
      }
      const open = target.closest(OPEN);
      if (!open || isMobilePresentation()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      openDesktopPoster(open);
    }, true);

    const media = window.matchMedia?.(MOBILE_WIDTH);
    media?.addEventListener?.('change', updateOpenLabel);
  }

  const enhance = () => {
    updateOpenLabel();
    cancelSameTabDesktopFullscreen();
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();
