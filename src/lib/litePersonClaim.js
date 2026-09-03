export function takePendingPersonClaim() {
  if (typeof window === 'undefined') return '';
  const url = new URL(window.location.href);
  const claim = String(url.searchParams.get('person_claim') || '').trim();
  if (!claim) return '';
  url.searchParams.delete('person_claim');
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  return claim;
}
