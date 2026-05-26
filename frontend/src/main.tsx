import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppLocaleProvider } from './app/locale';
import { AppRouter } from './app/router';
import './styles/design-tokens.css';
import './styles/layout.css';
import './styles/animations.css';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppLocaleProvider>
      <AppRouter />
    </AppLocaleProvider>
  </React.StrictMode>
);
