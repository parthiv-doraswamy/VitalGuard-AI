import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App.tsx';
import './index.css';
import { initPwa } from './services/pwa.ts';
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
// Production builds only: the dev server has no service worker, so local development never serves stale bundles.
if (import.meta.env.PROD) initPwa();
