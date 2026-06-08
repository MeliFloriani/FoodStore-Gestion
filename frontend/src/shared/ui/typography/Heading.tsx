import { HEADING_CLASSES } from './typography.tokens'

interface HeadingProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level?: 1|2|3|4|5|6
}

export function Heading({ level = 1, className = '', children, ...props }: HeadingProps) {
  const Tag = `h${level}` as 'h1'|'h2'|'h3'|'h4'|'h5'|'h6'
  return <Tag className={`${HEADING_CLASSES[level]} ${className}`} {...props}>{children}</Tag>
}
