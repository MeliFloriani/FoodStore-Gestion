import { BODY_CLASSES } from './typography.tokens'

type BodyVariant = 'body'|'body-sm'|'caption'|'label'|'code'

interface TextProps extends React.HTMLAttributes<HTMLElement> {
  variant?: BodyVariant
  as?: 'p'|'span'
}

export function Text({ variant = 'body', as: Tag = 'p', className = '', children, ...props }: TextProps) {
  return <Tag className={`${BODY_CLASSES[variant]} ${className}`} {...props}>{children}</Tag>
}
