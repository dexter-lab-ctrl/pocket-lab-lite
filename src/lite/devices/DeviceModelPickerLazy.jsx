import React, { useMemo } from 'react';
import { Check, Search, Smartphone } from 'lucide-react';
import { LiteSheet } from '../LiteOverlay.jsx';
import { LiteButton } from '../LiteUi.jsx';
import { liteApi } from '../../lib/liteApi.js';
import { suggestedAndroidDeviceModels } from '../../data/androidDeviceModels.js';
import { useLiteMutation, getLiteDeviceActionInvalidations } from '../../hooks/useLiteMutation.js';
import { useLiteDeviceModelFlow } from '../../hooks/useLiteDeviceModelFlow.js';
import { useLiteUiStore } from '../../stores/liteUiStore.js';

function vibrate(pattern = 12) {
  try { navigator?.vibrate?.(pattern); } catch { /* best effort */ }
}

export default function DeviceModelPickerLazy({ device, open, onClose, backendReachable = true, savedStateOnly = false }) {
  const search = useLiteUiStore((state) => state.deviceModelSearch);
  const setSearch = useLiteUiStore((state) => state.setDeviceModelSearch);
  const profile = device?.system_profile || {};
  const current = profile.consumer_model_name || '';
  const isProtectedServer = Boolean(device?.protected_server_host || device?.role === 'server_host' || device?.is_current || device?.isCurrent);
  const flow = useLiteDeviceModelFlow({ open, deviceId: device?.id, current, backendReachable, savedStateOnly });
  const suggestions = useMemo(() => suggestedAndroidDeviceModels(profile, search), [profile, search]);
  const mutation = useLiteMutation({
    mutationFn: ({ deviceId, consumerModelName, expectedProfileRevision, expectedConsumerModelName }) => liteApi.updateDeviceDisplayModel(
      deviceId,
      consumerModelName,
      expectedProfileRevision,
      expectedConsumerModelName,
    ),
    invalidateOnSuccess: true,
    invalidateForAction: (_variables, result) => getLiteDeviceActionInvalidations('update_device_model', result),
  });

  async function save() {
    flow.confirm();
    try {
      const result = await mutation.run({
        deviceId: device?.id,
        consumerModelName: flow.confirmed,
        expectedProfileRevision: Number(profile.revision || 0),
        expectedConsumerModelName: current,
      });
      flow.succeeded(result?.system_profile?.consumer_model_name || '');
      vibrate([12, 35, 12]);
    } catch (error) {
      flow.failed(error);
      vibrate(40);
    }
  }

  const isConfirming = flow.state === 'confirming' || flow.state === 'saving';
  return (
    <LiteSheet
      open={open}
      onClose={onClose}
      title={isProtectedServer ? "Choose server model" : "Choose phone model"}
      eyebrow={isProtectedServer ? "Pocket Lab server" : "Device details"}
      description="This label is display-only. Enrollment identity, technical model, internal codename, and server protection stay unchanged."
      className="lite-device-model-sheet"
      bodyClassName="lite-device-model-sheet-body"
      variant="manage"
      motion="safe-grip"
    >
      <div className="lite-device-model-identity">
        <Smartphone className="h-5 w-5" />
        <div>
          <strong>{profile.display_model || profile.technical_model || device?.name || 'Device'}</strong>
          <span>{[profile.manufacturer, profile.technical_model, profile.device_codename].filter(Boolean).join(' · ') || 'Technical details unavailable'}</span>
        </div>
      </div>

      {isConfirming ? (
        <div className="lite-device-model-confirmation">
          <span>Confirm display model</span>
          <strong>{flow.confirmed || 'Use technical model'}</strong>
          <p>
            This changes only the friendly model shown in Pocket Lab Lite.
            {isProtectedServer && profile.technical_model ? ` Technical model ${profile.technical_model}` : ''}
            {isProtectedServer && profile.device_codename ? ` and internal codename ${profile.device_codename}` : ''}
            {isProtectedServer ? ' remain unchanged.' : ''}
          </p>
          <div className="lite-device-model-actions">
            <LiteButton onClick={save} disabled={mutation.isPending || flow.writeBlocked}>
              <Check className="h-4 w-4" />
              {mutation.isPending ? 'Saving…' : 'Save model'}
            </LiteButton>
            <LiteButton tone="secondary" onClick={flow.edit} disabled={mutation.isPending}>Back</LiteButton>
          </div>
        </div>
      ) : (
        <>
          <label className="lite-device-model-search">
            <Search className="h-4 w-4" />
            <input
              value={search}
              onChange={(event) => { setSearch(event.target.value); flow.change(event.target.value); }}
              placeholder="Search Samsung, Pixel, model number…"
              maxLength={80}
            />
          </label>
          <div className="lite-device-model-list" role="listbox" aria-label="Phone model suggestions">
            {suggestions.map((entry) => (
              <button
                key={entry.consumerModelName}
                type="button"
                className="lite-device-model-option"
                onClick={() => { flow.review(entry.consumerModelName); vibrate(); }}
                disabled={flow.writeBlocked}
              >
                <span>{entry.manufacturer}</span>
                <strong>{entry.consumerModelName}</strong>
                {entry.score >= 80 ? <small>Suggested from technical details</small> : null}
              </button>
            ))}
          </div>
          <div className="lite-device-model-custom">
            <span>Other / Custom name</span>
            <div className="lite-device-model-actions">
              <LiteButton
                tone="secondary"
                onClick={() => flow.review(search)}
                disabled={!search.trim() || flow.writeBlocked}
              >Use “{search.trim() || 'custom name'}”</LiteButton>
              <LiteButton tone="secondary" onClick={flow.clear} disabled={!current || flow.writeBlocked}>Use detected technical model</LiteButton>
            </div>
          </div>
        </>
      )}

      {flow.writeBlocked ? <p className="lite-device-model-warning">Reconnect to change this device model. Saved state stays read-only.</p> : null}
      {flow.failureReason || mutation.error ? <p className="lite-device-model-error">{flow.failureReason || mutation.error?.message}</p> : null}
      {flow.state === 'succeeded' ? <p className="lite-device-model-success">Device model updated.</p> : null}
    </LiteSheet>
  );
}

export const DEVICE_MODEL_PICKER_NEVER_CHANGES_DEVICE_IDENTITY = true;
