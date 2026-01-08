import { useState, useRef, useEffect, useCallback } from 'react';
import { Volume2, Pause, Loader } from 'lucide-react';
import { getCritiqueAudio } from '../api/client';
import './CritiqueAudioPlayer.css';

interface CritiqueAudioPlayerProps {
  sessionId: string;
}

export default function CritiqueAudioPlayer({ sessionId }: CritiqueAudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Cleanup quando il componente viene smontato
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);

  // Funzione per riprodurre l'audio in modo sicuro
  const safePlay = useCallback(async (audio: HTMLAudioElement) => {
    try {
      await audio.play();
    } catch (err) {
      // Ignora errori "AbortError" causati da pause() che interrompe play()
      // Questo è un comportamento normale del browser, non un errore reale
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Play interrotto (normale)');
        return;
      }
      throw err;
    }
  }, []);

  const handlePlayPause = async () => {
    // Se l'audio è già caricato e pronto, riproduci/pausa
    if (audioRef.current && isReady) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        try {
          await safePlay(audioRef.current);
          setIsPlaying(true);
        } catch (err) {
          console.error('Errore nella riproduzione:', err);
          setError('Errore nella riproduzione audio');
          setIsPlaying(false);
        }
      }
      return;
    }

    // Se stiamo già caricando, non fare nulla
    if (isLoading) return;

    // Genera e carica audio
    setIsLoading(true);
    setError(null);
    
    try {
      const blob = await getCritiqueAudio(sessionId);
      const url = URL.createObjectURL(blob);
      audioUrlRef.current = url;
      
      // Crea elemento audio
      const audio = new Audio();
      audioRef.current = audio;
      
      // Configura eventi PRIMA di impostare src
      audio.onended = () => {
        setIsPlaying(false);
      };
      
      audio.onerror = () => {
        setError('Errore nella riproduzione audio');
        setIsPlaying(false);
        setIsLoading(false);
        setIsReady(false);
      };
      
      audio.onplay = () => {
        setIsPlaying(true);
        setIsLoading(false);
      };
      
      audio.onpause = () => {
        setIsPlaying(false);
      };
      
      // Aspetta che l'audio sia completamente caricato prima di riprodurre
      audio.oncanplaythrough = async () => {
        setIsReady(true);
        setIsLoading(false);
        try {
          await safePlay(audio);
        } catch (err) {
          console.error('Errore durante play:', err);
        }
      };
      
      // Imposta preload e src
      audio.preload = 'auto';
      audio.src = url;
      audio.load();
      
    } catch (err) {
      let errorMessage = 'Errore nella generazione audio';
      
      if (err instanceof Error) {
        errorMessage = err.message;
        
        // Migliora messaggi di errore specifici
        if (errorMessage.includes('non è abilitata') || errorMessage.includes('Text-to-Speech')) {
          errorMessage = 'L\'API Text-to-Speech non è abilitata. Contatta l\'amministratore per abilitarla.';
        } else if (errorMessage.includes('Permessi insufficienti') || errorMessage.includes('permission')) {
          errorMessage = 'Permessi insufficienti per il servizio audio.';
        } else if (errorMessage.includes('Credenziali') || errorMessage.includes('credentials')) {
          errorMessage = 'Problema con le credenziali Google Cloud.';
        }
      }
      
      setError(errorMessage);
      setIsLoading(false);
    }
  };

  return (
    <div className="critique-audio-player">
      <button
        className="audio-play-button"
        onClick={handlePlayPause}
        disabled={isLoading}
        aria-label={isPlaying ? 'Pausa' : 'Riproduci audio'}
      >
        {isLoading ? (
          <>
            <Loader className="audio-spinner" size={18} />
            <span>Generazione...</span>
          </>
        ) : isPlaying ? (
          <>
            <Pause size={18} />
            <span>In riproduzione</span>
          </>
        ) : (
          <>
            <Volume2 size={18} />
            <span>Ascolta critica</span>
          </>
        )}
      </button>
      {error && (
        <span className="audio-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
