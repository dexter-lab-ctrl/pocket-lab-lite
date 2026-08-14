(() => {
  const rootSelector = '#pl-threat-model-svg';
  const DEEP_LINK_KEYS = ['attack-path', 'control', 'system', 'boundary', 'threat', 'evidence', 'posture'];

  const detail = (title, body, meta = '') => {
    const panel = document.querySelector('#threat-selection');
    if (!panel) return;
    panel.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = title;
    panel.append(strong);
    const p = document.createElement('p');
    p.textContent = body;
    panel.append(p);
    if (meta) {
      const code = document.createElement('code');
      code.textContent = meta;
      panel.append(code);
    }
  };

  const svgDocument = () => document.querySelector(rootSelector)?.contentDocument || null;
  const svgRoot = () => svgDocument()?.documentElement || null;
  const all = (selector) => Array.from(svgDocument()?.querySelectorAll(selector) || []);
  const catalogCards = () => Array.from(document.querySelectorAll('[data-catalog-id]'));

  const viewForKind = (kind) => ({
    'attack-path': 'attack-surface',
    boundary: 'attack-surface',
    control: 'controls',
    system: 'system',
    threat: 'threats',
    evidence: 'evidence',
    posture: 'evidence',
  })[kind] || 'threats';

  const selectAtlasView = (viewId) => {
    const tabs = Array.from(document.querySelectorAll('[data-atlas-view]'));
    const panels = Array.from(document.querySelectorAll('[data-atlas-panel]'));
    if (!tabs.length || !panels.length) return;
    tabs.forEach((button) => {
      const selected = button.dataset.atlasView === viewId;
      button.setAttribute('aria-selected', String(selected));
      button.classList.toggle('md-button--primary', selected);
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.atlasPanel !== viewId;
    });
  };

  const catalogCard = (kind, target) => catalogCards().find((card) =>
    card.dataset.catalogKind === kind && card.dataset.catalogTarget === target
  ) || null;

  const markCatalogSelection = (kind, target) => {
    document.querySelectorAll('[data-catalog-id],[data-attack-path-id]').forEach((element) => {
      const selected = (
        (element.dataset.catalogKind === kind && element.dataset.catalogTarget === target)
        || (kind === 'attack-path' && element.dataset.attackPathId === target)
      );
      element.setAttribute('aria-pressed', String(selected));
    });
  };

  const detailFromCard = (card, fallbackTitle, fallbackBody, fallbackMeta = '') => {
    detail(
      card?.dataset.catalogTitle || fallbackTitle,
      card?.dataset.catalogSummary || fallbackBody,
      card?.dataset.catalogMeta || fallbackMeta,
    );
  };

  const clearSvg = () => {
    all('.node,.flow,.control').forEach((el) => el.classList.remove('is-active', 'is-muted'));
    all('.attack').forEach((el) => el.classList.remove('is-active'));
  };

  const clear = () => {
    clearSvg();
    document.querySelectorAll('[data-catalog-id],[data-attack-path-id]').forEach((el) => el.setAttribute('aria-pressed', 'false'));
  };

  const activateAttackPath = (id) => {
    clear();
    selectAtlasView('attack-surface');
    markCatalogSelection('attack-path', id);
    const card = catalogCard('attack-path', id);
    const path = all('.attack').find((candidate) => candidate.dataset.attackPath === id) || null;

    // Detail projection is intentionally independent of SVG readiness. Deep links can
    // resolve before the <object> document loads; the SVG highlight is replayed on load.
    detailFromCard(
      card,
      `Attack path ${id}`,
      'Modeled security-review path. Red animation is explanatory and does not represent a live attack.',
      path?.dataset.stride || '',
    );

    if (!path) return;
    path.classList.add('is-active');
    const nodes = new Set((path.dataset.nodes || '').split(/\s+/).filter(Boolean));
    const controls = new Set((path.dataset.controls || '').split(/\s+/).filter(Boolean));
    all('.node').forEach((node) => node.classList.toggle('is-muted', !nodes.has(node.dataset.node)));
    all('.control').forEach((control) => {
      const active = controls.has(control.dataset.control);
      control.classList.toggle('is-active', active);
      control.classList.toggle('is-muted', !active);
    });
  };

  const activateControl = (control) => {
    clear();
    const id = control.dataset.control || 'Security control';
    selectAtlasView('controls');
    markCatalogSelection('control', id);
    const card = catalogCard('control', id);
    const boundaries = new Set((control.dataset.boundaries || '').split(/\s+/).filter(Boolean));
    control.classList.add('is-active');
    all('.node').forEach((node) => node.classList.toggle('is-muted', !boundaries.has(node.dataset.boundary)));
    all('.control').forEach((candidate) => candidate.classList.toggle('is-muted', candidate !== control));
    detailFromCard(
      card,
      id,
      `Applied at: ${Array.from(boundaries).join(', ') || 'unvalidated'}`,
      control.dataset.threats || '',
    );
  };

  const activateControlById = (id) => {
    const control = all('.control').find((candidate) => candidate.dataset.control === id) || null;
    if (control) {
      activateControl(control);
      return;
    }
    clear();
    selectAtlasView('controls');
    markCatalogSelection('control', id);
    detailFromCard(catalogCard('control', id), `Control ${id}`, 'Source-derived security control.', 'SVG projection pending');
  };

  const activateNode = (node) => {
    clear();
    const id = node.dataset.node || 'unvalidated';
    selectAtlasView('system');
    markCatalogSelection('system', id);
    const card = catalogCard('system', id);
    const boundary = node.dataset.boundary || 'unvalidated';
    node.classList.add('is-active');
    all('.node').forEach((candidate) => candidate.classList.toggle('is-muted', candidate !== node));
    detailFromCard(
      card,
      node.getAttribute('aria-label')?.split(';')[0] || id,
      `Trust boundary: ${boundary}. Current promoted posture: ${node.dataset.state || 'unvalidated'}.`,
      `architecture:${node.dataset.architectureComponent || 'unvalidated'}`,
    );
  };

  const activateNodeById = (id) => {
    const node = all('.node').find((candidate) => candidate.dataset.node === id) || null;
    if (node) {
      activateNode(node);
      return;
    }
    clear();
    selectAtlasView('system');
    markCatalogSelection('system', id);
    detailFromCard(catalogCard('system', id), id, 'Canonical architecture component.', 'SVG projection pending');
  };

  const activateCatalogOnly = (kind, target) => {
    clear();
    selectAtlasView(viewForKind(kind));
    markCatalogSelection(kind, target);
    const card = catalogCard(kind, target);
    if (!card) return;
    detailFromCard(card, card.dataset.catalogTitle || target, card.dataset.catalogSummary || 'Source-derived catalog entry.');
  };

  const readDeepLink = () => {
    const url = new URL(window.location.href);

    // Canonical Security Atlas state lives in query parameters so MkDocs
    // Material remains free to own the document fragment namespace.
    for (const kind of DEEP_LINK_KEYS) {
      const target = url.searchParams.get(`atlas-${kind}`);
      if (target) return { kind, target, source: 'query' };
    }

    // Backward compatibility for previously shared fragment deep links such
    // as #attack-path=AP-04.
    const raw = window.location.hash.replace(/^#/, '');
    if (!raw || !raw.includes('=')) return null;

    const params = new URLSearchParams(raw);
    for (const kind of DEEP_LINK_KEYS) {
      const target = params.get(kind);
      if (target) return { kind, target, source: 'legacy-hash' };
    }

    return null;
  };

  const applyDeepLink = () => {
    const selection = readDeepLink();
    if (!selection) return false;

    const { kind, target } = selection;

    if (kind === 'attack-path') activateAttackPath(target);
    else if (kind === 'control') activateControlById(target);
    else if (kind === 'system') activateNodeById(target);
    else activateCatalogOnly(kind, target);

    return true;
  };

  const replaceSemanticUrl = (kind, target) => {
    const url = new URL(window.location.href);

    // Exactly one Security Atlas semantic selection is canonical at a time.
    DEEP_LINK_KEYS.forEach((key) => {
      url.searchParams.delete(`atlas-${key}`);
    });

    url.searchParams.set(`atlas-${kind}`, target);

    // The fragment belongs to the documentation shell. Keeping this stable
    // prevents Security Atlas state from competing with MkDocs section state.
    url.hash = '#security-atlas';

    window.history.replaceState(
      window.history.state,
      '',
      `${url.pathname}${url.search}${url.hash}`,
    );
  };

  const projectSelection = (kind, target) => {
    replaceSemanticUrl(kind, target);
    applyDeepLink();
  };

  const bindSvg = () => {
    const doc = svgDocument();
    if (!doc || doc.documentElement.dataset.plBound === 'true') {
      applyDeepLink();
      return;
    }
    doc.documentElement.dataset.plBound = 'true';
    all('.control').forEach((control) => {
      const invoke = () => projectSelection('control', control.dataset.control || '');
      control.addEventListener('click', invoke);
      control.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); invoke(); }
      });
    });
    all('.node').forEach((node) => {
      const invoke = () => projectSelection('system', node.dataset.node || '');
      node.addEventListener('click', invoke);
      node.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); invoke(); }
      });
    });
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      svgRoot()?.classList.add('motion-paused');
      const button = document.querySelector('[data-threat-motion="toggle"]');
      if (button) { button.textContent = 'Reduced motion'; button.disabled = true; }
    }
    // Reapply the URL state after the embedded SVG becomes available. This is the
    // deterministic replay that prevents a valid AP-04 deep link from leaving the
    // detail panel on its default text because the object loaded later than the page.
    applyDeepLink();
  };

  const enhanceThreatModelScrollableRegions = () => {
    if (!document.querySelector('.pl-threat-subnav')) return;

    Array.from(document.querySelectorAll('.md-typeset__table'))
      .forEach((region, index) => {
        const label = `Threat Model data table ${index + 1}`;
        const table = region.querySelector(':scope > table');

        region.dataset.plThreatScrollRegion = 'true';

        /*
         * Material can make the table itself the effective horizontal
         * scrolling surface on narrow viewports. The real scroll owner must
         * therefore be keyboard reachable; focusing only its wrapper does
         * not satisfy Safari/WCAG keyboard-access semantics.
         *
         * Preserve native <table> semantics: do not replace its role.
         */
        if (table) {
          if (!table.hasAttribute('tabindex')) {
            table.setAttribute('tabindex', '0');
          }

          if (!table.hasAttribute('aria-label')) {
            table.setAttribute('aria-label', label);
          }
        }

        /*
         * The wrapper remains a named structural region, but it is not an
         * additional tab stop. The focusable child table satisfies keyboard
         * access for both the table and any scrollable wrapper.
         */
        region.removeAttribute('tabindex');

        if (!region.hasAttribute('role')) {
          region.setAttribute('role', 'region');
        }

        if (!region.hasAttribute('aria-label')) {
          region.setAttribute('aria-label', label);
        }
      });
  };

  const enhanceThreatModel = () => {
    enhanceThreatModelScrollableRegions();
    const object = document.querySelector(rootSelector);
    if (!object || object.dataset.plThreatBound === 'true') return;
    object.dataset.plThreatBound = 'true';
    object.addEventListener('load', bindSvg);
    if (object.contentDocument) bindSvg();

    document.querySelectorAll('[data-atlas-view]').forEach((button) => button.addEventListener('click', () => {
      selectAtlasView(button.dataset.atlasView || 'threats');
    }));
    catalogCards().forEach((button) => button.addEventListener('click', () => {
      const kind = button.dataset.catalogKind || 'threat';
      const target = button.dataset.catalogTarget || button.dataset.catalogId || '';
      if (target) projectSelection(kind, target);
    }));
    document.querySelectorAll('[data-attack-path-id]').forEach((button) => button.addEventListener('click', () => {
      const id = button.dataset.attackPathId || '';
      if (id) projectSelection('attack-path', id);
    }));
    document.querySelectorAll('[data-threat-mode]').forEach((button) => button.addEventListener('click', () => {
      clear();
      const mode = button.dataset.threatMode;
      if (mode === 'controls') detail('Controls view', 'Select a shield in the diagram to highlight every trust boundary where that control applies.');
      else if (mode === 'attack-paths') detail('Attack paths', 'Choose a reviewed path below the diagram to highlight its modeled route and controls.');
      else if (mode === 'evidence') detail('Evidence posture', 'Node outlines reflect the latest promoted/canonical evidence state; this is not live monitoring.');
      else detail('System view', 'Canonical architecture and allowed/control flow. Animation is modeled flow, never live traffic.');
    }));
    document.querySelector('[data-threat-motion="toggle"]')?.addEventListener('click', (event) => {
      const root = svgRoot();
      if (!root) return;
      const paused = root.classList.toggle('motion-paused');
      event.currentTarget.textContent = paused ? 'Resume animation' : 'Pause animation';
    });
    document.querySelectorAll('[data-evidence-id]').forEach((link) => link.addEventListener('click', () => {
      detail('Evidence lineage', `Selected lineage step: ${link.dataset.evidenceId}. The exact canonical source is shown in the link card.`);
    }));

    if (!applyDeepLink()) selectAtlasView('threats');
  };

  if (!window.__plThreatNavigationBound) {
    window.__plThreatNavigationBound = true;
    window.addEventListener('popstate', applyDeepLink);
    window.addEventListener('hashchange', applyDeepLink);
  }
  if (typeof document$ !== 'undefined') document$.subscribe(enhanceThreatModel);
  else document.addEventListener('DOMContentLoaded', enhanceThreatModel);
})();

/* Security Atlas polish: explicit view selection and dismissible saved-model focus. */
(() => {
  const DEEP_LINK_KEYS = ['attack-path', 'control', 'system', 'boundary', 'threat', 'evidence', 'posture'];
  const svgObject = () => document.querySelector('#pl-threat-model-svg');
  const svgDocument = () => svgObject()?.contentDocument || null;
  const svgAll = (selector) => Array.from(svgDocument()?.querySelectorAll(selector) || []);

  const clearSemanticUrl = () => {
    const url = new URL(window.location.href);
    DEEP_LINK_KEYS.forEach((key) => url.searchParams.delete(`atlas-${key}`));
    url.hash = '#security-atlas';
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const defaultDetail = () => {
    const panel = document.querySelector('#threat-selection');
    if (!panel) return;
    panel.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = 'Explore the saved model';
    const p = document.createElement('p');
    p.textContent = 'Choose a component, control, catalog entry or reviewed attack path. Click empty diagram space or press Escape to clear focus.';
    panel.append(strong, p);
  };

  const resetSelection = () => {
    svgAll('.node,.flow,.control').forEach((element) => element.classList.remove('is-active', 'is-muted'));
    svgAll('.attack').forEach((element) => element.classList.remove('is-active'));
    document.querySelectorAll('[data-catalog-id],[data-attack-path-id]').forEach((element) => element.setAttribute('aria-pressed', 'false'));
    clearSemanticUrl();
    defaultDetail();
    document.documentElement.dataset.plThreatFocus = 'false';
  };

  const syncAtlasTabs = () => {
    document.querySelectorAll('[data-atlas-view]').forEach((button) => {
      const selected = button.getAttribute('aria-selected') === 'true';
      button.dataset.selected = String(selected);
      button.classList.toggle('pl-is-selected', selected);
    });
  };

  const selectDiagramMode = (selected) => {
    document.querySelectorAll('[data-threat-mode]').forEach((button) => {
      const active = button === selected;
      button.setAttribute('aria-pressed', String(active));
      button.dataset.selected = String(active);
      button.classList.toggle('pl-is-selected', active);
      button.classList.toggle('md-button--primary', active);
    });
    const mode = selected?.dataset.threatMode || 'system';
    const root = svgDocument()?.documentElement;
    if (root) {
      ['system', 'controls', 'attack-paths', 'evidence'].forEach((name) => root.classList.toggle(`view-${name}`, name === mode));
      root.dataset.viewMode = mode;
    }
  };

  const bindSvgReset = () => {
    const object = svgObject();
    const bind = () => {
      const doc = object?.contentDocument;
      if (!doc || doc.documentElement.dataset.plAtlasResetBound === 'true') return;
      doc.documentElement.dataset.plAtlasResetBound = 'true';
      const onDiagramPointer = (event) => {
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if (target.closest('.node,.control')) {
          document.documentElement.dataset.plThreatFocus = 'true';
          return;
        }
        if (target.closest('[data-reset-target="true"],.bg,.grid') || target === doc.documentElement) resetSelection();
      };
      doc.documentElement.addEventListener('pointerdown', onDiagramPointer);
      doc.documentElement.addEventListener('click', onDiagramPointer);
      doc.documentElement.addEventListener('keydown', (event) => {
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if ((event.key === 'Enter' || event.key === ' ') && target.closest('.node,.control')) {
          document.documentElement.dataset.plThreatFocus = 'true';
        }
      });
      const current = document.querySelector('[data-threat-mode][aria-pressed="true"]') || document.querySelector('[data-threat-mode="system"]');
      if (current) selectDiagramMode(current);
    };
    object?.addEventListener('load', bind);
    bind();
  };

  const enhance = () => {
    const atlasRoot = document.querySelector('.pl-atlas-layout');
    if (!atlasRoot || atlasRoot.dataset.plAtlasPolishBound === 'true') return;
    atlasRoot.dataset.plAtlasPolishBound = 'true';
    syncAtlasTabs();
    document.querySelectorAll('[data-atlas-view]').forEach((button) => button.addEventListener('click', syncAtlasTabs));
    const system = document.querySelector('[data-threat-mode="system"]');
    if (system) selectDiagramMode(system);
    document.querySelectorAll('[data-threat-mode]').forEach((button) => button.addEventListener('click', () => selectDiagramMode(button)));
    document.querySelectorAll('[data-catalog-id],[data-attack-path-id]').forEach((button) => button.addEventListener('click', () => {
      document.documentElement.dataset.plThreatFocus = 'true';
    }));
    bindSvgReset();
    if (!window.__plThreatAtlasPolishNavigationBound) {
      window.__plThreatAtlasPolishNavigationBound = true;
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && document.querySelector('.pl-atlas-layout')) resetSelection();
      });
      document.addEventListener('pointerdown', (event) => {
        if (document.documentElement.dataset.plThreatFocus !== 'true' || !document.querySelector('.pl-atlas-layout')) return;
        const target = event.target;
        if (!target || typeof target.closest !== 'function') return;
        if (target.closest('.pl-threat-canvas,.pl-atlas-layout,.pl-threat-toolbar,.pl-atlas-toolbar,[data-attack-path-id]')) return;
        resetSelection();
      });
    }
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();
