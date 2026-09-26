let deviceCardPromise = null;

export function loadDeviceCard() {
  return import('./DeviceCard.jsx');
}

export function preloadDeviceCard() {
  if (!deviceCardPromise) {
    deviceCardPromise = loadDeviceCard().catch((error) => {
      deviceCardPromise = null;
      throw error;
    });
  }
  return deviceCardPromise;
}
