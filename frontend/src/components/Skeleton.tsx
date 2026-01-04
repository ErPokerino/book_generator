import './Skeleton.css'

interface SkeletonTextProps {
  lines?: number
  width?: string
  className?: string
}

export function SkeletonText({ lines = 1, width, className = '' }: SkeletonTextProps) {
  return (
    <div className={`skeleton-text ${className}`}>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="skeleton-line"
          style={{
            width: index === lines - 1 && lines > 1 ? '75%' : width || '100%',
          }}
        />
      ))}
    </div>
  )
}

interface SkeletonBoxProps {
  width?: string
  height?: string
  className?: string
  borderRadius?: string
}

export function SkeletonBox({ width = '100%', height = '1rem', className = '', borderRadius }: SkeletonBoxProps) {
  return (
    <div
      className={`skeleton-box ${className}`}
      style={{
        width,
        height,
        borderRadius: borderRadius || 'var(--radius-sm, 4px)',
      }}
    />
  )
}

interface SkeletonCardProps {
  className?: string
}

export function SkeletonCard({ className = '' }: SkeletonCardProps) {
  return (
    <div className={`skeleton-card ${className}`}>
      {/* Cover Image Skeleton */}
      <div className="skeleton-card-cover" />
      
      {/* Content */}
      <div className="skeleton-card-content">
        <SkeletonBox width="60%" height="1.5rem" className="skeleton-title" />
        <SkeletonText lines={2} width="90%" className="skeleton-description" />
        <div className="skeleton-card-meta">
          <SkeletonBox width="80px" height="1rem" />
          <SkeletonBox width="60px" height="1rem" />
        </div>
        <div className="skeleton-card-actions">
          <SkeletonBox width="100px" height="2rem" borderRadius="var(--radius-md, 8px)" />
          <SkeletonBox width="80px" height="2rem" borderRadius="var(--radius-md, 8px)" />
        </div>
      </div>
    </div>
  )
}

interface SkeletonChapterProps {
  className?: string
}

export function SkeletonChapter({ className = '' }: SkeletonChapterProps) {
  return (
    <div className={`skeleton-chapter ${className}`}>
      <SkeletonBox width="40%" height="2rem" className="skeleton-chapter-title" />
      <SkeletonText lines={8} className="skeleton-chapter-content" />
    </div>
  )
}

interface SkeletonChartProps {
  width?: string
  height?: string
  className?: string
}

export function SkeletonChart({ width = '100%', height = '300px', className = '' }: SkeletonChartProps) {
  return (
    <div
      className={`skeleton-chart ${className}`}
      style={{ width, height }}
    >
      {/* Chart lines skeleton */}
      <div className="skeleton-chart-lines">
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="skeleton-chart-line"
            style={{
              width: `${60 + Math.random() * 40}%`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
