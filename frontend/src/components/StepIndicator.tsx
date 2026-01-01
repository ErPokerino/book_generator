import React from 'react';
import './StepIndicator.css';

interface StepConfig {
  id: string;
  label: string;
  icon: string;
}

const STEPS: StepConfig[] = [
  { id: 'form', label: 'Setup', icon: '📝' },
  { id: 'questions', label: 'Domande', icon: '❓' },
  { id: 'draft', label: 'Bozza', icon: '📄' },
  { id: 'summary', label: 'Struttura', icon: '📋' },
  { id: 'writing', label: 'Scrittura', icon: '✍️' },
];

interface StepIndicatorProps {
  currentStep: 'form' | 'questions' | 'draft' | 'summary' | 'writing';
  progress?: number; // Opzionale: progresso dettagliato per step "writing"
}

export default function StepIndicator({ currentStep, progress }: StepIndicatorProps) {
  const currentStepIndex = STEPS.findIndex(step => step.id === currentStep);
  
  const getStepStatus = (stepIndex: number): 'completed' | 'current' | 'pending' => {
    if (stepIndex < currentStepIndex) return 'completed';
    if (stepIndex === currentStepIndex) return 'current';
    return 'pending';
  };

  return (
    <div className="step-indicator">
      {STEPS.map((step, index) => {
        const status = getStepStatus(index);
        const isLast = index === STEPS.length - 1;
        
        return (
          <div key={step.id} className="step-indicator-item">
            <div className={`step-indicator-content ${status}`}>
              <div className="step-indicator-icon">
                {status === 'completed' ? (
                  <span className="step-checkmark">✓</span>
                ) : (
                  <span className="step-icon">{step.icon}</span>
                )}
              </div>
              <div className="step-indicator-text">
                <div className="step-label">{step.label}</div>
                {status === 'current' && progress !== undefined && currentStep === 'writing' && (
                  <div className="step-progress-detail">
                    {Math.round(progress)}%
                  </div>
                )}
              </div>
            </div>
            {!isLast && (
              <div className={`step-indicator-line ${status === 'completed' ? 'completed' : ''}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
