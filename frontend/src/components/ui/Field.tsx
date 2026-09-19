import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';
import './Field.css';

interface FieldShellProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  htmlFor?: string;
  children: ReactNode;
}

export function Field({ label, hint, error, required, htmlFor, children }: FieldShellProps) {
  return (
    <label className={`ui-field${error ? ' has-error' : ''}`} htmlFor={htmlFor}>
      <span className="ui-field-label">
        {label}
        {required ? <abbr className="ui-field-required" title="Obbligatorio">*</abbr> : null}
      </span>
      {children}
      {error ? <em className="ui-field-error">{error}</em> : hint ? <span className="ui-field-hint">{hint}</span> : null}
    </label>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`ui-control ${props.className ?? ''}`.trim()} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`ui-control ${props.className ?? ''}`.trim()} />;
}

export function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`ui-control ${props.className ?? ''}`.trim()} />;
}
