import React from 'react';

const STAGES = ['Check', 'Download', 'Verify', 'Apply', 'Restart', 'Complete'];
const EVIDENCE = {
  Check: 'release candidate found',
  Download: 'artifact fetched',
  Verify: 'signature checked',
  Apply: 'rollback point created',
  Restart: 'service restart tracked',
  Complete: 'audit recorded',
};

export default function ReleaseConveyor({ activeStage = 0, simpleMode = false, enterpriseMode = false, className = '' }) {
  const safeStage = Math.max(0, Math.min(STAGES.length - 1, Number(activeStage) || 0));
  return (
    <div className={`release-conveyor ${className}`} aria-label={simpleMode ? 'Update progress' : 'Release workflow conveyor'}>
      {STAGES.map((stage, index) => {
        const complete = index < safeStage;
        const active = index === safeStage;
        return (
          <div key={stage} className={`release-conveyor-stage ${complete ? 'release-conveyor-stage-complete' : ''} ${active ? 'release-conveyor-stage-active' : ''}`}>
            <div className="release-conveyor-fill" />
            <span className="release-conveyor-label">{stage}</span>
            {enterpriseMode || !simpleMode ? <small>{EVIDENCE[stage]}</small> : null}
          </div>
        );
      })}
    </div>
  );
}
