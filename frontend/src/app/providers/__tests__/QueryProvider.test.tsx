import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryProvider } from '../QueryProvider'

describe('QueryProvider', () => {
  it('renders children', () => {
    render(
      <QueryProvider>
        <p>Hello world</p>
      </QueryProvider>,
    )
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('provides a query client that works', async () => {
    render(
      <QueryProvider>
        <p>Client ready</p>
      </QueryProvider>,
    )
    expect(screen.getByText('Client ready')).toBeInTheDocument()
  })
})
