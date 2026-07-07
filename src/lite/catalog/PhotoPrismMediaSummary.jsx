import React from 'react';
import { FolderOpen } from 'lucide-react';

export default function PhotoPrismMediaSummary({ title = 'Media folders', summary = 'No folders connected', children }) {
  return (
    <div className="lite-catalog-storage-panel lite-catalog-storage-panel--sheet">
      <div className="lite-catalog-storage-head">
        <div>
          <span>{title}</span>
          <strong>{summary}</strong>
        </div>
        <FolderOpen className="h-5 w-5" />
      </div>
      {children}
    </div>
  );
}
