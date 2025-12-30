import { useState } from 'react';
import { Question, QuestionAnswer, submitAnswers } from '../api/client';
import './QuestionsStep.css';

interface QuestionsStepProps {
  questions: Question[];
  sessionId: string;
  onComplete: (answers: QuestionAnswer[]) => void;
  onBack?: () => void;
}

export default function QuestionsStep({ questions, sessionId, onComplete, onBack }: QuestionsStepProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnswerChange = (questionId: string, value: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: value }));
    if (error) setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      // Costruisce l'array di risposte (include anche quelle vuote/saltate)
      const answersList: QuestionAnswer[] = questions.map(q => ({
        question_id: q.id,
        answer: answers[q.id]?.trim() || undefined,
      }));

      await submitAnswers({
        session_id: sessionId,
        answers: answersList,
      });

      onComplete(answersList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nell\'invio delle risposte');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderQuestion = (question: Question) => {
    const answerValue = answers[question.id] || '';

    if (question.type === 'multiple_choice') {
      return (
        <div key={question.id} className="question-item">
          <label htmlFor={question.id} className="question-label">
            {question.text}
            <span className="optional-badge">(opzionale)</span>
          </label>
          <select
            id={question.id}
            value={answerValue}
            onChange={(e) => handleAnswerChange(question.id, e.target.value)}
            className="question-input"
          >
            <option value="">-- Seleziona una risposta (opzionale) --</option>
            {question.options?.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    }

    // Text input
    return (
      <div key={question.id} className="question-item">
        <label htmlFor={question.id} className="question-label">
          {question.text}
          <span className="optional-badge">(opzionale)</span>
        </label>
        <input
          type="text"
          id={question.id}
          value={answerValue}
          onChange={(e) => handleAnswerChange(question.id, e.target.value)}
          className="question-input"
          placeholder="Lascia vuoto se preferisci saltare questa domanda"
        />
      </div>
    );
  };

  return (
    <div className="questions-step-container">
      <h2>Domande Preliminari</h2>
      <p className="questions-intro">
        Per aiutarti a creare il romanzo perfetto, abbiamo preparato alcune domande opzionali.
        Puoi rispondere a tutte, ad alcune, o saltarle completamente.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <form onSubmit={handleSubmit} className="questions-form">
        {questions.map(renderQuestion)}

        <div className="questions-actions">
          {onBack && (
            <button type="button" onClick={onBack} className="back-button">
              Indietro
            </button>
          )}
          <button type="submit" disabled={isSubmitting} className="submit-button">
            {isSubmitting ? 'Invio in corso...' : 'Continua'}
          </button>
        </div>
      </form>
    </div>
  );
}




