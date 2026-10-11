import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

const SoundContext = createContext({ enabled: false, toggle: () => {} });
const KEY = 'narrai.notebook-sounds';

export function NotebookSoundProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(() => { try { return localStorage.getItem(KEY) === 'true'; } catch { return false; } });
  const audio = useRef<AudioContext | null>(null);
  useEffect(() => {
    try { localStorage.setItem(KEY, String(enabled)); } catch { /* preference stays active for this visit */ }
    if (!enabled) { void audio.current?.suspend().catch(() => {}); return; }
    let lastStroke = 0;
    let lastHover = -Infinity;
    function stroke(turnPage = false, hover = false) {
      if (document.hidden || (!turnPage && !hover && performance.now() - lastStroke < 100)) return;
      // Hover cannot unlock audio: wait for a deliberate click or keystroke.
      if (hover && audio.current?.state !== 'running') return;
      lastStroke = performance.now();
      try {
        const context = audio.current || (audio.current = new AudioContext());
        if (context.state === 'suspended') void context.resume().catch(() => {});
        const duration = hover ? .045 : turnPage ? .13 : .035;
        const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * duration), context.sampleRate);
        const data = buffer.getChannelData(0);
        for (let index = 0; index < data.length; index++) data[index] = (Math.random() * 2 - 1) * Math.sin(Math.PI * index / data.length);
        const source = context.createBufferSource(); source.buffer = buffer;
        const filter = context.createBiquadFilter(); filter.type = 'bandpass'; filter.frequency.value = turnPage ? 1100 : 2600; filter.Q.value = .7;
        const gain = context.createGain(); gain.gain.value = hover ? .008 : turnPage ? .035 : .017;
        source.connect(filter); filter.connect(gain); gain.connect(context.destination);
        source.onended = () => { source.disconnect(); filter.disconnect(); gain.disconnect(); };
        source.start();
      } catch { /* Sound is optional; unsupported browsers keep the studio usable. */ }
    }
    const click = (event: MouseEvent) => { if ((event.target as Element)?.closest('a,button') && !(event.target as Element).closest('[data-sound-toggle]')) stroke(true); };
    const key = (event: KeyboardEvent) => { if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && (event.target as Element)?.matches('textarea,input[type="text"],input:not([type])')) stroke(); };
    const hover = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
      const card = event.target instanceof Element ? event.target.closest('.notebook-mode-card') : null;
      if (!card || (event.relatedTarget instanceof Node && card.contains(event.relatedTarget))) return;
      if (performance.now() - lastHover < 450 || audio.current?.state !== 'running') return;
      lastHover = performance.now();
      stroke(false, true);
    };
    document.addEventListener('click', click); document.addEventListener('keydown', key); document.addEventListener('pointerover', hover);
    return () => { document.removeEventListener('click', click); document.removeEventListener('keydown', key); document.removeEventListener('pointerover', hover); };
  }, [enabled]);
  useEffect(() => () => { void audio.current?.close().catch(() => {}); }, []);
  return <SoundContext.Provider value={{ enabled, toggle: () => setEnabled(value => !value) }}>{children}</SoundContext.Provider>;
}

export const useNotebookSound = () => useContext(SoundContext);
