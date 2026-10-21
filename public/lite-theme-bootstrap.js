(function () {
  // Blocking same-origin bootstrap: resolve only a harmless preference before CSS paint.
  var preference = 'system';
  try {
    var value = localStorage.getItem('pocketlab:appearance');
    if (value === null) value = localStorage.getItem('POCKETLAB_LITE_THEME');
    if (value === 'light' || value === 'dark' || value === 'system') preference = value;
    else if (value === 'daylight') preference = 'light';
  } catch (_) { /* private browsing */ }
  var dark = preference === 'dark' || (preference === 'system' &&
    !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches));
  var theme = dark ? 'dark' : 'light';
  var root = document.documentElement;
  root.dataset.liteTheme = theme;
  root.dataset.pocketlabLiteTheme = dark ? 'dark' : 'daylight';
  root.classList.toggle('theme-pocket-lite-dark', dark);
  root.classList.toggle('theme-pocket-lite-daylight', !dark);
  root.style.colorScheme = theme;
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', dark ? '#050607' : '#F4F9FF');
})();
