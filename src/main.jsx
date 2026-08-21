import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import App from './App.jsx';
import { captureOwnerClaimFromUrl } from './lib/liteOwnerClaim.js';
import { ToastProvider } from './components/ToastProvider.jsx';
import { ExperienceModeProvider } from './context/ExperienceModeContext.jsx';
import { GovernanceModeProvider } from './context/GovernanceModeContext.jsx';
import {
  announceLiteServiceWorkerUpdate,
  createLiteControlledServiceWorkerUpdate,
  pruneLiteRuntimeCaches,
} from './lib/liteServiceWorkerRuntime.js';
import './index.css';

let updateSW = () => {};
if (typeof window !== 'undefined') {
  captureOwnerClaimFromUrl();
  updateSW = registerSW({
    immediate: true,
    onRegisteredSW() {
      pruneLiteRuntimeCaches();
    },
    onNeedRefresh() {
      announceLiteServiceWorkerUpdate(createLiteControlledServiceWorkerUpdate({
        updateServiceWorker: (reloadPage = false) => updateSW(reloadPage),
        buildId: import.meta.env.VITE_POCKETLAB_BUILD_ID || 'development',
      }));
    },
    onOfflineReady() {
      // no-op: the release workflow keeps the app ready for offline use
    },
  });
}

async function bootstrapPocketLabLite() {
  if (import.meta.env.VITE_POCKETLAB_MOCKS === '1') {
    const { startPocketLabMocks } = await import('./mocks/browser.js');
    await startPocketLabMocks();
  }

  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <ExperienceModeProvider>
        <GovernanceModeProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </GovernanceModeProvider>
      </ExperienceModeProvider>
    </React.StrictMode>,
  );
}

bootstrapPocketLabLite().catch((error) => {
  console.error('[Pocket Lab Lite] startup failed', error);
});
