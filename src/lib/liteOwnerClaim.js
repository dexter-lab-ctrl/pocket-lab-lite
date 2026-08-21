let pendingOwnerClaim = '';

export function captureOwnerClaimFromUrl() {
  if (typeof window === 'undefined') return '';
  const url = new URL(window.location.href);
  const claim = String(url.searchParams.get('owner_claim') || '');
  if (!claim) return '';
  pendingOwnerClaim = claim;
  url.searchParams.delete('owner_claim');
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  return claim;
}

export function takePendingOwnerClaim() {
  const claim = pendingOwnerClaim;
  pendingOwnerClaim = '';
  return claim;
}

export function hasPendingOwnerClaim() {
  return Boolean(pendingOwnerClaim);
}
