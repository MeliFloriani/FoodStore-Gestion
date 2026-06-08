interface SkeletonCircleProps {
  size?: string
  className?: string
}
export function SkeletonCircle({ size = 'h-10 w-10', className = '' }: SkeletonCircleProps) {
  return <div className={`animate-pulse bg-muted rounded-full ${size} ${className}`} />
}
