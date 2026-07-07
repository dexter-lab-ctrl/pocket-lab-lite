import React from 'react';
import LiteActionProgress from '../LiteActionProgress.jsx';
import { LiteProgressMorphPanel } from '../LiteMotion.jsx';

export default function AppActionProgressSlot({
  active,
  motionKey,
  actionId,
  status,
  enabled,
  disabledReason,
  progress,
  result,
  detailsAvailable,
  lastResult,
  firstRanAt,
  lastRanAt,
  runCount,
  troubleshooting,
  evidenceRef,
  receiptId,
  executionOwner,
}) {
  if (!active) return null;
  return (
    <LiteProgressMorphPanel
      active={active}
      className="lite-app-action-progress-motion"
      motionKey={motionKey}
    >
      <LiteActionProgress
        actionId={actionId}
        status={status}
        enabled={enabled}
        disabledReason={disabledReason}
        progress={progress}
        result={result}
        detailsAvailable={detailsAvailable}
        lastResult={lastResult}
        firstRanAt={firstRanAt}
        lastRanAt={lastRanAt}
        runCount={runCount}
        troubleshooting={troubleshooting}
        evidenceRef={evidenceRef}
        receiptId={receiptId}
        executionOwner={executionOwner}
      />
    </LiteProgressMorphPanel>
  );
}
