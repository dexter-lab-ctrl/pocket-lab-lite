import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'A UI section failed to render.',
    };
  }

  componentDidCatch(error, info) {
    if (typeof console !== 'undefined') {
      console.error('Pocket Lab UI section failed to render', error, info);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="mb-4 rounded-[2rem] border border-amber-500/30 bg-amber-500/10 p-5 text-amber-100">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/15 p-2">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-80">UI section isolated</p>
              <h3 className="mt-1 text-lg font-black">This panel could not be rendered safely</h3>
              <p className="mt-1 text-sm opacity-90">
                Pocket Lab kept the rest of the app running. Refresh this section after checking the latest backend payload.
              </p>
              {this.state.message ? <p className="mt-2 text-xs opacity-80">{this.state.message}</p> : null}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
