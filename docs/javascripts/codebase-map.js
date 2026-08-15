(() => {
  const mountCodebaseMap = () => {
    const root = document.querySelector('[data-pl-codebase-map="true"]');
    if (!root || root.dataset.plCodebaseBound === 'true') return;
    root.dataset.plCodebaseBound = 'true';

  const q = (selector) => root.querySelector(selector);
  const tree = q('[data-cb-tree]');
  const inspector = q('[data-cb-inspector]');
  const search = q('[data-cb-search]');
  const roleFilter = q('[data-cb-role]');
  const languageFilter = q('[data-cb-language]');
  const ownerFilter = q('[data-cb-owner]');
  const confidenceFilter = q('[data-cb-confidence]');
  const collapse = q('[data-cb-collapse]');
  const state = { data: null, selected: null, expanded: new Set(['path:.']), query: '', filters: {}, symbol: '' };
  const HISTORY_KEY = 'pocketLabCodebaseMap';
  const HISTORY_PATH = window.location.pathname;
  const codebaseHistoryState = () => ({
    ...((history.state && typeof history.state === 'object') ? history.state : {}),
    [HISTORY_KEY]: true,
  });

  const el = (tag, cls = '', text = '') => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== '') node.textContent = String(text);
    return node;
  };
  const add = (parent, ...nodes) => (parent.append(...nodes), parent);
  const nodeById = (id) => state.data?.nodeMap.get(id);
  const external = (id) => state.data?.external?.[id];
  const labelFor = (id) => nodeById(id)?.p || external(id)?.name || id;
  const pathFor = (id) => nodeById(id)?.p || '';
  const fmtBytes = (value) => {
    const n = Number(value || 0);
    if (!n) return '—';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
  };
  const safePath = (value) => {
    if (!value || value === '.') return value || '.';
    let decoded = value;
    try { decoded = decodeURIComponent(value); } catch (_) { return ''; }
    decoded = decoded.replace(/\\/g, '/').replace(/^\.\//, '');
    if (/^(?:\/|[A-Za-z]:)/.test(decoded)) return '';
    const parts = decoded.split('/');
    if (parts.some((part) => !part || part === '.' || part === '..')) return '';
    return parts.join('/');
  };
  const updateUrl = (node, symbol = '', replace = false) => {
    const url = new URL(window.location.href);
    if (node?.p && node.p !== '.') url.searchParams.set('path', node.p);
    else url.searchParams.delete('path');
    if (symbol) url.searchParams.set('symbol', symbol);
    else url.searchParams.delete('symbol');
    history[replace ? 'replaceState' : 'pushState'](codebaseHistoryState(), '', url);
  };
  const expandAncestors = (node) => {
    let cursor = node;
    while (cursor?.parent) {
      state.expanded.add(cursor.parent);
      cursor = nodeById(cursor.parent);
    }
  };
  const selectNode = (node, options = {}) => {
    if (!node) return;
    state.selected = node.id;
    state.symbol = options.symbol || '';
    expandAncestors(node);
    if (!options.fromHistory) updateUrl(node, state.symbol, Boolean(options.replace));
    renderTree();
    renderInspector();
    requestAnimationFrame(() => tree.querySelector(`[data-cb-node-id="${CSS.escape(node.id)}"]`)?.scrollIntoView({ block: 'nearest' }));
  };

  const relationship = (id) => state.data.relMap.get(id);
  const outgoing = (id) => (state.data.indexes.relationships_from[id] || []).map(relationship).filter(Boolean);
  const incoming = (id) => (state.data.indexes.relationships_to[id] || []).map(relationship).filter(Boolean);
  const pathRelations = (items) => items.filter((rel) => nodeById(rel.a) || nodeById(rel.b));

  const scoreNode = (node, query) => {
    const normalized = query.toLowerCase().trim();
    if (!normalized) return 1;
    const hay = state.data.indexes.search[node.id] || '';
    const file = node.p.split('/').pop().toLowerCase();
    const path = node.p.toLowerCase();
    if (path === normalized) return 1000;
    if (file === normalized) return 900;
    if (path.startsWith(normalized)) return 700;
    const tokens = normalized.split(/\s+/).filter(Boolean);
    if (!tokens.every((token) => hay.includes(token))) return 0;
    return 100 + tokens.reduce((sum, token) => sum + (path.includes(token) ? 20 : 5), 0);
  };
  const matchesFilters = (node) => {
    const f = state.filters;
    return (!f.role || node.r === f.role)
      && (!f.language || (node.l || '') === f.language)
      && (!f.owner || node.o === f.owner)
      && (!f.confidence || node.c === f.confidence);
  };
  const visibleSearchResults = () => state.data.nodes
    .map((node) => ({ node, score: scoreNode(node, state.query) }))
    .filter(({ node, score }) => score > 0 && matchesFilters(node))
    .sort((a, b) => b.score - a.score || a.node.p.localeCompare(b.node.p))
    .slice(0, 120)
    .map(({ node }) => node);

  const treeRow = (node, depth) => {
    const row = el('div', `pl-codebase-tree-row pl-codebase-tree-row--${node.k}`);
    row.style.setProperty('--cb-depth', String(depth));
    const children = state.data.indexes.children_by_parent[node.id] || [];
    const toggle = el('button', 'pl-codebase-tree-toggle', children.length ? (state.expanded.has(node.id) ? '▾' : '▸') : '·');
    toggle.type = 'button';
    toggle.disabled = !children.length;
    toggle.setAttribute('aria-label', children.length ? `${state.expanded.has(node.id) ? 'Collapse' : 'Expand'} ${node.p}` : `${node.p} has no children`);
    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      state.expanded.has(node.id) ? state.expanded.delete(node.id) : state.expanded.add(node.id);
      renderTree();
    });
    const button = el('button', 'pl-codebase-tree-node');
    button.type = 'button';
    button.dataset.cbNodeId = node.id;
    button.setAttribute('role', 'treeitem');
    button.setAttribute('aria-selected', state.selected === node.id ? 'true' : 'false');
    button.title = node.p;
    const icon = el('span', `pl-codebase-node-icon pl-codebase-node-icon--${node.k}`, node.k === 'directory' ? '◇' : '•');
    icon.setAttribute('aria-hidden', 'true');
    const name = el('span', 'pl-codebase-node-name', node.p === '.' ? 'pocket-lab-lite' : node.p.split('/').pop());
    const meta = el('span', 'pl-codebase-node-meta', node.k === 'file' ? node.r : `${children.length} items`);
    add(button, icon, name, meta);
    button.addEventListener('click', () => selectNode(node));
    button.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowRight' && children.length) { state.expanded.add(node.id); renderTree(); }
      if (event.key === 'ArrowLeft' && children.length) { state.expanded.delete(node.id); renderTree(); }
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectNode(node); }
    });
    return add(row, toggle, button);
  };

  const renderBranch = (id, depth, container, budget) => {
    if (budget.count >= 900) return;
    const node = nodeById(id);
    if (!node) return;
    container.append(treeRow(node, depth));
    budget.count += 1;
    if (!state.expanded.has(id)) return;
    for (const child of state.data.indexes.children_by_parent[id] || []) renderBranch(child, depth + 1, container, budget);
  };
  const renderTree = () => {
    if (!state.data) return;
    tree.replaceChildren();
    if (state.query || Object.values(state.filters).some(Boolean)) {
      const results = visibleSearchResults();
      const header = el('div', 'pl-codebase-results-meta', `${results.length} matching paths (max 120)`);
      tree.append(header);
      results.forEach((node) => tree.append(treeRow(node, Math.min(node.p.split('/').length - 1, 4))));
      if (!results.length) tree.append(add(el('div', 'pl-empty-state'), el('strong', '', 'No matching paths'), el('p', '', 'Try a different path, role, language, owner, or confidence filter.')));
      return;
    }
    renderBranch(state.data.root_id, 0, tree, { count: 0 });
  };

  const fact = (label, value) => add(el('div', 'pl-codebase-fact'), el('span', '', label), el('strong', '', value ?? '—'));
  const chips = (title, values) => {
    const section = el('section', 'pl-codebase-inspector-section');
    section.append(el('h4', '', title));
    const list = el('div', 'pl-chip-list');
    (values.length ? values : ['None recorded']).forEach((value) => list.append(el('span', values.length ? 'pl-chip pl-chip--code' : 'pl-chip pl-chip--muted', labelFor(value))));
    section.append(list);
    return section;
  };
  const relationSection = (title, rows, currentId, limit = 24) => {
    const section = el('section', 'pl-codebase-inspector-section');
    section.append(el('h4', '', `${title} (${rows.length})`));
    const list = el('div', 'pl-codebase-relation-list');
    rows.slice(0, limit).forEach((rel) => {
      const outbound = rel.a === currentId;
      const other = outbound ? rel.b : rel.a;
      const node = nodeById(other);
      const item = el(node ? 'button' : 'div', 'pl-codebase-relation');
      if (node) { item.type = 'button'; item.addEventListener('click', () => selectNode(node)); }
      add(item, el('code', 'pl-codebase-relation-type', rel.t), el('span', '', `${outbound ? '→' : '←'} ${labelFor(other)}`));
      list.append(item);
    });
    if (!rows.length) list.append(el('p', 'pl-muted', 'No evidence-backed relationships recorded.'));
    if (rows.length > limit) list.append(el('p', 'pl-muted', `Showing first ${limit}; refine search or inspect related nodes.`));
    section.append(list);
    return section;
  };
  const impactFor = (id) => {
    const visited = new Set([id]);
    let frontier = [id];
    const direct = [], transitive = [];
    const allowed = new Set(['IMPORTS', 'GENERATED_BY', 'GENERATES', 'TESTED_BY', 'CONFIGURED_BY', 'DEPENDS_ON']);
    for (let depth = 1; depth <= 2; depth += 1) {
      const next = [];
      for (const current of frontier) {
        for (const rel of incoming(current)) {
          if (!allowed.has(rel.t)) continue;
          const candidate = rel.a;
          if (!nodeById(candidate) || visited.has(candidate)) continue;
          visited.add(candidate); next.push(candidate);
          (depth === 1 ? direct : transitive).push(candidate);
          if (visited.size >= 42) break;
        }
        if (visited.size >= 42) break;
      }
      frontier = next;
      if (!frontier.length || visited.size >= 42) break;
    }
    return { direct, transitive };
  };
  const renderInspector = () => {
    inspector.replaceChildren();
    const node = nodeById(state.selected);
    if (!node) {
      add(inspector, el('span', 'pl-card-kicker', 'Inspector'), el('strong', '', 'Select a file or folder'), el('p', '', 'Purpose, ownership, relationships, symbols, and bounded impact appear here.'));
      return;
    }
    const header = el('div', 'pl-codebase-inspector-head');
    add(header, add(el('div'), el('span', 'pl-card-kicker', node.k === 'directory' ? 'Directory' : 'File'), el('h3', '', node.p === '.' ? 'pocket-lab-lite' : node.p)), el('button', 'md-button pl-codebase-copy', 'Copy path'));
    header.querySelector('button').addEventListener('click', async (event) => {
      try { await navigator.clipboard.writeText(node.p); event.currentTarget.textContent = 'Copied'; setTimeout(() => { event.currentTarget.textContent = 'Copy path'; }, 1200); } catch (_) { event.currentTarget.textContent = 'Copy unavailable'; }
    });
    inspector.append(header);
    const grid = el('div', 'pl-codebase-fact-grid');
    [
      ['Role', node.r], ['Execution owner', node.o], ['Language', node.l || '—'], ['Confidence', node.c],
      ['Freshness', node.s], ['Size', fmtBytes(node.size)], ['Lines', node.loc ?? '—'], ['Critical path', node.critical ? 'yes' : 'no'],
    ].forEach(([label, value]) => grid.append(fact(label, value)));
    inspector.append(grid);
    inspector.append(add(el('section', 'pl-codebase-inspector-section'), el('h4', '', 'Purpose'), el('p', 'pl-card-lead', node.purpose)));
    inspector.append(chips('Architecture', node.arch || []), chips('Trust boundaries', node.boundaries || []), chips('Knowledge', node.knowledge || []));

    const out = outgoing(node.id); const inc = incoming(node.id);
    const uses = pathRelations(out.filter((rel) => !['CONTAINS', 'TESTED_BY', 'MAPS_TO_KNOWLEDGE', 'MAPS_TO_ARCHITECTURE', 'MAPS_TO_TRUST_BOUNDARY', 'DEFINES'].includes(rel.t)));
    const usedBy = pathRelations(inc.filter((rel) => rel.t !== 'CONTAINS'));
    const tests = out.filter((rel) => rel.t === 'TESTED_BY');
    const generated = out.filter((rel) => ['GENERATES', 'GENERATED_BY', 'INVOKED_BY_TASK'].includes(rel.t));
    inspector.append(relationSection('Uses', uses, node.id), relationSection('Used by', usedBy, node.id), relationSection('Tests', tests, node.id), relationSection('Generated / tasks', generated, node.id));

    if (node.symbols?.length) {
      const section = el('section', 'pl-codebase-inspector-section');
      section.append(el('h4', '', `Symbols (${node.symbols.length})`));
      const list = el('div', 'pl-codebase-symbol-list');
      node.symbols.slice(0, 80).forEach((symbol) => {
        const button = el('button', `pl-codebase-symbol${state.symbol === symbol.name ? ' is-selected' : ''}`);
        button.type = 'button';
        add(button, el('code', '', symbol.name), el('span', '', `${symbol.kind || 'symbol'} · line ${symbol.line || '—'}`));
        button.addEventListener('click', () => selectNode(node, { symbol: symbol.name }));
        list.append(button);
      });
      section.append(list); inspector.append(section);
    }
    const impact = impactFor(node.id);
    const impactSection = el('section', 'pl-codebase-inspector-section');
    add(impactSection, el('h4', '', 'Bounded impact'), el('p', 'pl-muted', 'Static dependency projection only; it does not claim runtime consequences.'));
    const impactList = el('div', 'pl-codebase-impact');
    [['Direct', impact.direct], ['Transitive (depth 2)', impact.transitive]].forEach(([label, ids]) => {
      const box = el('div', 'pl-codebase-impact-group'); box.append(el('strong', '', `${label} (${ids.length})`));
      ids.slice(0, 20).forEach((id) => { const n = nodeById(id); const b = el('button', '', pathFor(id)); b.type = 'button'; b.addEventListener('click', () => selectNode(n)); box.append(b); });
      if (!ids.length) box.append(el('span', 'pl-muted', 'None recorded'));
      impactList.append(box);
    });
    impactSection.append(impactList); inspector.append(impactSection);
  };

  const fillFilter = (select, values) => {
    [...new Set(values.filter(Boolean))].sort().forEach((value) => {
      const option = document.createElement('option'); option.value = value; option.textContent = value; select.append(option);
    });
  };
  const bindFilters = () => {
    fillFilter(roleFilter, state.data.nodes.filter((n) => n.k === 'file').map((n) => n.r));
    fillFilter(languageFilter, state.data.nodes.map((n) => n.l));
    fillFilter(ownerFilter, state.data.nodes.map((n) => n.o));
    fillFilter(confidenceFilter, state.data.nodes.map((n) => n.c));
    const update = () => {
      state.query = search.value.trim();
      state.filters = { role: roleFilter.value, language: languageFilter.value, owner: ownerFilter.value, confidence: confidenceFilter.value };
      renderTree();
    };
    search.addEventListener('input', update);
    [roleFilter, languageFilter, ownerFilter, confidenceFilter].forEach((select) => select.addEventListener('change', update));
    collapse.addEventListener('click', () => { state.expanded = new Set(['path:.']); renderTree(); });
  };
  const restoreUrl = (replace = false) => {
    const url = new URL(window.location.href);
    const raw = url.searchParams.get('path') || '.';
    const normalized = raw === '.' ? '.' : safePath(raw);
    const id = normalized ? state.data.indexes.by_path[normalized] : null;
    const node = id ? nodeById(id) : nodeById(state.data.root_id);
    if (!id && raw !== '.') {
      inspector.replaceChildren(add(el('div', 'pl-empty-state'), el('strong', '', 'Path not found'), el('p', '', 'The requested path is invalid or is not present in the current Git-tracked Codebase Map.')));
      state.selected = state.data.root_id; state.symbol = ''; renderTree();
      if (replace) updateUrl(nodeById(state.data.root_id), '', true);
      return;
    }
    selectNode(node, { symbol: url.searchParams.get('symbol') || '', fromHistory: !replace, replace });
  };
  const fail = (message) => {
    tree.replaceChildren(add(el('div', 'pl-empty-state'), el('strong', '', 'Codebase Map unavailable'), el('p', '', message), el('code', '', 'contracts/generated/knowledge/repository-codebase-map.json')));
    inspector.replaceChildren(add(el('div', 'pl-empty-state'), el('strong', '', 'Static model remains authoritative'), el('p', '', 'Regenerate the Documentation Platform to restore the browser projection.')));
  };

  const prefix = location.pathname.includes('/generated/') ? location.pathname.split('/generated/')[0] : '';
  fetch(`${prefix}/generated/assets/knowledge/repository-codebase-map.json`, { credentials: 'same-origin' })
    .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then((data) => {
      if (!data || data.live_runtime !== false || !Array.isArray(data.nodes) || !Array.isArray(data.relationships)) throw new Error('invalid static Codebase Map projection');
      if (Number(root.dataset.nodeCount || 0) && Number(root.dataset.nodeCount) !== data.statistics.nodes) throw new Error('node count mismatch');
      data.nodeMap = new Map(data.nodes.map((node) => [node.id, node]));
      data.relMap = new Map(data.relationships.map((rel) => [rel.id, rel]));
      state.data = data;
      bindFilters();

      // Mark the initial Codebase Map entry while preserving any state that
      // MkDocs Material already placed on the history record.
      history.replaceState(codebaseHistoryState(), '', window.location.href);

      restoreUrl(false);

      // MkDocs Material uses popstate for navigation.instant. Codebase Map
      // path/symbol changes are same-document state, so handle only our
      // marked entries here and stop Material from replacing the document.
      window.addEventListener('popstate', (event) => {
        if (!root.isConnected) return;
        const isCodebaseEntry = Boolean(
          event.state
          && event.state[HISTORY_KEY] === true
          && window.location.pathname === HISTORY_PATH
        );
        if (!isCodebaseEntry) return;

        event.stopImmediatePropagation();
        restoreUrl(false);
      }, true);
    })
    .catch((error) => fail(`The same-origin generated browser projection could not be loaded (${error.message}).`));
  };

  const scheduleCodebaseMapMount = () => {
    window.requestAnimationFrame(() => mountCodebaseMap());
  };

  // Initial full-page load.
  mountCodebaseMap();

  // MkDocs Material navigation.instant replaces the document body without
  // reloading this extra JavaScript file. Re-mount against the new document
  // and restore the current ?path= / ?symbol= state after every swap.
  if (
    typeof document$ !== 'undefined'
    && document$
    && typeof document$.subscribe === 'function'
  ) {
    document$.subscribe(scheduleCodebaseMapMount);
  }
})();
