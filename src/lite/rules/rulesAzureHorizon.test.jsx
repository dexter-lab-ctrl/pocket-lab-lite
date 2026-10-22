// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { rulesProtectionView, rulesDecisionView, rulesActivationView } from './rulesPremiumView.js';
import RulesProtectionJourney from './RulesProtectionJourney.jsx';
import RulesDecisionInsight from './RulesDecisionInsight.jsx';

const ready = { status: 'ready', engine: { healthy: true, loopback_only: true }, active_policy: { bundle_ready: true, source_update_required: false, activation_in_progress: false } };
describe('Azure Horizon Rules: source-authored truth contracts', () => {
  it('only confirms Ready with all backend proofs', () => {
    expect(rulesProtectionView(ready, { enterprise:false })).toMatchObject({ state:'ready', revisionCurrent:true, mode:'Personal Mode' });
    expect(rulesProtectionView(ready, { enterprise:true }).mode).toBe('Enterprise Mode');
    expect(rulesProtectionView({ ...ready, engine:{healthy:true} }).state).toBe('degraded');
    expect(rulesProtectionView({ ...ready, active_policy:{source_update_required:true} }).state).toBe('degraded');
  });
  it('saved, stale, unreachable and unavailable never grant write authority', () => {
    for (const options of [{savedStateOnly:true},{isExpired:true},{backendReachable:false}]) {
      expect(rulesProtectionView(ready, options).canWrite).toBe(false);
    }
    expect(rulesProtectionView(null)).toMatchObject({state:'unavailable',canWrite:false});
    expect(rulesProtectionView({status:'unknown'}).revisionCurrent).toBe(false);
  });
  it('distinguishes allowed, denied, step-up, approval and simulated decisions', () => {
    const outcomes=['allow','blocked','step_up_required','approval_required','unknown'];
    const labels=outcomes.map(outcome=>rulesDecisionView({outcome,action_id:'device.remove'}).status);
    expect(labels).toEqual(['Authorization allowed','Blocked','Passkey step-up required','Independent approval required','Decision not confirmed']);
    expect(rulesDecisionView({outcome:'allow',mode:'synthetic'}).status).toBe('Simulation allowed');
    expect(rulesDecisionView({outcome:'allow'}).execution).toBe('');
    expect(rulesDecisionView({outcome:'allow',execution_state:'untrusted'}).execution).toBe('');
  });
  it('renders server activation stages without manufacturing success',()=>{
    expect(rulesActivationView({state:'pending'}).steps.every(stage=>stage.state!=='completed')).toBe(true);
    expect(rulesActivationView({state:'uncertain'}).recovery).toBe(true);
    expect(rulesActivationView({state:'rolled_back'}).recovery).toBe(true);
    expect(rulesActivationView({state:'active'}).steps.every(stage=>stage.state==='completed')).toBe(true);
  });
  it('keeps the four selectable Journey stages educational',()=>{
    render(<RulesProtectionJourney/>);
    const buttons=screen.getAllByRole('button');
    expect(buttons).toHaveLength(4);
    fireEvent.click(buttons[1]);
    expect(buttons[1].getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText(/evaluates the applicable Rules/i)).toBeTruthy();
    cleanup();
  });
  it('never turns a simulation into a granted permission',()=>{
    render(<RulesDecisionInsight simulated decision={{outcome:'allow',actor_label:'Operator'}}/>);
    expect(screen.getByText(/No real permission or system change is granted/i)).toBeTruthy();
    expect(screen.getByText(/Authorization does not establish/i)).toBeTruthy();
    cleanup();
  });
});
