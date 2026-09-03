const HELP = {
  'identity.overview': {
    title: 'Your Identity & Access overview',
    simple: 'This area tells you who Pocket Lab believes you are, how you signed in, and what level of access the server currently gives you.',
    why: 'Identity is checked before protected changes. The browser cannot grant itself a role or stronger access.',
    next: 'Review anything marked Needs attention, then use Manage access for passkeys, sessions and recovery.',
    technical: 'The values come from the signed-in server session plus the server-resolved Enterprise membership when Enterprise Mode is enabled.',
  },
  'identity.passkeys': {
    title: 'Passkeys',
    simple: 'A passkey lets you sign in and confirm sensitive changes using your device security instead of sending a reusable secret.',
    why: 'Pocket Lab uses passkeys for phishing-resistant sign-in and short-lived step-up confirmation.',
    next: 'Keep at least one working passkey and a recovery method. Give each passkey a recognizable name.',
  },
  'identity.sessions': {
    title: 'Sessions',
    simple: 'A session is a browser or device that is currently signed in as you.',
    why: 'Removing a session signs out that browser without exposing its cookie or token.',
    next: 'Sign out sessions you do not recognize or no longer use.',
  },
  'identity.recovery': {
    title: 'Recovery',
    simple: 'Recovery codes are one-time backup codes for regaining access when your normal sign-in method is unavailable.',
    why: 'Generating a new set invalidates the old set. Pocket Lab never shows stored recovery secrets later.',
    next: 'Save new codes somewhere private when they are shown.',
  },
  'identity.people': {
    title: 'People',
    simple: 'People are separate human identities. Each person has their own passkeys, sessions, recovery state and Enterprise role.',
    why: 'Separate identities make delegated administration and trustworthy audit history possible.',
    next: 'Use Add person to create a short-lived one-time connect link, then share it privately with that person.',
    technical: 'Raw enrollment claims are shown only at creation. The database stores only a hash and bounded enrollment metadata.',
  },
  'identity.roles': {
    title: 'Roles & access',
    simple: 'Roles describe the kind of work a person may perform. Safety Rules can add confirmation, step-up or independent review to protected actions.',
    why: 'Both Identity and Rules use the same server-owned capability projection, so their explanations stay synchronized.',
    next: 'Use the role matrix to understand effective authority before changing a person’s role.',
  },
  'identity.mode': {
    title: 'Personal and Enterprise Mode',
    simple: 'Personal Mode is optimized for one local Owner. Enterprise Mode adds separate people, roles, policy governance, requests and temporary access.',
    why: 'Changing modes changes authorization for the whole workspace, so Pocket Lab previews the impact and signs out active sessions.',
    next: 'Review the impact before switching. Your Enterprise memberships are retained if you return to Personal Mode.',
  },
  'identity.owner': {
    title: 'Owner authority',
    simple: 'Owner is Pocket Lab’s root-equivalent human role. An Owner does not need another person to approve supported administrative actions.',
    why: 'Owner authority removes topology deadlocks while hard safety checks, explicit confirmation, passkey step-up and audit evidence remain in force.',
    next: 'Use Owner access carefully. Protected Server Host and policy-consistency guards are never bypassed.',
  },
  'rules.protection': {
    title: 'Protection',
    simple: 'Protection explains how the current Safety Rules treat each supported action for each role.',
    why: 'It answers “what can this role do?” and “will it need review?” without exposing raw policy internals.',
    next: 'Check this matrix before delegating a role or changing Rules.',
  },
  'rules.policies': {
    title: 'Rules policies',
    simple: 'A Rules revision is an immutable, validated version of the typed governance settings.',
    why: 'Editing creates a candidate only. It does not change the running policy until an Owner confirms activation and the supervisor proves the new runtime revision.',
    next: 'Draft, validate, compare, then activate. Restore known-good Rules if the active revision must be recovered.',
    technical: 'The browser never edits free-form Rego and never changes OPA pointers. FastAPI records lifecycle intent; the supervisor owns activation and proof.',
  },
  'rules.simulation': {
    title: 'Test a change',
    simple: 'Simulation asks Safety Rules what would happen without executing the real action.',
    why: 'It is useful for understanding role behavior and candidate policy changes safely.',
    next: 'Choose a supported action, target and context. Treat the result as policy evidence, not proof that a real operation completed.',
  },
  'rules.decisions': {
    title: 'Decisions',
    simple: 'Each protected action produces a bounded Rules decision explaining whether it was allowed, blocked or required another step.',
    why: 'Decision history helps explain what happened without exposing raw credentials, tokens or complete policy input.',
    next: 'Open Details when you need the exact reason code, revision and constraints.',
  },
  'rules.requests': {
    title: 'Review requests',
    simple: 'A request is a short-lived independent review for a protected action started by an Admin or Operator.',
    why: 'Owner actions do not need peer approval. Admin and Operator actions can require another eligible Owner or Admin depending on current Rules.',
    next: 'Approving changes approval state only. The original requester must retry the exact protected action.',
  },
  'rules.exceptions': {
    title: 'Temporary access',
    simple: 'Temporary access is a narrow, expiring exception for one person, app, device and current Rules revision.',
    why: 'It avoids broad permanent policy changes during a short operational need.',
    next: 'Always give a clear reason and revoke the exception early when it is no longer needed.',
  },
  'rules.activity': {
    title: 'Rules activity',
    simple: 'Activity brings together recent policy decisions, requests and governance changes as sanitized evidence.',
    why: 'It helps technical and non-technical users understand what changed and what action is still needed.',
    next: 'Use the specific Protection, Policies, Requests or Temporary access section when an event needs follow-up.',
  },
  'rules.owner': {
    title: 'Owner in Safety Rules',
    simple: 'Owner has complete supported Pocket Lab authority and does not wait for another human approval.',
    why: 'This mirrors root administration while still requiring every normal safety invariant such as confirmed targets, valid Rules state and protected-host checks.',
    next: 'For root-level Rules activation, rollback and workspace mode changes, Pocket Lab also requires recent passkey confirmation.',
  },
};

export function getLiteHelpContent(key, fallback = {}) {
  return HELP[key] || {
    title: fallback.title || 'About this control',
    simple: fallback.simple || 'This control is part of Pocket Lab Lite and is verified by the server before protected changes are accepted.',
    why: fallback.why || 'Pocket Lab keeps authority and execution on the server rather than in the browser.',
    next: fallback.next || 'Follow the on-screen status and wait for a server-confirmed result.',
    technical: fallback.technical || '',
  };
}

export const LITE_HELP_KEYS = Object.freeze(Object.keys(HELP));
