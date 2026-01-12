import { useState, useEffect } from 'react';
import './SplashScreen.css';

interface SplashScreenProps {
  /** Minimum time to show splash screen in ms */
  minDisplayTime?: number;
  /** Called when splash screen should be hidden */
  onFinished?: () => void;
}

export default function SplashScreen({ 
  minDisplayTime = 1500,
  onFinished 
}: SplashScreenProps) {
  const [fadeOut, setFadeOut] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setFadeOut(true);
      // Wait for fade animation to complete before calling onFinished
      setTimeout(() => {
        setHidden(true);
        onFinished?.();
      }, 400);
    }, minDisplayTime);

    return () => clearTimeout(timer);
  }, [minDisplayTime, onFinished]);

  if (hidden) {
    return null;
  }

  return (
    <div className={`splash-screen ${fadeOut ? 'fade-out' : ''}`}>
      <img 
        src="/logo-narrai.png" 
        alt="NarrAI" 
        className="splash-logo"
      />
      <div className="splash-loader">
        <div className="splash-loader-dot" />
        <div className="splash-loader-dot" />
        <div className="splash-loader-dot" />
      </div>
    </div>
  );
}
