import React, { useState } from 'react'
import { WelcomeIcon, CustomizeIcon, EditIcon, ModesIcon, LibraryIcon } from './onboardingIcons'
import './OnboardingCarousel.css'

interface OnboardingScreen {
  id: string
  title: string
  description: string | React.ReactNode
  icon: React.ReactNode
}

interface OnboardingCarouselProps {
  onComplete: () => void
  onSkip: () => void
}

const screens: OnboardingScreen[] = [
  {
    id: 'welcome',
    title: 'Benvenuto in NarrAI',
    description: 'Crea libri unici con l\'intelligenza artificiale',
    icon: <WelcomeIcon className="onboarding-icon-svg" size={80} />,
  },
  {
    id: 'define',
    title: 'Descrivi la tua storia',
    description: 'Inserisci la trama, scegli genere, stile narrativo e tutte le opzioni per creare il libro perfetto per te.',
    icon: <CustomizeIcon className="onboarding-icon-svg" size={80} />,
  },
  {
    id: 'edit',
    title: 'Modifica in ogni momento',
    description: 'Puoi modificare la trama e la struttura del libro in qualsiasi fase del processo. L\'AI si adatterà alle tue modifiche.',
    icon: <EditIcon className="onboarding-icon-svg" size={80} />,
  },
  {
    id: 'modes',
    title: 'Scegli la modalità',
    description: (
      <ul className="onboarding-modes-list">
        <li><strong>Flash</strong>: rapidità</li>
        <li><strong>Pro</strong>: massima qualità</li>
        <li><strong>Ultra</strong>: libri estesi</li>
      </ul>
    ),
    icon: <ModesIcon className="onboarding-icon-svg" size={80} />,
  },
  {
    id: 'library',
    title: 'Crea la tua libreria',
    description: 'Tutti i libri generati vengono salvati nella tua libreria personale. Puoi rileggerli, esportarli e condividerli quando vuoi.',
    icon: <LibraryIcon className="onboarding-icon-svg" size={80} />,
  },
]

export const OnboardingCarousel: React.FC<OnboardingCarouselProps> = ({
  onComplete,
  onSkip,
}) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [direction, setDirection] = useState<'left' | 'right'>('right')

  const isLast = currentStep === screens.length - 1
  const isFirst = currentStep === 0

  const handleNext = () => {
    if (isLast) {
      onComplete()
    } else {
      setDirection('right')
      setCurrentStep((prev) => prev + 1)
    }
  }

  const handlePrevious = () => {
    if (!isFirst) {
      setDirection('left')
      setCurrentStep((prev) => prev - 1)
    }
  }

  const handleDotClick = (index: number) => {
    setDirection(index > currentStep ? 'right' : 'left')
    setCurrentStep(index)
  }

  return (
    <div className="onboarding-overlay">
      <button className="onboarding-skip" onClick={onSkip} aria-label="Salta onboarding">
        Salta
      </button>

      <div className="onboarding-container">
        <div
          className={`onboarding-content onboarding-slide-${direction}`}
          key={currentStep}
        >
          <div className="onboarding-icon-wrapper">
            {screens[currentStep].icon}
          </div>
          <h1 className="onboarding-title">{screens[currentStep].title}</h1>
          <div className="onboarding-description">
            {typeof screens[currentStep].description === 'string' 
              ? <p>{screens[currentStep].description}</p>
              : screens[currentStep].description
            }
          </div>
        </div>

        <div className="onboarding-navigation">
          <div className="onboarding-dots">
            {screens.map((_, index) => (
              <button
                key={index}
                className={`onboarding-dot ${index === currentStep ? 'active' : ''}`}
                onClick={() => handleDotClick(index)}
                aria-label={`Vai alla schermata ${index + 1}`}
              />
            ))}
          </div>

          <div className="onboarding-buttons">
            {!isFirst && (
              <button
                className="onboarding-button onboarding-button-secondary"
                onClick={handlePrevious}
                aria-label="Schermata precedente"
              >
                Indietro
              </button>
            )}
            <button
              className="onboarding-button onboarding-button-primary"
              onClick={handleNext}
              aria-label={isLast ? 'Inizia a usare NarrAI' : 'Schermata successiva'}
            >
              {isLast ? 'Inizia' : 'Avanti'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default OnboardingCarousel
