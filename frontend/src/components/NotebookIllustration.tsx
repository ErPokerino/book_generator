export type Medium = 'book' | 'essay' | 'manga';

export default function NotebookIllustration({ medium, className = '' }: { medium: Medium; className?: string }) {
  return <svg className={`notebook-illustration ${className}`} viewBox="0 0 180 120" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {medium === 'book' ? <>
      <path d="M29 28 Q58 20 87 33 Q114 18 147 25 L151 91 Q120 85 90 101 Q60 89 28 97 Z" />
      <path d="M87 33 Q85 65 90 101 M29 28 L24 32 L23 101 Q61 95 90 105 Q121 91 155 96 L154 29 L148 27" />
      <path d="M41 41 Q62 37 75 42 M41 50 Q61 47 75 51 M41 59 L74 60 M40 69 L65 69 M102 41 Q124 33 136 37 M103 50 L137 45 M103 59 L133 54 M105 68 L122 64" strokeWidth="1.2" />
      <path d="M110 24 L109 62 L118 54 L125 58 L124 21" />
      <path d="M15 15 L18 21 M6 29 L15 30 M161 12 L159 20 M169 24 L163 27" />
    </> : medium === 'essay' ? <>
      <path d="M39 22 L121 19 L132 100 L43 103 Z M45 26 L124 23 M40 22 L36 27 L39 107 L130 104" />
      <path d="M54 42 Q80 40 100 41 M55 50 L105 49 M57 62 L97 61 M57 70 L103 69 M58 79 L85 78" strokeWidth="1.2" />
      <path d="M108 83 Q121 49 157 15 Q165 36 138 61 L115 74 M157 15 Q134 54 102 94 M128 46 L145 42 M120 61 L137 56" />
      <path d="M26 39 Q6 39 13 62 Q17 71 32 64 M22 57 L32 64 L24 69 M136 90 Q150 96 163 86" />
      <path d="M56 88 Q75 90 94 86" strokeWidth="2.5" />
    </> : <>
      <path d="M30 20 L150 23 L147 102 L27 98 Z M37 28 L79 29 L77 64 L35 63 Z M86 29 L141 31 L140 65 L85 64 Z M35 71 L139 73 L138 93 L34 91 Z" />
      <path d="M57 35 L59 44 L69 40 L63 50 L72 54 L61 55 L57 64 L54 54 L44 58 L49 50 L43 42 L53 44 Z M95 43 Q97 34 118 37 Q136 41 130 52 Q125 59 110 56 L99 61 L102 53 Q92 51 95 43 Z" />
      <path d="M103 44 L121 45 M105 49 L117 50 M43 80 L70 81 M43 85 L86 86 M96 79 L128 80 M107 86 L129 86 M152 13 L157 6 M161 21 L170 18 M17 81 L11 84" strokeWidth="1.2" />
    </>}
    <path className="sketch-ground" d="M16 111 Q76 106 167 111" strokeWidth=".8" opacity=".4" />
  </svg>;
}
