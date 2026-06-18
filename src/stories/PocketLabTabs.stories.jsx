import React from 'react';
import metadata from './tier9UiScreens.json';
import { withPocketLabStoryMocks } from './pocketlabTier9MockApi.js';
import AppStoreTab from '../tabs/AppStoreTab.jsx';
import GitOpsTab from '../tabs/GitOpsTab.jsx';
import FleetScalingTab from '../tabs/FleetScalingTab.jsx';
import IdentityVaultTab from '../tabs/IdentityVaultTab.jsx';
import ReleaseWorkflowTab from '../tabs/ReleaseWorkflowTab.jsx';
import DriftCenterTab from '../tabs/DriftCenterTab.jsx';
import SecurityPostureTab from '../tabs/SecurityPostureTab.jsx';
import NocTelemetryTab from '../tabs/NocTelemetryTab.jsx';
import DisasterRecoveryTab from '../tabs/DisasterRecoveryTab.jsx';
import PolicyGuardrailsTab from '../tabs/PolicyGuardrailsTab.jsx';
import SettingsTab from '../tabs/SettingsTab.jsx';

const ScreenFrame = ({ children, simple = false }) => (
  <div className={`theme-control-plane-graphite ${simple ? 'theme-midnight-saas-simple' : ''} min-h-screen bg-slate-950 p-4 text-slate-100`}>
    {children}
  </div>
);

const screenById = Object.fromEntries(metadata.screens.map((screen) => [screen.id, screen]));

function params(screenId, state, scenario = 'normal') {
  const screen = screenById[screenId];
  return {
    layout: 'fullscreen',
    pocketlab: {
      tier: metadata.capability || metadata.tier,
      screenId,
      scenario,
      state,
      professionalLabel: screen.professionalLabel,
      simpleLabel: screen.simpleLabel,
      operations: screen.operations,
      backendEndpoints: screen.backendEndpoints,
    },
    docs: {
      description: {
        story: `${screen.professionalLabel}: ${screen.states[state] || screen.purpose}`,
      },
    },
  };
}

export default {
  title: 'Pocket Lab/UI Evidence Screens',
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Generated Storybook UI documentation stories for Pocket Lab tabs. Stories use a deterministic FastAPI mock and never talk directly to NATS or execute shell commands.',
      },
    },
  },
  decorators: [withPocketLabStoryMocks],
};

export const AppStoreNormal = {
  name: 'App Store / Normal',
  render: () => <ScreenFrame><AppStoreTab /></ScreenFrame>,
  parameters: params('app-store', 'normal'),
};

export const AppStoreSimpleMode = {
  name: 'Apps & Services / Simple Mode',
  render: () => <ScreenFrame simple><AppStoreTab simpleMode /></ScreenFrame>,
  parameters: params('app-store', 'simple_mode'),
};

export const AppStoreEmptyState = {
  name: 'App Store / Empty state',
  render: () => <ScreenFrame><AppStoreTab /></ScreenFrame>,
  parameters: params('app-store', 'empty', 'empty'),
};

export const AppStoreDegradedWriteBlocked = {
  name: 'App Store / Degraded write blocked',
  render: () => <ScreenFrame simple><AppStoreTab simpleMode /></ScreenFrame>,
  parameters: params('app-store', 'degraded', 'degraded'),
};

export const GitOpsProfessional = {
  name: 'GitOps / Professional Mode',
  render: () => <ScreenFrame><GitOpsTab /></ScreenFrame>,
  parameters: params('gitops', 'professional_mode'),
};

export const GitOpsSimpleMode = {
  name: 'Keep My Environment Updated / Simple Mode',
  render: () => <ScreenFrame simple><GitOpsTab simpleMode /></ScreenFrame>,
  parameters: params('gitops', 'simple_mode'),
};

export const GitOpsApprovalRequired = {
  name: 'GitOps / Approval required',
  render: () => <ScreenFrame><GitOpsTab /></ScreenFrame>,
  parameters: params('gitops', 'permission_or_approval_required', 'approval-required'),
};

export const GitOpsFailedOperation = {
  name: 'GitOps / Failed operation',
  render: () => <ScreenFrame><GitOpsTab /></ScreenFrame>,
  parameters: params('gitops', 'failed_operation', 'failed-operation'),
};

export const FleetNormal = {
  name: 'Fleet Scaling / Normal',
  render: () => <ScreenFrame><FleetScalingTab /></ScreenFrame>,
  parameters: params('fleet-scaling', 'normal'),
};

export const FleetSimpleMode = {
  name: 'My Devices / Simple Mode',
  render: () => <ScreenFrame simple><FleetScalingTab simpleMode /></ScreenFrame>,
  parameters: params('fleet-scaling', 'simple_mode'),
};

export const FleetEmptyAgents = {
  name: 'Fleet Scaling / Empty agents',
  render: () => <ScreenFrame><FleetScalingTab /></ScreenFrame>,
  parameters: params('fleet-scaling', 'empty', 'empty'),
};

export const FleetDegraded = {
  name: 'Fleet Scaling / Degraded',
  render: () => <ScreenFrame simple><FleetScalingTab simpleMode /></ScreenFrame>,
  parameters: params('fleet-scaling', 'degraded', 'degraded'),
};

export const IdentityVaultNormal = {
  name: 'Identity & Vault / Normal',
  render: () => <ScreenFrame><IdentityVaultTab /></ScreenFrame>,
  parameters: params('identity-vault', 'normal'),
};

export const IdentityVaultSimpleMode = {
  name: 'Passwords & Access / Simple Mode',
  render: () => <ScreenFrame simple><IdentityVaultTab simpleMode /></ScreenFrame>,
  parameters: params('identity-vault', 'simple_mode'),
};

export const IdentityVaultSuccess = {
  name: 'Identity & Vault / Success state',
  render: () => <ScreenFrame><IdentityVaultTab /></ScreenFrame>,
  parameters: params('identity-vault', 'success', 'success'),
};

export const IdentityVaultFailedOperation = {
  name: 'Identity & Vault / Failed operation',
  render: () => <ScreenFrame simple><IdentityVaultTab simpleMode /></ScreenFrame>,
  parameters: params('identity-vault', 'failed_operation', 'failed-operation'),
};

export const ReleaseWorkflowNormal = {
  name: 'Release Workflow / Normal',
  render: () => <ScreenFrame><ReleaseWorkflowTab /></ScreenFrame>,
  parameters: params('release-workflow', 'normal'),
};

export const ReleaseWorkflowSimpleMode = {
  name: 'Release / Simple Mode',
  render: () => <ScreenFrame simple><ReleaseWorkflowTab simpleMode /></ScreenFrame>,
  parameters: params('release-workflow', 'simple_mode'),
};

export const ReleaseWorkflowLoading = {
  name: 'Release Workflow / Loading',
  render: () => <ScreenFrame><ReleaseWorkflowTab /></ScreenFrame>,
  parameters: params('release-workflow', 'loading', 'loading'),
};

export const ReleaseWorkflowError = {
  name: 'Release Workflow / Error',
  render: () => <ScreenFrame><ReleaseWorkflowTab /></ScreenFrame>,
  parameters: params('release-workflow', 'error', 'error'),
};

export const DriftCenterNormal = {
  name: 'Drift Center / Normal',
  render: () => <ScreenFrame><DriftCenterTab /></ScreenFrame>,
  parameters: params('drift-center', 'normal'),
};

export const DriftCenterSimpleMode = {
  name: 'Health & Issues / Simple Mode',
  render: () => <ScreenFrame simple><DriftCenterTab simpleMode /></ScreenFrame>,
  parameters: params('drift-center', 'simple_mode'),
};

export const DriftCenterPermissionRequired = {
  name: 'Drift Center / Permission required',
  render: () => <ScreenFrame><DriftCenterTab /></ScreenFrame>,
  parameters: params('drift-center', 'permission_or_approval_required', 'approval-required'),
};

export const DriftCenterFailedOperation = {
  name: 'Drift Center / Failed operation',
  render: () => <ScreenFrame simple><DriftCenterTab simpleMode /></ScreenFrame>,
  parameters: params('drift-center', 'failed_operation', 'failed-operation'),
};

export const SecurityPostureSimple = {
  name: 'Safety Center / Simple Mode',
  render: () => <ScreenFrame simple><SecurityPostureTab simpleMode /></ScreenFrame>,
  parameters: params('security-posture', 'simple_mode'),
};

export const NocTelemetryDegraded = {
  name: 'System Status / Degraded',
  render: () => <ScreenFrame simple><NocTelemetryTab simpleMode /></ScreenFrame>,
  parameters: params('noc-telemetry', 'degraded', 'degraded'),
};

export const DisasterRecoveryNormal = {
  name: 'Disaster Recovery / Normal',
  render: () => <ScreenFrame><DisasterRecoveryTab /></ScreenFrame>,
  parameters: params('disaster-recovery', 'normal'),
};

export const PolicyGuardrailsNormal = {
  name: 'Policy Guardrails / Normal',
  render: () => <ScreenFrame><PolicyGuardrailsTab /></ScreenFrame>,
  parameters: params('policy-guardrails', 'normal'),
};

export const SettingsEnterpriseGovernance = {
  name: 'Settings / Enterprise Governance',
  render: () => <ScreenFrame><SettingsTab /></ScreenFrame>,
  parameters: params('settings-governance', 'enterprise_mode', 'enterprise'),
};
