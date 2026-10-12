import { describe, it, expect } from 'vitest';
import { prioritizeWorkspaceAttention } from './homeAttentionPriority.js';
describe('Home attention ordering', () => {
  it('sorts severity first and removes healthy and duplicate service issues without source mutation', () => {
    const items = [{ key: 'safety', tone: 'review' }, { key: 'devices', tone: 'danger' },
      { key: 'safety', tone: 'danger' }, { key: 'healthy', tone: 'ready' }];
    expect(prioritizeWorkspaceAttention(items).map((item) => item.key)).toEqual(['devices', 'safety']);
    expect(items).toHaveLength(4);
  });
});
