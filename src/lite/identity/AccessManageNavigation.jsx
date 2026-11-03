import React, { useEffect, useRef } from 'react';
import { Activity, ArrowLeft, ChevronRight, Fingerprint, KeyRound, MonitorSmartphone, Settings2, ShieldCheck, UserRound, UsersRound } from 'lucide-react';
import { accessManageGroups } from './accessCenterPresentation.js';

const icons = { activity: Activity, fingerprint: Fingerprint, key: KeyRound, monitor: MonitorSmartphone, settings: Settings2, shield: ShieldCheck, user: UserRound, users: UsersRound };

export default function AccessManageNavigation({ section, setSection, enterpriseEnabled, hasApprovals, hasClients, children }) {
  const groups = accessManageGroups({ enterpriseEnabled, hasApprovals, hasClients });
  const selectedId = section || 'overview';
  const selected = groups.flatMap((group) => group.items).find((item) => item.id === selectedId);
  const titleRef = useRef(null);
  const lastSelectedRef = useRef(section);
  const activeButtonRef = useRef(null);

  useEffect(() => {
    if (lastSelectedRef.current !== section) {
      if (section) titleRef.current?.focus({ preventScroll: true });
      else activeButtonRef.current?.focus({ preventScroll: true });
      lastSelectedRef.current = section;
    }
  }, [section]);

  return <div className="lite-id-native-workspace" data-access-manage-view={section ? 'section' : 'index'} data-access-manage-selected={selectedId}>
    <nav className="lite-id-native-index" aria-label="Manage Access sections">
      {groups.map((group) => <div className="lite-id-native-group" key={group.label}>
        <h2>{group.label}</h2>
        <div className="lite-id-native-rows">
          {group.items.map((item) => {
            const Icon = icons[item.icon] || ShieldCheck;
            return <button type="button" key={item.id} ref={item.id === selectedId ? activeButtonRef : null}
              className="lite-id-native-row" aria-label={item.label} aria-current={item.id === selectedId ? 'page' : undefined}
              onClick={() => setSection(item.id)}>
              <Icon size={19} aria-hidden="true" />
              <span><strong>{item.label}</strong><small>{item.description}</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>;
          })}
        </div>
      </div>)}
    </nav>
    <div className="lite-id-native-detail">
      <button type="button" className="lite-id-native-back" onClick={() => setSection(null)}>
        <ArrowLeft size={18} aria-hidden="true" /> All access settings
      </button>
      <header className="lite-id-native-detail-heading">
        <h2 ref={titleRef} tabIndex={-1}>{selected?.label || 'Overview'}</h2>
        <p>{selected?.description || 'Your account and protection'}</p>
      </header>
      <div className="lite-id-native-detail-content">{children}</div>
    </div>
  </div>;
}
