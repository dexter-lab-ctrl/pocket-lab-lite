import {
  Activity,
  Database,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Network,
  ShieldCheck,
} from 'lucide-react';

export const DEFAULT_LITE_SCREEN_ID = 'home';

export const NAV_ITEMS = Object.freeze([
  Object.freeze({ id: 'home', label: 'Home', icon: Activity }),
  Object.freeze({ id: 'catalog', label: 'App Catalog', icon: LayoutGrid }),
  Object.freeze({ id: 'identity', label: 'Identity & Access', icon: Fingerprint }),
  Object.freeze({ id: 'security', label: 'Security', icon: ShieldCheck }),
  Object.freeze({ id: 'devices', label: 'Devices', icon: Network }),
  Object.freeze({ id: 'rules', label: 'Rules', icon: FileCheck }),
  Object.freeze({ id: 'recovery', label: 'Recovery', icon: Database }),
]);

const LITE_SCREEN_IDS = new Set(NAV_ITEMS.map((item) => item.id));

export function isLiteScreenId(value) {
  return LITE_SCREEN_IDS.has(String(value || '').trim().toLowerCase());
}

export function normalizeLiteScreenId(value, fallback = DEFAULT_LITE_SCREEN_ID) {
  const normalized = String(value || '').trim().toLowerCase();
  if (LITE_SCREEN_IDS.has(normalized)) return normalized;
  return LITE_SCREEN_IDS.has(fallback) ? fallback : DEFAULT_LITE_SCREEN_ID;
}
