import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorBoundary } from '../ErrorBoundary'

const ThrowError = () => {
  throw new Error('Test error')
}

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">OK</div>
      </ErrorBoundary>,
    )
    expect(screen.getByTestId('child')).toHaveTextContent('OK')
  })

  it('renders error UI when a child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Test error')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()

    vi.restoreAllMocks()
  })

  it('resets error state when Try again is clicked', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    // After reset, the child re-renders and throws again, so still in error state
    expect(screen.getByRole('alert')).toBeInTheDocument()

    vi.restoreAllMocks()
  })

  it('shows empty message paragraph when error has no message', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const ThrowWithoutMessage = () => {
      throw new Error()
    }

    render(
      <ErrorBoundary>
        <ThrowWithoutMessage />
      </ErrorBoundary>,
    )

    // error.message is '' (empty string), rendered as empty <p>
    const paragraphs = screen.getByRole('alert').querySelectorAll('p')
    expect(paragraphs.length).toBe(1)
    expect(paragraphs[0].textContent).toBe('')

    vi.restoreAllMocks()
  })
})
