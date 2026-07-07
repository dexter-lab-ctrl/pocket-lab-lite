import React from 'react';

export default function AppStatusChips({ chips = [], className = '' }) {
  const visible = (Array.isArray(chips) ? chips : []).filter(Boolean);
  if (!visible.length) return null;
  return (
    <div className={`lite-catalog-status-chips ${className}`.trim()}>
      {visible.map((chip) => (
        <span key={chip.key || chip.label || chip}>{chip.icon || null}{chip.label || chip}</span>
      ))}
    </div>
  );
}
