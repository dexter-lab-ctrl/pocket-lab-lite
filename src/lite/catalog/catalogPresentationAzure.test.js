import { describe, expect, it } from 'vitest';
import { catalogStateBucket, filterCatalogApps, sortCatalogApps } from './catalogPresentation.js';

const examples = [
  { id: 'ready', name: 'PhotoPrism', description: 'Private photos', status: 'installed_running', installed: true, access: { route_ready: true, open: true } },
  { id: 'starting', name: 'Starting app', status: 'installing' },
  { id: 'attention', name: 'Broken route', installed: true, status: 'installed_running', access: { route_ready: false } },
  { id: 'new', name: 'New app', status: 'not_installed', installed: false },
  { id: 'unknown', name: 'Unknown app', status: 'unknown' },
];

describe('Azure Apps capability-neutral catalog presentation', () => {
  it('keeps stable name and id ordering without mutating the source', () => {
    const input = [...examples].reverse();
    expect(sortCatalogApps(input).map((item) => item.id)).toEqual(['attention','new','ready','starting','unknown']);
    expect(input[0].id).toBe('unknown');
  });
  it('searches names, identifiers and descriptions case-insensitively', () => {
    expect(filterCatalogApps(examples, 'PHOTO').map((item) => item.id)).toEqual(['ready']);
    expect(filterCatalogApps(examples, 'BROKEN').map((item) => item.id)).toEqual(['attention']);
  });
  it('distinguishes backend-confirmed routes from merely installed apps', () => {
    expect(catalogStateBucket(examples[0])).toBe('ready');
    expect(catalogStateBucket(examples[2])).toBe('attention');
    expect(catalogStateBucket({ id: 'installed', status: 'installed' })).toBe('unknown');
  });
  it.each([
    ['ready',['ready']],['working',['starting']],['attention',['attention']],
    ['not_installed',['new']],['all',['attention','new','ready','starting','unknown']],
  ])('returns truthful %s filter counts', (bucket, ids) => {
    expect(filterCatalogApps(examples, '', bucket).map((item) => item.id)).toEqual(ids);
  });
  it('retains unknown, malformed and future app types without claiming green readiness', () => {
    expect(catalogStateBucket({ id: 'future', capabilities: {} })).toBe('unknown');
    expect(filterCatalogApps([null, false, 'not a record', { id: 'future' }], '')).toHaveLength(1);
    expect(filterCatalogApps([], 'anything')).toEqual([]);
  });
  it('does not hide saved or unsupported apps unless user explicitly selects a filter', () => {
    expect(filterCatalogApps([{id:'saved',name:'Saved',saved:true}], '')).toHaveLength(1);
  });
});
