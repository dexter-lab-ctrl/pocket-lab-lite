import './liteHelp.css';
import React from 'react';
import { CircleHelp, Info } from 'lucide-react';
import { getLiteHelpContent } from '../lib/liteHelpContent.js';
import { LiteSheet } from './LiteOverlay.jsx';

export default function LiteHelp({ helpKey, fallback = {}, label = '', className = '' }) {
  const [open, setOpen] = React.useState(false);
  const help = getLiteHelpContent(helpKey, fallback);
  const accessibleLabel = label || `Help: ${help.title}`;
  return (
    <>
      <button
        type="button"
        className={`lite-help-trigger ${className}`.trim()}
        onClick={(event) => { event.stopPropagation(); setOpen(true); }}
        aria-label={accessibleLabel}
        title={accessibleLabel}
        data-lite-help-key={helpKey}
      >
        <CircleHelp className="h-4 w-4" aria-hidden="true" />
      </button>
      <LiteSheet
        open={open}
        onClose={() => setOpen(false)}
        eyebrow="Help"
        title={help.title}
        description={help.simple}
        className="lite-help-sheet"
        bodyClassName="lite-help-sheet-body"
      >
        <div className="lite-help-story">
          <div className="lite-help-story-row">
            <Info className="h-5 w-5" aria-hidden="true" />
            <div><strong>Why it matters</strong><p>{help.why}</p></div>
          </div>
          <div className="lite-help-story-row">
            <span className="lite-help-step" aria-hidden="true">→</span>
            <div><strong>What to do</strong><p>{help.next}</p></div>
          </div>
          {help.technical ? (
            <details className="lite-help-technical">
              <summary>Technical detail</summary>
              <p>{help.technical}</p>
            </details>
          ) : null}
        </div>
      </LiteSheet>
    </>
  );
}

export function LiteHelpHeading({ title, helpKey, fallback, as: Component = 'h3', className = '' }) {
  return (
    <div className={`lite-help-heading ${className}`.trim()}>
      <Component>{title}</Component>
      <LiteHelp helpKey={helpKey} fallback={fallback} />
    </div>
  );
}

export const LITE_CONTEXT_HELP_READY = true;
