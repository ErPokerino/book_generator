import React from 'react';

interface IconProps {
  className?: string;
  size?: number;
}

export const FlashIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  const gradientId = `flashGradient-${Math.random().toString(36).substr(2, 9)}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill={`url(#${gradientId})`} />
    </svg>
  );
};

export const ProIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  const gradientId = `proGradient-${Math.random().toString(36).substr(2, 9)}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <defs>
        <linearGradient id={gradientId} x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.4" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.15" />
        </linearGradient>
      </defs>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" fill={`url(#${gradientId})`} />
    </svg>
  );
};

export const UltraIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  const gradientId = `ultraGradient-${Math.random().toString(36).substr(2, 9)}`;
  const orbitId = `ultraOrbit-${Math.random().toString(36).substr(2, 9)}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <defs>
        <radialGradient id={gradientId} cx="50%" cy="50%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.5" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.2" />
        </radialGradient>
        <linearGradient id={orbitId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      {/* Sistema solare: Sole centrale con pianeti orbitanti */}
      <circle cx="12" cy="12" r="3.5" fill={`url(#${gradientId})`} />
      {/* Orbite */}
      <ellipse cx="12" cy="12" rx="7" ry="4" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />
      <ellipse cx="12" cy="12" rx="9" ry="5.5" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.2" />
      {/* Pianeti */}
      <circle cx="19" cy="12" r="1.5" fill={`url(#${orbitId})`} />
      <circle cx="5" cy="12" r="1.2" fill={`url(#${orbitId})`} />
      <circle cx="12" cy="6" r="1" fill={`url(#${orbitId})`} />
      <circle cx="12" cy="18" r="1" fill={`url(#${orbitId})`} />
    </svg>
  );
};
