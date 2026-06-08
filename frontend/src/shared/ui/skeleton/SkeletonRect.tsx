interface SkeletonRectProps {
  width?: string
  height?: string
  className?: string
}
export function SkeletonRect({ width = 'w-full', height = 'h-24', className = '' }: SkeletonRectProps) {
  return <div className={`animate-pulse bg-muted rounded-md ${width} ${height} ${className}`} />
}
