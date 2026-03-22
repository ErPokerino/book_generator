import { useCallback, useEffect, useState } from 'react';
import { getUserCredits } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export function useUserPoints(currentStep?: string) {
  const { user } = useAuth();
  const [userPoints, setUserPoints] = useState<number | null>(null);
  const [nextPointsReset, setNextPointsReset] = useState<string | null>(null);

  const refreshUserPoints = useCallback(async () => {
    if (!user) {
      setUserPoints(null);
      setNextPointsReset(null);
      return null;
    }

    const response = await getUserCredits();
    if (response) {
      setUserPoints(response.points);
      setNextPointsReset(response.next_reset_at);
    }
    return response;
  }, [user]);

  useEffect(() => {
    void refreshUserPoints().catch((error) => {
      console.warn('[useUserPoints] Errore nel caricamento punti:', error);
    });
  }, [refreshUserPoints]);

  useEffect(() => {
    if (currentStep === 'form' && user) {
      void refreshUserPoints().catch((error) => {
        console.warn('[useUserPoints] Errore nel refresh punti:', error);
      });
    }
  }, [currentStep, refreshUserPoints, user]);

  return {
    userPoints,
    nextPointsReset,
    refreshUserPoints,
  };
}
