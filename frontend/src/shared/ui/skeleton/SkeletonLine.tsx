interface SkeletonLineProps {
  width?: string
  className?: string
}
export function SkeletonLine({ width = 'w-full', className = '' }: SkeletonLineProps) {
  return <div className={`animate-pulse bg-muted rounded h-4 ${width} ${className}`} />
}
