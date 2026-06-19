import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Heading } from '../typography/Heading'

describe('Heading', () => {
  it('renders h1 by default', () => {
    render(<Heading>Título</Heading>)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveTextContent('Título')
  })

  it('renders the specified heading level', () => {
    render(<Heading level={3}>Sección</Heading>)
    const h3 = screen.getByRole('heading', { level: 3 })
    expect(h3).toHaveTextContent('Sección')
  })

  it('renders h6', () => {
    render(<Heading level={6}>Pequeño</Heading>)
    const h6 = screen.getByRole('heading', { level: 6 })
    expect(h6).toHaveTextContent('Pequeño')
  })

  it('applies className from tokens', () => {
    render(<Heading level={1}>Styled</Heading>)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1.className).toContain('font-display')
  })

  it('merges custom className', () => {
    render(<Heading level={2} className="my-class">Custom</Heading>)
    const h2 = screen.getByRole('heading', { level: 2 })
    expect(h2.className).toContain('my-class')
    expect(h2.className).toContain('font-display')
  })
})
