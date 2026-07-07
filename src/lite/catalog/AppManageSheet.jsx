import React from 'react';

export default function AppManageSheet({ children, className = '', ...props }) {
  return (
    <section className={`lite-catalog-manage-sheet ${className}`.trim()} {...props}>
      {children}
    </section>
  );
}
