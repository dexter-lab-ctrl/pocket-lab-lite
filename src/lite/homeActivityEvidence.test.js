import {describe,it,expect} from 'vitest';import {selectHomeActivityEvidence} from './homeActivityEvidence.js';describe('Home prepared activity evidence',()=>{it('does not invent unavailable history',()=>expect(selectHomeActivityEvidence({history_available:false})).toBeNull());it('projects bounded sanitized counts',()=>{const r=selectHomeActivityEvidence({history_available:true,active_operations:2,recent_completed:3,attention_required:1});expect([r.active,r.completed,r.attention]).toEqual([2,3,1])})});

it('accepts only bounded sanitized known-domain timeline items',()=>{
  const projected=selectHomeActivityEvidence({
    history_available:true,
    recent_events:[
      {domain:'devices',status:'completed',occurred_at_epoch_ms:1700000000000,token:'do-not-display'},
      {domain:'unknown',status:'running',occurred_at_epoch_ms:1700000000001},
      {domain:'apps',status:'waiting_for_review',occurred_at_epoch_ms:1700000000002},
    ],
  });
  expect(projected.events).toHaveLength(2);
  expect(projected.events[0]).toEqual({domain:'devices',status:'completed',at:1700000000000});
  expect(JSON.stringify(projected.events)).not.toContain('do-not-display');
});
