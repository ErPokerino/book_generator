import { useState, useRef, useEffect, useCallback } from 'react';
import { Volume2, Pause, Loader } from 'lucide-react';
import { getCritiqueAudio, getChapterAudio } from '../api/client';
import './AudioPlayer.css';

interface AudioPlayerProps {
  sessionId: string;
  type: 'critique' | 'chapter';
  chapterIndex?: number;
}

export default function AudioPlayer({ sessionId, type, chapterIndex }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

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

  const safePlay = useCallback(async (audio: HTMLAudioElement) => {
    try {
      await audio.play();
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Play interrotto (normale)');
        return;
      }
      throw err;
    }
  }, []);

  const handlePlayPause = async () => {
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

    if (isLoading) return;

    setIsLoading(true);
    setError(null);
    
    try {
      let blob: Blob;
      if (type === 'critique') {
        blob = await getCritiqueAudio(sessionId);
      } else {
        if (chapterIndex === undefined) throw new Error("Manca indice capitolo");
        blob = await getChapterAudio(sessionId, chapterIndex);
      }
      
      const url = URL.createObjectURL(blob);
      audioUrlRef.current = url;
      
      const audio = new Audio();
      audioRef.current = audio;
      
      audio.onended = () => setIsPlaying(false);
      
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
      
      audio.onpause = () => setIsPlaying(false);
      
      audio.oncanplaythrough = async () => {
        setIsReady(true);
        setIsLoading(false);
        try {
          await safePlay(audio);
        } catch (err) {
          console.error('Errore durante play:', err);
        }
      };
      
      audio.preload = 'auto';
      audio.src = url;
      audio.load();
      
    } catch (err) {
      let errorMessage = 'Errore nella generazione audio';
      
      if (err instanceof Error) {
        errorMessage = err.message;
        if (errorMessage.includes('non è abilitata') || errorMessage.includes('Text-to-Speech')) {
          errorMessage = 'L\'API Text-to-Speech non è abilitata. Contatta l\'amministratore.';
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

  const labelAction = type === 'critique' ? 'Ascolta critica' : 'Ascolta capitolo';

  return (
    <div className="audio-player-container">
      <button
        className="audio-play-button"
        onClick={handlePlayPause}
        disabled={isLoading}
        aria-label={isPlaying ? 'Pausa' : labelAction}
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
            <span>{labelAction}</span>
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
