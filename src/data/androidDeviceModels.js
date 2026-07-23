// Display-only, intentionally bounded catalog. Add reviewed entries here; matches are suggestions and are never auto-selected.
export const ANDROID_DEVICE_MODEL_CATALOG = Object.freeze([
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S23', technicalModels: ['SM-S911B', 'SM-S911U', 'SM-S911N'], codenames: ['dm1q'] },
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S23+', technicalModels: ['SM-S916B', 'SM-S916U', 'SM-S916N'], codenames: ['dm2q'] },
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S23 Ultra', technicalModels: ['SM-S918B', 'SM-S918U', 'SM-S918N'], codenames: ['dm3q'] },
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S24', technicalModels: ['SM-S921B', 'SM-S921U'], codenames: ['e1q'] },
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S24+', technicalModels: ['SM-S926B', 'SM-S926U'], codenames: ['e2q'] },
  { manufacturer: 'Samsung', consumerModelName: 'Samsung Galaxy S24 Ultra', technicalModels: ['SM-S928B', 'SM-S928U'], codenames: ['e3q'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 4', technicalModels: ['Pixel 4'], codenames: ['flame'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 4 XL', technicalModels: ['Pixel 4 XL'], codenames: ['coral'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 7', technicalModels: ['GVU6C', 'GQML3'], codenames: ['panther'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 7 Pro', technicalModels: ['GE2AE', 'GP4BC'], codenames: ['cheetah'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 8', technicalModels: ['GKWS6', 'G9BQD'], codenames: ['shiba'] },
  { manufacturer: 'Google', consumerModelName: 'Google Pixel 8 Pro', technicalModels: ['GC3VE', 'G1MNW'], codenames: ['husky'] },
  { manufacturer: 'OnePlus', consumerModelName: 'OnePlus 11', technicalModels: ['CPH2449', 'CPH2451'], codenames: ['salami'] },
  { manufacturer: 'OnePlus', consumerModelName: 'OnePlus 12', technicalModels: ['CPH2573', 'CPH2581'], codenames: ['waffle'] },
]);

function normalized(value = '') {
  return String(value || '').trim().toLowerCase();
}

export function suggestedAndroidDeviceModels(profile = {}, search = '') {
  const query = normalized(search);
  const manufacturer = normalized(profile.manufacturer);
  const technicalModel = normalized(profile.technical_model);
  const codename = normalized(profile.device_codename);
  return ANDROID_DEVICE_MODEL_CATALOG
    .map((entry) => {
      const modelMatch = entry.technicalModels.some((value) => normalized(value) === technicalModel);
      const codenameMatch = entry.codenames.some((value) => normalized(value) === codename);
      const manufacturerMatch = manufacturer && normalized(entry.manufacturer) === manufacturer;
      const haystack = normalized([entry.manufacturer, entry.consumerModelName, ...entry.technicalModels, ...entry.codenames].join(' '));
      const searchMatch = !query || haystack.includes(query);
      return { ...entry, score: (modelMatch ? 100 : 0) + (codenameMatch ? 80 : 0) + (manufacturerMatch ? 20 : 0), searchMatch };
    })
    .filter((entry) => entry.searchMatch)
    .sort((a, b) => b.score - a.score || a.consumerModelName.localeCompare(b.consumerModelName))
    .slice(0, 30);
}

export const DEVICE_MODEL_CATALOG_IS_DISPLAY_ONLY = true;
