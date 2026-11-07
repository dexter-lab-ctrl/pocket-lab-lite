import React from 'react';
import {
  Activity, ChevronRight, DatabaseBackup, HeartPulse, History,
  Layers3, Link2, Server, Settings2, ShieldCheck,
} from 'lucide-react';
import { deviceManageSections } from './deviceManagePresentation.js';

const ICONS = {
  server: Server, link: Link2, heart: HeartPulse, shield: ShieldCheck,
  layers: Layers3, backup: DatabaseBackup, history: History,
  settings: Settings2,
};

/**
 * A single semantic grouped index for desktop persistent navigation and mobile
 * index-to-detail. It owns no device status or backend commands.
 */
export default function DeviceManageNavigation({
  isProtectedServer = false, activeArea = 'overview', mobile = false, onSelect,
}) {
  return (
    <nav className={`lite-device-manage-navigation ${mobile ? 'is-mobile-index' : 'is-desktop-index'}`}
      aria-label="Device management sections">
      {deviceManageSections(isProtectedServer).map((group) => (
        <section key={group.id} className="lite-device-manage-nav-group" aria-label={group.label}>
          <h4>{group.label}</h4>
          <div className="lite-device-manage-nav-list">
            {group.sections.map(({ id, label, description, icon }) => {
              const Icon = ICONS[icon] || Activity;
              const current = activeArea === id;
              return (
                <button key={id} type="button"
                  data-device-section={id}
                  className={`lite-device-manage-nav-row ${current ? 'is-current' : ''}`}
                  aria-label={label}
                  aria-current={!mobile && current ? 'page' : undefined}
                  onClick={() => onSelect?.(id)}>
                  <Icon size={19} aria-hidden="true" />
                  <span className="lite-device-manage-nav-copy">
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </span>
                  {mobile ? <ChevronRight size={17} className="lite-device-manage-nav-chevron" aria-hidden="true" /> : null}
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </nav>
  );
}
