import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import './redesign.css';
import './mascot.css';
import './theme.css';
import './portal.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
