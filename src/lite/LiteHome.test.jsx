import { describe, expect, it } from 'vitest';
import { homeWorkflowPresentation } from './LiteHome.jsx';

describe('homeWorkflowPresentation', () => {
  it('uses a live pulse only for current, ready workspace information', () => {
    expect(homeWorkflowPresentation({ overallTone: 'ready', attentionCount: 0, savedStateOnly: false, checking: false })).toMatchObject({
      state: 'ready',
      motion: 'live',
      badge: 'Live',
      activeNodes: ['device', 'services', 'apps', 'safety'],
    });
    expect(homeWorkflowPresentation({ overallTone: 'ready', attentionCount: 0, savedStateOnly: true, checking: false })).toMatchObject({
      state: 'saved',
      motion: 'rest',
      badge: 'Saved',
    });
  });

  it('uses an explicit checking or attention state instead of implying a live flow', () => {
    expect(homeWorkflowPresentation({ overallTone: 'ready', attentionCount: 0, savedStateOnly: false, checking: true })).toMatchObject({
      state: 'checking',
      motion: 'checking',
      badge: 'Checking',
    });
    expect(homeWorkflowPresentation({ overallTone: 'review', attentionCount: 2, savedStateOnly: false, checking: false })).toMatchObject({
      state: 'attention',
      motion: 'rest',
      badge: 'Review',
    });
  });
});
