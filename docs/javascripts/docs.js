(() => {
  const labelProgressBars = (root = document) => {
    const label = (element) => {
      if (element?.matches?.('.md-progress[role=\"progressbar\"]') && !element.hasAttribute('aria-label')) {
        element.setAttribute('aria-label', 'Page loading progress');
      }
    };

    label(root);
    root?.querySelectorAll?.('.md-progress[role=\"progressbar\"]').forEach(label);
  };

  const enhanceAccessibility = () => {
    labelProgressBars();
    const searchDialog = document.querySelector('[data-md-component="search"][role="dialog"]');
    if (searchDialog && !searchDialog.hasAttribute('aria-label')) {
      searchDialog.setAttribute('aria-label', 'Search documentation');
    }

    document.querySelectorAll('.md-content a[href^="http"]').forEach((link) => {
      try {
        if (new URL(link.href).origin !== window.location.origin) {
          link.rel = 'noopener noreferrer';
          link.dataset.external = 'true';
        }
      } catch (_) {
        // Strict MkDocs validation owns malformed authored links.
      }
    });
  };

  const canPrefetch = () => {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection?.saveData) return false;
    return !['slow-2g', '2g'].includes(connection?.effectiveType);
  };

  const prefetched = new Set();
  const prefetch = (anchor) => {
    if (!canPrefetch() || !anchor?.href) return;
    const url = new URL(anchor.href, window.location.href);
    if (url.origin !== window.location.origin || prefetched.has(url.href)) return;
    prefetched.add(url.href);
    const hint = document.createElement('link');
    hint.rel = 'prefetch';
    hint.href = url.href;
    hint.as = 'document';
    document.head.appendChild(hint);
  };

  const enhanceIntentNavigation = () => {
    document.querySelectorAll('a.pl-intent-link').forEach((anchor) => {
      if (anchor.dataset.plIntentBound === 'true') return;
      anchor.dataset.plIntentBound = 'true';
      anchor.addEventListener('pointerenter', () => prefetch(anchor), { once: true, passive: true });
      anchor.addEventListener('focus', () => prefetch(anchor), { once: true });
      anchor.addEventListener('touchstart', () => prefetch(anchor), { once: true, passive: true });
    });
  };

  let progressObserver;
  const observeProgressBars = () => {
    if (progressObserver || !document.body) return;
    progressObserver = new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) labelProgressBars(node);
        }
      }
    });
    progressObserver.observe(document.body, { childList: true, subtree: true });
  };

  const enhanceAudienceIdentity = () => {
    const content = document.querySelector('.md-content__inner');
    if (!content || content.querySelector('.pl-audience-banner')) return;
    const path = window.location.pathname;
    const audience = path.includes('/generated/production/') || path.includes('/generated/enterprise/threat-model/') || path.includes('/generated/enterprise/operate/')
      ? 'production'
      : path.includes('/generated/development/') || path.includes('/generated/enterprise/engineering/') || path.includes('/generated/enterprise/documentation-platform/')
        ? 'development'
        : null;
    if (!audience) return;
    const banner = document.createElement('div');
    banner.className = `pl-audience-banner pl-audience-banner--${audience}`;
    banner.setAttribute('role', 'note');
    if (audience === 'production') {
      banner.innerHTML = '<strong>POCKET LAB LITE · Production Knowledge</strong><small>Operational · evidence-backed · sanitized · release-aware</small>';
    } else {
      banner.innerHTML = '<strong>POCKET LAB LITE · Engineering Reference</strong><small>Source-derived · contracts · validation · implementation detail</small>';
    }
    content.prepend(banner);
  };

  const enhance = () => {
    observeProgressBars();
    enhanceAccessibility();
    enhanceIntentNavigation();
    enhanceAudienceIdentity();
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();
