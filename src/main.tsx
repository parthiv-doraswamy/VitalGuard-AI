import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App.tsx';
import { registerPwa } from './services/pwa.ts';
import './index.css';

void registerPwa();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
