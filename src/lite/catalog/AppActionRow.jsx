import React from 'react';
import { StatusBadge, LiteButton } from '../LiteUi.jsx';
import { LiteElevationSurface } from '../LiteMotion.jsx';

function AppActionRow({
  actionId,
  className,
  disabled,
  active,
  icon,
  cue,
  eyebrow,
  label,
  summary,
  displayStatus,
  displayLabel,
  buttonTone,
  buttonLabel,
  buttonTitle,
  onClick,
  disabledReason,
  progressSlot,
  resultSlot,
}) {
  const isDisabled = Boolean(disabled);
  return (
    <LiteElevationSurface
      className={className}
      data-action-id={actionId}
      disabled={isDisabled}
      active={active}
      settle
    >
      <div className="lite-app-action-row-main">
        <span className="lite-catalog-action-tile-icon lite-app-action-row-icon">
          {icon}
          {cue}
        </span>
        <div className="lite-app-action-row-copy">
          <span>{eyebrow}</span>
          <strong>{label}</strong>
          <p>{summary}</p>
        </div>
      </div>
      <div className="lite-app-action-row-side">
        <StatusBadge status={displayStatus}>{displayLabel}</StatusBadge>
        <LiteButton
          tone={buttonTone}
          onClick={onClick}
          disabled={isDisabled}
          title={buttonTitle}
          haptic={!isDisabled}
        >
          {buttonLabel}
        </LiteButton>
      </div>
      {disabledReason}
      {progressSlot}
      {resultSlot}
    </LiteElevationSurface>
  );
}

export default React.memo(AppActionRow);
