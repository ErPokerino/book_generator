import React, { useState } from 'react'
import { LibraryIcon, CustomizeIcon, EditIcon } from './onboardingIcons'
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
    id: 'library',
    title: 'Le tue opere',
    description: 'Qui trovi i libri e i manga. Continua una bozza o leggi un’opera pronta.',
    icon: <LibraryIcon className="onboarding-icon-svg" size={72} />,
  },
  {
    id: 'create',
    title: 'Crea una storia',
    description: 'Parti dalla trama. Libro o manga, nello stesso foglio. I modelli restano in secondo piano.',
    icon: <CustomizeIcon className="onboarding-icon-svg" size={72} />,
  },
  {
    id: 'read',
    title: 'Leggi senza rumore',
    description: 'Il lettore è una pagina: titolo, capitolo, testo. Niente pannelli, solo la storia.',
    icon: <EditIcon className="onboarding-icon-svg" size={72} />,
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
