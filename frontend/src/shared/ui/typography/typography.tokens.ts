export const HEADING_CLASSES: Record<1|2|3|4|5|6, string> = {
  1: 'text-4xl font-display font-bold leading-tight',
  2: 'text-2xl font-display font-semibold leading-snug',
  3: 'text-xl font-display font-semibold leading-snug',
  4: 'text-lg font-sans font-semibold leading-normal',
  5: 'text-base font-sans font-medium leading-normal',
  6: 'text-sm font-sans font-medium leading-normal',
}

export const BODY_CLASSES: Record<'body'|'body-sm'|'caption'|'label'|'code', string> = {
  body: 'text-base font-sans leading-relaxed',
  'body-sm': 'text-sm font-sans leading-relaxed',
  caption: 'text-xs font-sans text-muted-foreground',
  label: 'text-sm font-sans font-medium',
  code: 'font-mono text-sm',
}
