(() => {
  const rootSelector = '#pl-threat-model-svg';

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

  const clear = () => {
    all('.node,.flow,.control').forEach((el) => el.classList.remove('is-active', 'is-muted'));
    all('.attack').forEach((el) => el.classList.remove('is-active'));
    document.querySelectorAll('[data-attack-path-id]').forEach((el) => el.setAttribute('aria-pressed', 'false'));
  };

  const activateAttackPath = (id) => {
    clear();
    const path = all(`.attack[data-attack-path="${CSS.escape(id)}"]`)[0];
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
    document.querySelectorAll('[data-attack-path-id]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.attackPathId === id)));
    detail(`Attack path ${id}`, 'Modeled security-review path. Red animation is explanatory and does not represent a live attack.', path.dataset.stride || '');
  };

  const activateControl = (control) => {
    clear();
    const boundaries = new Set((control.dataset.boundaries || '').split(/\s+/).filter(Boolean));
    control.classList.add('is-active');
    all('.node').forEach((node) => node.classList.toggle('is-muted', !boundaries.has(node.dataset.boundary)));
    all('.control').forEach((candidate) => candidate.classList.toggle('is-muted', candidate !== control));
    detail(control.dataset.control || 'Security control', `Applied at: ${Array.from(boundaries).join(', ') || 'unvalidated'}`, control.dataset.threats || '');
  };

  const activateNode = (node) => {
    clear();
    const boundary = node.dataset.boundary || 'unvalidated';
    node.classList.add('is-active');
    all('.node').forEach((candidate) => candidate.classList.toggle('is-muted', candidate !== node));
    detail(node.getAttribute('aria-label')?.split(';')[0] || node.dataset.node, `Trust boundary: ${boundary}. Current promoted posture: ${node.dataset.state || 'unvalidated'}.`, `architecture:${node.dataset.architectureComponent || 'unvalidated'}`);
  };

  const bindSvg = () => {
    const doc = svgDocument();
    if (!doc || doc.documentElement.dataset.plBound === 'true') return;
    doc.documentElement.dataset.plBound = 'true';
    all('.control').forEach((control) => {
      const invoke = () => activateControl(control);
      control.addEventListener('click', invoke);
      control.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); invoke(); } });
    });
    all('.node').forEach((node) => {
      const invoke = () => activateNode(node);
      node.addEventListener('click', invoke);
      node.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); invoke(); } });
    });
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      svgRoot()?.classList.add('motion-paused');
      const button = document.querySelector('[data-threat-motion="toggle"]');
      if (button) { button.textContent = 'Reduced motion'; button.disabled = true; }
    }
  };

  const enhanceThreatModel = () => {
    const object = document.querySelector(rootSelector);
    if (!object || object.dataset.plThreatBound === 'true') return;
    object.dataset.plThreatBound = 'true';
    object.addEventListener('load', bindSvg, { once: true });
    if (object.contentDocument) bindSvg();

    document.querySelectorAll('[data-attack-path-id]').forEach((button) => button.addEventListener('click', () => activateAttackPath(button.dataset.attackPathId)));
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
    document.querySelectorAll('[data-evidence-id]').forEach((link) => link.addEventListener('click', () => detail('Evidence lineage', `Selected lineage step: ${link.dataset.evidenceId}. The exact canonical source is shown in the link card.`)));
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhanceThreatModel);
  else document.addEventListener('DOMContentLoaded', enhanceThreatModel);
})();
