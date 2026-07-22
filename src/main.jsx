import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import App from './App.jsx';
import { ToastProvider } from './components/ToastProvider.jsx';
import { ExperienceModeProvider } from './context/ExperienceModeContext.jsx';
import { GovernanceModeProvider } from './context/GovernanceModeContext.jsx';
import { announceLiteServiceWorkerUpdate, pruneLiteRuntimeCaches } from './lib/liteServiceWorkerRuntime.js';
import './index.css';

let updateSW = () => {};
if (typeof window !== 'undefined') {
  updateSW = registerSW({
    immediate: true,
    onRegisteredSW() {
      pruneLiteRuntimeCaches();
    },
    onNeedRefresh() {
      announceLiteServiceWorkerUpdate(() => updateSW(true));
    },
    onOfflineReady() {
      // no-op: the release workflow keeps the app ready for offline use
    },
  });
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
