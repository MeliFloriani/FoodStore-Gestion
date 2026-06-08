import { SkeletonRect } from './SkeletonRect'
import { SkeletonLine } from './SkeletonLine'

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      <SkeletonRect height="h-48" />
      <SkeletonLine width="w-3/4" />
      <SkeletonLine width="w-1/2" />
      <SkeletonLine width="w-full" />
    </div>
  )
}
