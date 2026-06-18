export const controlPlaneHealthy = {
  ready: true,
  message: 'FastAPI/NATS production control plane ready',
  api: true,
  nats: true,
  jetstream: true,
  worker: true,
};

export const controlPlaneNatsDown = {
  ready: false,
  message: 'NATS/JetStream is required for safe write operations and is unavailable.',
  api: true,
  nats: false,
  jetstream: false,
  worker: false,
};

export const workerDown = {
  ready: false,
  message: 'Worker execution is not available; write actions are paused.',
  api: true,
  nats: true,
  jetstream: true,
  worker: false,
};
