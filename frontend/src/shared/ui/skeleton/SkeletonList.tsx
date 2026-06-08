import { SkeletonCard } from './SkeletonCard'

interface SkeletonListProps {
  rows?: number
  className?: string
}
export function SkeletonList({ rows = 4, className = '' }: SkeletonListProps) {
  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
