import React from 'react';
import { DatabaseZap } from 'lucide-react';

const FLOW_NODES = ['Control API', 'Event Bus', 'Executor', 'Audit Events', 'UI'];

export default function JetStreamFlowLine({ activeIndex = 0, simpleMode = false, className = '' }) {
  const boundedIndex = Math.max(0, Math.min(activeIndex, FLOW_NODES.length - 1));
  return (
    <div className={`jetstream-flow-line ${className}`} aria-label="Pocket Lab command flow">
      <div className="jetstream-flow-header">
        <DatabaseZap className="h-4 w-4" />
        <span>{simpleMode ? 'Safe request path' : 'Control API → Event Bus → Executor trace'}</span>
      </div>
      <div className="jetstream-flow-track" aria-hidden="true">
        {FLOW_NODES.map((node, index) => (
          <React.Fragment key={node}>
            <div className={`jetstream-flow-node ${index <= boundedIndex ? 'jetstream-flow-node-active' : ''}`}>
              <span className="jetstream-flow-dot" />
              <span>{node}</span>
            </div>
            {index < FLOW_NODES.length - 1 ? <span className="jetstream-flow-segment" /> : null}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
