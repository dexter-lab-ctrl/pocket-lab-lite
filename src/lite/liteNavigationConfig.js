import {
  Activity,
  Database,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Network,
  ShieldCheck,
} from 'lucide-react';
import {
  DEFAULT_LITE_SCREEN_ID,
  LITE_SCREEN_METADATA,
} from './liteNavigationMetadata.js';

const LITE_SCREEN_ICONS = Object.freeze({
  home: Activity,
  catalog: LayoutGrid,
  identity: Fingerprint,
  security: ShieldCheck,
  devices: Network,
  rules: FileCheck,
  recovery: Database,
});

export { DEFAULT_LITE_SCREEN_ID } from './liteNavigationMetadata.js';
export {
  createLiteScreenLaunchUrl,
  getLiteManifestShortcutDefinitions,
  initialLiteScreenIdFromLocation,
  isLiteScreenId,
  isLiteShortcutScreenId,
  normalizeLiteScreenId,
  parseLiteScreenLaunch,
  replaceLiteScreenLaunch,
} from './liteNavigationMetadata.js';

export const NAV_ITEMS = Object.freeze(
  LITE_SCREEN_METADATA.map((item) => Object.freeze({
    id: item.id,
    label: item.label,
    icon: LITE_SCREEN_ICONS[item.id],
  })),
);
