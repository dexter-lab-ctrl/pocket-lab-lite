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
