import React, { useEffect, useMemo, useRef, useState } from 'react';
import { LiteSheet } from '../LiteOverlay.jsx';
import './liteQuickNavigate.css';

export function shouldOpenLiteQuickNavigate(event) {
  if (!event || event.defaultPrevented || event.repeat || event.isComposing || event.altKey || event.shiftKey) return false;
  if (!(event.ctrlKey || event.metaKey) || String(event.key).toLowerCase() !== 'k') return false;
  const node = event.target;
  if (node?.closest?.('input, textarea, select, [contenteditable="true"], [role="textbox"]')) return false;
  return true;
}
export function filterLiteNavigation(items, query) {
  const q = String(query || '').trim().toLocaleLowerCase();
  return (Array.isArray(items) ? items : []).filter((item) =>
    item?.id && item?.label && (!q || String(item.label).toLocaleLowerCase().includes(q))
  );
}
/** Navigation only; never dispatches backend commands or interprets role authority. */
export default function LiteQuickNavigate({ open, onClose, onNavigate, items = [], activeId = '' }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  const matches = useMemo(() => filterLiteNavigation(items, query), [items, query]);
  useEffect(() => {
    if (!open) { setQuery(''); return undefined; }
    const id = window.requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }));
    return () => window.cancelAnimationFrame(id);
  }, [open]);
  const select = (id) => { onClose?.(); onNavigate?.(id); };
  return (
    <LiteSheet open={open} onClose={onClose} title="Go to a section" eyebrow="Quick navigation" description="Find a Pocket Lab section. No actions run from here." variant="manage" className="lite-p3-command-surface" bodyClassName="lite-p3-command-body">
      <label className="lite-p3-command-label" htmlFor="lite-p3-command-search">Find a section</label>
      <input ref={inputRef} id="lite-p3-command-search" type="search" autoComplete="off" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Home, Apps, Devices…" aria-controls="lite-p3-command-options" onKeyDown={(event) => {
        if (event.key === 'Enter' && matches[0]) { event.preventDefault(); select(matches[0].id); }
      }} />
      <div id="lite-p3-command-options" className="lite-p3-command-options" role="group" aria-label="Sections">
        {matches.map((item) => {
          const Icon = item.icon;
          return <button type="button" key={item.id} onClick={() => select(item.id)} aria-current={item.id === activeId ? 'page' : undefined}>
            {Icon ? <Icon className="h-4 w-4" aria-hidden="true" /> : null}<span>{item.label}</span>{item.id === activeId ? <small>Current</small> : null}
          </button>;
        })}
        {!matches.length ? <p role="status">No matching section. Try another name.</p> : null}
      </div>
    </LiteSheet>
  );
}
