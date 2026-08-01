(() => {
  const enhanceAccessibility = () => {
    const searchDialog = document.querySelector('[data-md-component="search"][role="dialog"]');
    if (searchDialog && !searchDialog.hasAttribute('aria-label')) {
      searchDialog.setAttribute('aria-label', 'Search documentation');
    }

    const markExternalLinks = () => {
    document.querySelectorAll('.md-content a[href^="http"]').forEach((link) => {
      try {
        if (new URL(link.href).origin !== window.location.origin) {
          link.rel = 'noopener noreferrer';
          link.dataset.external = 'true';
        }
      } catch (_) {
        // Ignore malformed authored links; strict MkDocs validation handles them.
      }
    });
    };
    markExternalLinks();
  };
  if (typeof document$ !== 'undefined') document$.subscribe(enhanceAccessibility);
  else document.addEventListener('DOMContentLoaded', enhanceAccessibility);
})();
