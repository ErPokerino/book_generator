import { useState, useCallback } from 'react'

const CAROUSEL_KEY = 'narrai_onboarding_carousel'
const TOOLTIPS_KEY = 'narrai_onboarding_tooltips'

export const useOnboarding = () => {
  const [hasSeenCarousel, setHasSeenCarousel] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem(CAROUSEL_KEY) === 'true'
  })

  const [seenTooltips, setSeenTooltips] = useState<string[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      return JSON.parse(localStorage.getItem(TOOLTIPS_KEY) || '[]')
    } catch {
      return []
    }
  })

  const completeCarousel = useCallback(() => {
    if (typeof window === 'undefined') return
    localStorage.setItem(CAROUSEL_KEY, 'true')
    setHasSeenCarousel(true)
  }, [])

  const markTooltipSeen = useCallback((id: string) => {
    if (typeof window === 'undefined') return
    const updated = [...seenTooltips, id]
    localStorage.setItem(TOOLTIPS_KEY, JSON.stringify(updated))
    setSeenTooltips(updated)
  }, [seenTooltips])

  const resetOnboarding = useCallback(() => {
    if (typeof window === 'undefined') return
    localStorage.removeItem(CAROUSEL_KEY)
    localStorage.removeItem(TOOLTIPS_KEY)
    setHasSeenCarousel(false)
    setSeenTooltips([])
  }, [])

  const hasSeenTooltip = useCallback((id: string) => {
    return seenTooltips.includes(id)
  }, [seenTooltips])

  return {
    hasSeenCarousel,
    seenTooltips,
    completeCarousel,
    markTooltipSeen,
    resetOnboarding,
    hasSeenTooltip,
  }
}
