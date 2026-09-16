import { useEffect, useState } from 'react';

export function LockoutBanner({ lockoutUntil, onClose }) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!lockoutUntil) return;
    const update = () => {
      const diff = lockoutUntil - Date.now();
      if (diff <= 0) {
        setRemaining(0);
        onClose?.();
      } else {
        setRemaining(diff);
      }
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [lockoutUntil, onClose]);

  if (!remaining) return null;

  const mins = Math.floor(remaining / 60000);
  const secs = Math.floor((remaining % 60000) / 1000);

  return (
    <div className="lockout-banner" role="alert">
      <span>Too many failed attempts. Try again in {mins}:{secs.toString().padStart(2, '0')}.</span>
    </div>
  );
}

export function LockoutWarning({ attempts, maxAttempts = 5, onClose }) {
  if (attempts < 2 || attempts >= maxAttempts) return null;
  
  const remaining = maxAttempts - attempts;
  
  return (
    <div className="lockout-warning" role="alert">
      <span>
        {remaining} attempt{remaining !== 1 ? 's' : ''} remaining before account lockout.
      </span>
      <button 
        type="button" 
        className="lockout-warning-close" 
        onClick={onClose}
        aria-label="Dismiss warning"
      >
        ✕
      </button>
    </div>
  );
}