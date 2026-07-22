import React from 'react';
import { RefreshCw, WifiOff } from 'lucide-react';
import { GlassCard, LiteButton } from './LiteUi.jsx';
import { createLiteChunkRecoveryController, isLiteChunkLoadError } from './liteNavigationRuntime.js';

const BUILD_ID = import.meta.env.VITE_POCKETLAB_BUILD_ID || 'development';
const chunkRecovery = createLiteChunkRecoveryController({ buildId: BUILD_ID });

export function LiteScreenLoading({ label = 'Pocket Lab', intrinsicSize = '48rem' }) {
  return (
    <div
      className="lite-screen-loading"
      style={{ '--lite-screen-intrinsic-size': intrinsicSize }}
      role="status"
      aria-live="polite"
      aria-label={`Loading ${label}`}
    >
      <div className="lite-screen-loading-copy">
        <span className="lite-screen-loading-dot" aria-hidden="true" />
        <strong>Opening {label}</strong>
        <p>The Pocket Lab shell and saved state remain available.</p>
      </div>
      <div className="lite-screen-loading-block" aria-hidden="true" />
      <div className="lite-screen-loading-block lite-screen-loading-block-short" aria-hidden="true" />
    </div>
  );
}

export class LiteScreenErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false, autoRecoveryStarted: false, chunkFailure: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    const chunkFailure = isLiteChunkLoadError(error);
    const autoRecoveryStarted = chunkFailure && chunkRecovery.attempt(error);
    this.setState({ autoRecoveryStarted, chunkFailure });
    console.warn('[Pocket Lab Lite] A screen was safely isolated.', {
      screenId: this.props.screenId || 'unknown',
      failureType: chunkFailure ? 'chunk_load' : 'screen_render',
    });
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <GlassCard className="lite-screen-error-card" role="alert">
        <div className="lite-devices-mini-icon"><WifiOff className="h-5 w-5" /></div>
        <h1>{this.state.autoRecoveryStarted ? 'Refreshing Pocket Lab' : `${this.props.label || 'This section'} needs a moment`}</h1>
        <p>
          {this.state.autoRecoveryStarted
            ? 'Pocket Lab detected an updated app file and is refreshing once.'
            : 'This section was safely contained. Other Pocket Lab tabs are still available.'}
        </p>
        {!this.state.autoRecoveryStarted ? (
          <LiteButton onClick={this.props.onRetry} tone="secondary">
            <RefreshCw className="h-4 w-4" /> Retry section
          </LiteButton>
        ) : null}
        {this.state.chunkFailure && !this.state.autoRecoveryStarted ? (
          <small>Refresh the app if a newer Pocket Lab version was installed.</small>
        ) : null}
      </GlassCard>
    );
  }
}
