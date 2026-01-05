import { motion } from 'framer-motion';
import './ProgressBar.css';

interface ProgressBarProps {
  percentage: number;
  className?: string;
  showGlow?: boolean;
}

export default function ProgressBar({ 
  percentage, 
  className = '',
  showGlow = true
}: ProgressBarProps) {
  const clampedPercentage = Math.min(100, Math.max(0, percentage));

  return (
    <div className={`progress-bar-container ${className}`}>
      <motion.div
        className="progress-bar-fill"
        initial={{ width: 0 }}
        animate={{ width: `${clampedPercentage}%` }}
        transition={{
          type: "spring",
          stiffness: 50,
          damping: 15,
          mass: 0.8
        }}
        style={{
          boxShadow: showGlow && clampedPercentage > 0 && clampedPercentage < 100
            ? '0 0 8px rgba(139, 92, 246, 0.4)'
            : 'none'
        }}
      />
    </div>
  );
}
