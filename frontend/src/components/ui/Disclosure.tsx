import { ReactNode, useId, useState } from 'react';
import './Disclosure.css';

interface DisclosureProps {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export default function Disclosure({ title, summary, defaultOpen = false, children }: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <div className="ui-disclosure">
      <button
        type="button"
        className="ui-disclosure-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <span>
          <strong>{title}</strong>
          {summary ? <em>{summary}</em> : null}
        </span>
        <span aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open ? (
        <div id={panelId} className="ui-disclosure-panel">
          {children}
        </div>
      ) : null}
    </div>
  );
}
