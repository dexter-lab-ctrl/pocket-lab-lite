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

    object?.addEventListener('load', replay, { once: true });
    if (object?.contentDocument) replay();
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();
