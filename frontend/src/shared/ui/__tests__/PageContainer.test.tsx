import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageContainer } from '../layout/PageContainer'

describe('PageContainer', () => {
  it('renders children', () => {
    render(<PageContainer><span data-testid="child">Hello</span></PageContainer>)
    expect(screen.getByTestId('child')).toHaveTextContent('Hello')
  })

  it('applies default classes', () => {
    const { container } = render(<PageContainer>Content</PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('mx-auto')
    expect(div.className).toContain('max-w-screen-xl')
    expect(div.className).toContain('px-4')
  })

  it('merges custom className', () => {
    const { container } = render(<PageContainer className="custom-class">Content</PageContainer>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('custom-class')
    expect(div.className).toContain('mx-auto')
  })
})
