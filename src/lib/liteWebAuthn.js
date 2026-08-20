function decodeBase64Url(value = '') {
  const text = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
  const padded = text + '='.repeat((4 - (text.length % 4 || 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes.buffer;
}

function encodeBase64Url(value) {
  const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : new Uint8Array(value?.buffer || value || []);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function registrationOptions(options = {}) {
  const publicKey = { ...(options.publicKey || options) };
  publicKey.challenge = decodeBase64Url(publicKey.challenge);
  if (publicKey.user?.id) publicKey.user = { ...publicKey.user, id: decodeBase64Url(publicKey.user.id) };
  if (Array.isArray(publicKey.excludeCredentials)) {
    publicKey.excludeCredentials = publicKey.excludeCredentials.map((item) => ({ ...item, id: decodeBase64Url(item.id) }));
  }
  return publicKey;
}

function authenticationOptions(options = {}) {
  const publicKey = { ...(options.publicKey || options) };
  publicKey.challenge = decodeBase64Url(publicKey.challenge);
  if (Array.isArray(publicKey.allowCredentials)) {
    publicKey.allowCredentials = publicKey.allowCredentials.map((item) => ({ ...item, id: decodeBase64Url(item.id) }));
  }
  return publicKey;
}

function credentialEnvelope(credential) {
  return {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment || null,
    clientExtensionResults: credential.getClientExtensionResults?.() || {},
  };
}

export function webAuthnAvailable() {
  return typeof window !== 'undefined' && window.isSecureContext && Boolean(window.PublicKeyCredential && navigator.credentials);
}

export async function createLitePasskey(options = {}) {
  if (!webAuthnAvailable()) throw new Error('Passkeys need HTTPS and a browser with WebAuthn support. Use Advanced setup instead.');
  const credential = await navigator.credentials.create({ publicKey: registrationOptions(options) });
  if (!credential) throw new Error('Passkey setup was cancelled.');
  const response = credential.response;
  return {
    ...credentialEnvelope(credential),
    clientDataJSON: encodeBase64Url(response.clientDataJSON),
    attestationObject: encodeBase64Url(response.attestationObject),
    transports: response.getTransports?.() || [],
  };
}

export async function getLitePasskey(options = {}) {
  if (!webAuthnAvailable()) throw new Error('Passkeys need HTTPS and a browser with WebAuthn support. Use Advanced sign-in instead.');
  const credential = await navigator.credentials.get({ publicKey: authenticationOptions(options) });
  if (!credential) throw new Error('Passkey verification was cancelled.');
  const response = credential.response;
  return {
    ...credentialEnvelope(credential),
    clientDataJSON: encodeBase64Url(response.clientDataJSON),
    authenticatorData: encodeBase64Url(response.authenticatorData),
    signature: encodeBase64Url(response.signature),
    userHandle: response.userHandle ? encodeBase64Url(response.userHandle) : null,
  };
}
