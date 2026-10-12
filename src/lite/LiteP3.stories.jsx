import React, { useState } from 'react';
import { Activity, LayoutGrid, Network } from 'lucide-react';
import LiteQuickNavigate from './components/LiteQuickNavigate.jsx';

export default { title:'Pocket Lab Lite/P3 Responsive Productivity', tags:['autodocs'] };
const items=[{id:'home',label:'Home',icon:Activity},{id:'catalog',label:'Apps',icon:LayoutGrid},{id:'devices',label:'Devices',icon:Network}];
function Fixture({initialOpen=true}) {const [open,setOpen]=useState(initialOpen); const [selected,setSelected]=useState('home'); return <div className="theme-pocket-lite-daylight" style={{padding:24,minHeight:'100vh'}}><button type="button" onClick={()=>setOpen(true)}>Find a section</button><p>Current: {selected}</p><LiteQuickNavigate open={open} onClose={()=>setOpen(false)} onNavigate={setSelected} items={items} activeId={selected}/></div>}
export const DesktopOpen={render:()=> <Fixture/>};
export const MobileNarrow={render:()=> <Fixture/>,parameters:{viewport:{defaultViewport:'mobile360'}}};
export const Closed={render:()=> <Fixture initialOpen={false}/>};
