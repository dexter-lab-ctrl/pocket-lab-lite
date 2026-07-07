import React from 'react';
import { GlassCard } from '../LiteUi.jsx';

export default function AppSummaryCard({ children, className = '', ...props }) {
  return (
    <GlassCard className={`lite-catalog-card lite-catalog-app-card ${className}`.trim()} {...props}>
      {children}
    </GlassCard>
  );
}
