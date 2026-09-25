export function shouldUseLiteSecurityProgressStream({
  rootOwnsAcceptedSecurityRun = false,
  shouldLoadSecurityProgress = false,
  activeSecurityDetails = null,
} = {}) {
  if (rootOwnsAcceptedSecurityRun) return false;
  return Boolean(shouldLoadSecurityProgress) || activeSecurityDetails === 'checkPath';
}
