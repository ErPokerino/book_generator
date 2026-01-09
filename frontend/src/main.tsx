import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Rimuovi splash screen dopo il render
const removeSplashScreen = () => {
  const splashScreen = document.getElementById('splash-screen');
  if (splashScreen) {
    splashScreen.classList.add('hidden');
    // Rimuovi completamente dopo la transizione
    setTimeout(() => {
      splashScreen.remove();
    }, 500); // Match con la durata della transizione CSS
  }
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Rimuovi splash screen dopo che React è stato renderizzato
// Usa requestAnimationFrame per assicurarsi che il DOM sia pronto
requestAnimationFrame(() => {
  // Piccolo delay per permettere all'animazione di essere visibile
  setTimeout(removeSplashScreen, 300);
});




