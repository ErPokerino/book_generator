import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useOnboarding } from '../../hooks/useOnboarding'
import './OnboardingTooltip.css'

interface OnboardingTooltipProps {
  id: string
  children: React.ReactNode
  message: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const tooltipPositions = {
  top: 'tooltip-top',
  bottom: 'tooltip-bottom',
  left: 'tooltip-left',
  right: 'tooltip-right',
}

export const OnboardingTooltip: React.FC<OnboardingTooltipProps> = ({
  id,
  children,
  message,
  position: initialPosition = 'bottom',
  delay = 300,
}) => {
  const { hasSeenTooltip, markTooltipSeen } = useOnboarding()
  const [visible, setVisible] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [actualPosition, setActualPosition] = useState(initialPosition)
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({})
  const [arrowStyle, setArrowStyle] = useState<React.CSSProperties>({})
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (hasSeenTooltip(id)) {
      setVisible(false)
      return
    }

    setVisible(true)
    
    // Delay per mostrare il tooltip dopo che il componente è montato
    timeoutRef.current = setTimeout(() => {
      setShowTooltip(true)
    }, delay)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [id, hasSeenTooltip, delay])

  // Riposizionamento dinamico quando il tooltip è visibile
  useEffect(() => {
    if (!showTooltip || !wrapperRef.current) return

    const checkPosition = () => {
      const wrapper = wrapperRef.current
      if (!wrapper) return

      const wrapperRect = wrapper.getBoundingClientRect()
      const viewportHeight = window.innerHeight
      const viewportWidth = window.innerWidth

      // Stima dell'altezza del tooltip (circa 150-200px con contenuto)
      const estimatedTooltipHeight = 180
      const minSpace = estimatedTooltipHeight + 30 // Spazio minimo richiesto

      // Se la posizione iniziale è 'top', verifica immediatamente se c'è spazio
      if (initialPosition === 'top') {
        const spaceAbove = wrapperRect.top
        
        // Se non c'è abbastanza spazio sopra, cambia immediatamente a 'bottom'
        if (spaceAbove < minSpace) {
          setActualPosition('bottom')
        } else {
          setActualPosition('top')
        }
      } else {
        setActualPosition(initialPosition)
      }
    }

    // Controlla immediatamente e poi dopo un breve delay per il rendering
    checkPosition()
    const checkTimeout = setTimeout(checkPosition, 150)
    
    // Controlla anche su resize e scroll
    window.addEventListener('resize', checkPosition)
    window.addEventListener('scroll', checkPosition, true)

    return () => {
      clearTimeout(checkTimeout)
      window.removeEventListener('resize', checkPosition)
      window.removeEventListener('scroll', checkPosition, true)
    }
  }, [showTooltip, initialPosition])

  // Reset posizione quando cambia la posizione iniziale
  useEffect(() => {
    setActualPosition(initialPosition)
  }, [initialPosition])

  // Calcola la posizione assoluta per il portal
  useEffect(() => {
    if (!showTooltip || !wrapperRef.current) return

    const updateTooltipPosition = () => {
      const wrapper = wrapperRef.current
      if (!wrapper) return

      const rect = wrapper.getBoundingClientRect()
      const tooltipHeight = 180 // Stima
      const tooltipWidth = 280 // Stima
      const spacing = 12

      let top = 0
      let left = rect.left + rect.width / 2

      if (actualPosition === 'top') {
        top = rect.top - tooltipHeight - spacing
      } else {
        top = rect.bottom + spacing
      }

      // Centra orizzontalmente
      const tooltipLeft = Math.max(10, Math.min(left - tooltipWidth / 2, window.innerWidth - tooltipWidth - 10))
      const arrowLeft = left - tooltipLeft // Posizione relativa della freccia

      setTooltipStyle({
        position: 'fixed',
        top: `${top}px`,
        left: `${tooltipLeft}px`,
        zIndex: 10001,
        width: `${tooltipWidth}px`,
      })

      // Posiziona la freccia
      setArrowStyle({
        position: 'absolute',
        left: `${arrowLeft}px`,
        ...(actualPosition === 'top' 
          ? { bottom: '-8px', transform: 'translateX(-50%)' }
          : { top: '-8px', transform: 'translateX(-50%)' }
        ),
      })
    }

    updateTooltipPosition()
    const timeout = setTimeout(updateTooltipPosition, 50)

    window.addEventListener('resize', updateTooltipPosition)
    window.addEventListener('scroll', updateTooltipPosition, true)

    return () => {
      clearTimeout(timeout)
      window.removeEventListener('resize', updateTooltipPosition)
      window.removeEventListener('scroll', updateTooltipPosition, true)
    }
  }, [showTooltip, actualPosition])

  const handleDismiss = () => {
    setShowTooltip(false)
    markTooltipSeen(id)
    setTimeout(() => {
      setVisible(false)
    }, 300) // Aspetta l'animazione di uscita
  }

  if (!visible) {
    return <>{children}</>
  }

  return (
    <>
      <div className="onboarding-tooltip-wrapper" ref={wrapperRef}>
        {children}
      </div>
      {showTooltip && typeof document !== 'undefined' && createPortal(
        <div 
          ref={tooltipRef}
          className={`onboarding-tooltip ${tooltipPositions[actualPosition]}`}
          style={tooltipStyle}
        >
          <div className="onboarding-tooltip-content">
            <p className="onboarding-tooltip-message">{message}</p>
            <button
              className="onboarding-tooltip-button"
              onClick={handleDismiss}
              aria-label="Chiudi tooltip"
            >
              Ho capito
            </button>
          </div>
          <div 
            className={`onboarding-tooltip-arrow arrow-${actualPosition}`}
            style={arrowStyle}
          />
        </div>,
        document.body
      )}
    </>
  )
}

export default OnboardingTooltip
