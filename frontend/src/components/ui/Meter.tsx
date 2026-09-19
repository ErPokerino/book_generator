import './Meter.css';

interface MeterProps {
  value: number;
  label?: string;
}

export default function Meter({ value, label }: MeterProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className="ui-meter" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(clamped)} aria-label={label}>
      <span style={{ width: `${clamped}%` }} />
    </div>
  );
}
