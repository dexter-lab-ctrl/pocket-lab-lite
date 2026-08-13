(() => {
  'use strict';

  const mermaid = window.mermaid;

  if (!mermaid || typeof mermaid.initialize !== 'function') {
    throw new Error(
      'Pocket Lab docs Mermaid runtime is unavailable; ' +
      'the repository-owned Mermaid asset must load before mermaid-local.js',
    );
  }

  /*
   * Material for MkDocs owns Mermaid lifecycle, palette synchronization,
   * instant-navigation re-rendering, and diagram mounting.
   *
   * Disable Mermaid's independent page-load initialization so there is one
   * renderer/lifecycle owner and no duplicate rendering race.
   */
  mermaid.initialize({
    startOnLoad: false,
  });

  /*
   * Deliberately preserve the global. Material detects a supplied Mermaid
   * runtime through window.mermaid and therefore does not need its dynamic
   * CDN fallback.
   */
  window.mermaid = mermaid;
})();
