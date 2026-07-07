import React from 'react';

export default function AppManageSections({ children, className = '' }) {
  return <div className={`lite-catalog-manage-sections ${className}`.trim()}>{children}</div>;
}
