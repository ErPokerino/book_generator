import React from 'react';

interface IconProps {
  className?: string;
  size?: number;
}

// Icone originali - stile outline (disegno a matita), senza colori

// FLASH: fulmine originale
export const FlashIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
};

// PRO: stella originale
export const ProIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
};

// ULTRA: simbolo infinito (∞) - lemniscata classica, stile outline
export const UltraIcon: React.FC<IconProps> = ({ className = '', size = 32 }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {/* Simbolo infinito: lemniscata classica (∞) - solo outline - forma continua e pulita */}
      <path d="M18.178 8.088c-1.183 0-2.143.96-2.143 2.143 0 1.183.96 2.143 2.143 2.143 1.183 0 2.143-.96 2.143-2.143 0-1.183-.96-2.143-2.143-2.143" />
      <path d="M5.822 8.088c1.183 0 2.143.96 2.143 2.143 0 1.183-.96 2.143-2.143 2.143-1.183 0-2.143-.96-2.143-2.143 0-1.183.96-2.143 2.143-2.143" />
      <path d="M5.822 8.088c0 0 2.143 0 4.286 2.143s4.286 2.143 4.286 2.143" />
      <path d="M18.178 8.088c0 0-2.143 0-4.286 2.143s-4.286 2.143-4.286 2.143" />
    </svg>
  );
};
