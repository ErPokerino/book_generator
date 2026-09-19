import './ProgressBar.css';

interface ProgressBarProps {
  percentage: number;
  className?: string;
  showGlow?: boolean;
}

export default function ProgressBar({ percentage, className = '' }: ProgressBarProps) {
  const clampedPercentage = Math.min(100, Math.max(0, percentage));

  return (
    <div
      className={`progress-bar-container ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clampedPercentage)}
    >
      <div className="progress-bar-fill" style={{ width: `${clampedPercentage}%` }} />
    </div>
  );
}
