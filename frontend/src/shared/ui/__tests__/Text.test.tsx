import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Text } from '../typography/Text'

describe('Text', () => {
  it('renders as <p> by default', () => {
    render(<Text>Hello</Text>)
    const el = screen.getByText('Hello')
    expect(el.tagName).toBe('P')
  })

  it('renders as <span> when as="span"', () => {
    render(<Text as="span">Inline</Text>)
    const el = screen.getByText('Inline')
    expect(el.tagName).toBe('SPAN')
  })

  it('applies body class by default', () => {
    render(<Text>Body</Text>)
    const el = screen.getByText('Body')
    expect(el.className).toContain('text-base')
  })

  it('applies caption class for variant="caption"', () => {
    render(<Text variant="caption">Small</Text>)
    const el = screen.getByText('Small')
    expect(el.className).toContain('text-xs')
    expect(el.className).toContain('text-muted-foreground')
  })

  it('applies label class for variant="label"', () => {
    render(<Text variant="label">Label</Text>)
    const el = screen.getByText('Label')
    expect(el.className).toContain('font-medium')
  })

  it('applies body-sm class', () => {
    render(<Text variant="body-sm">Small body</Text>)
    const el = screen.getByText('Small body')
    expect(el.className).toContain('text-sm')
  })

  it('applies code class', () => {
    render(<Text variant="code">const x = 1</Text>)
    const el = screen.getByText('const x = 1')
    expect(el.className).toContain('font-mono')
  })

  it('merges custom className', () => {
    render(<Text className="custom-class">Custom</Text>)
    const el = screen.getByText('Custom')
    expect(el.className).toContain('custom-class')
  })
})
