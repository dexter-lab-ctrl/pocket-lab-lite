import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import LiteQuickNavigate, { filterLiteNavigation, shouldOpenLiteQuickNavigate } from './LiteQuickNavigate.jsx';

const items = [{id:'home',label:'Home'}, {id:'catalog',label:'Apps'}, {id:'devices',label:'Devices'}];
describe('P3 responsive navigation productivity', () => {
  it('only handles explicit non-editable Ctrl/Cmd K', () => {
    expect(shouldOpenLiteQuickNavigate({key:'k',ctrlKey:true})).toBe(true);
    expect(shouldOpenLiteQuickNavigate({key:'k',metaKey:true})).toBe(true);
    expect(shouldOpenLiteQuickNavigate({key:'k',ctrlKey:true,repeat:true})).toBe(false);
    expect(shouldOpenLiteQuickNavigate({key:'k',ctrlKey:true,target:{closest:()=>({})}})).toBe(false);
    expect(shouldOpenLiteQuickNavigate({key:'x',ctrlKey:true})).toBe(false);
  });
  it('filters existing sections, never invents commands', () => {
    expect(filterLiteNavigation(items,'dev')).toEqual([items[2]]);
    expect(filterLiteNavigation(items,'unknown')).toEqual([]);
  });
  it('navigates only on deliberate selection, and closes on selection', () => {
    const navigate=vi.fn(), close=vi.fn();
    render(<LiteQuickNavigate open items={items} activeId="home" onNavigate={navigate} onClose={close}/>);
    fireEvent.change(screen.getByRole('searchbox'),{target:{value:'devices'}});
    fireEvent.click(screen.getByRole('button',{name:'Devices'}));
    expect(navigate).toHaveBeenCalledWith('devices');
    expect(close).toHaveBeenCalledTimes(1);
  });
  it('does not show any overlay when closed', () => {
    render(<LiteQuickNavigate open={false} items={items} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
