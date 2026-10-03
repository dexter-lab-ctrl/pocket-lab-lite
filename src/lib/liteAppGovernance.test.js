import { describe, expect, it } from 'vitest';

import { getLiteAppActionInvalidations } from '../hooks/useLiteMutation.js';
import { liteQueryKeys } from './liteQueryClient.js';
import { selectAppResourceView } from './liteViewModels.js';

function hasKey(keys, wanted) {
  return keys.some((key) => JSON.stringify(key) === JSON.stringify(wanted));
}

describe('Universal app governance projection', () => {
  it('keeps app authority capability-aware and secret-free', () => {
    const view = selectAppResourceView({
      resource_type: 'app',
      app_id: 'example-app',
      app_label: 'Example App',
      authority: {
        mode: 'enterprise',
        role: 'Operator',
        summary: 'Access follows current Safety Rules.',
        actions: [
          { action_id: 'app.open', label: 'Open app', mode: 'allow', allowed: true, required_capability: 'open' },
          { action_id: 'app.install', label: 'Install app', mode: 'temporary_access', allowed: false, requires_temporary_access: true, temporary_access_supported: true, required_capability: 'install' },
        ],
      },
      credentials: {
        credential_required: true,
        configured: false,
        missing: true,
        needs_rotation: false,
        credentials: [{
          credential_id: 'app_sign_in',
          label: 'App sign-in',
          purpose: 'interactive_app_access',
          required: true,
          management: 'external_or_manual',
          status: 'missing',
          password: 'must-not-project',
          token: 'must-not-project',
        }],
      },
      recovery: {
        backup_supported: true,
        restore_preview_supported: true,
        restore_apply_supported: false,
        protected_user_data_excluded: true,
        credential_rebinding_required: true,
        recovery_ready: false,
        recovery_blockers: ['Storage target is unavailable.'],
      },
    });

    expect(view.app_id).toBe('example-app');
    expect(view.authority.actions.find((item) => item.action_id === 'app.install')).toMatchObject({
      allowed: false,
      requires_temporary_access: true,
    });
    expect(view.credential_status.items[0]).not.toHaveProperty('password');
    expect(view.credential_status.items[0]).not.toHaveProperty('token');
    expect(view.credential_status.secret_values_exposed).toBe(false);
    expect(view.recovery.restore_apply_supported).toBe(false);
    expect(view.recovery.protected_user_data_excluded).toBe(true);
  });

  it('invalidates only app and affected cross-feature projections', () => {
    const backup = getLiteAppActionInvalidations('example-app', 'backup_app', {});
    expect(hasKey(backup, liteQueryKeys.appActions('example-app'))).toBe(true);
    expect(hasKey(backup, liteQueryKeys.appResource('example-app'))).toBe(true);
    expect(hasKey(backup, liteQueryKeys.appRecovery('example-app'))).toBe(true);
    expect(hasKey(backup, liteQueryKeys.recoveryDetails())).toBe(true);
    expect(hasKey(backup, liteQueryKeys.fleet())).toBe(false);

    const security = getLiteAppActionInvalidations('example-app', 'check_app', {});
    expect(hasKey(security, liteQueryKeys.security())).toBe(true);
    expect(hasKey(security, liteQueryKeys.securityProfile('app', 'example-app'))).toBe(true);
    expect(hasKey(security, liteQueryKeys.recoveryDetails())).toBe(false);
  });
});
