import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import type React from 'react'
import { RoleGuard } from '../RoleGuard'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mockClientUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

const mockAdminUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440001',
  nombre: 'Admin',
  apellido: 'User',
  email: 'admin@example.com',
  roles: ['ADMIN'],
}

describe('Chunk Security — guard-before-Suspense invariant (D-08)', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('CLIENT user at /admin redirects to /403 without triggering AdminPage chunk', () => {
    // Create a spy-tracked factory function that we can check was not called
    const chunkImportSpy = vi.fn().mockResolvedValue({
      default: function AdminPage() {
        return <div>Admin Page</div>
      },
    })
    const LazyAdminPage = lazy(chunkImportSpy)

    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route element={<RoleGuard roles={['ADMIN']} />}>
            <Route
              path="/admin"
              element={
                <Suspense fallback={<div>Loading chunk...</div>}>
                  <LazyAdminPage />
                </Suspense>
              }
            />
          </Route>
          <Route path="/403" element={<div>Forbidden Page</div>} />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>,
    )

    // Assert: guard redirects to /403
    expect(screen.getByText('Forbidden Page')).toBeInTheDocument()

    // Assert: the lazy chunk import was NOT triggered
    expect(chunkImportSpy).not.toHaveBeenCalled()
  })

  it('ADMIN user at /admin triggers AdminPage chunk download (import spy called)', async () => {
    // We need a never-resolving promise so the Suspense fallback stays visible
    // and we can confirm the spy was called without worrying about component rendering
    let resolveModule!: (value: { default: React.ComponentType }) => void
    const chunkImportSpy = vi.fn(
      () =>
        new Promise<{ default: React.ComponentType }>(resolve => {
          resolveModule = resolve
        }),
    )
    const LazyAdminPage = lazy(chunkImportSpy)

    useAuthStore.setState({ status: 'authenticated', user: mockAdminUser })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route element={<RoleGuard roles={['ADMIN']} />}>
            <Route
              path="/admin"
              element={
                <Suspense fallback={<div>Loading chunk...</div>}>
                  <LazyAdminPage />
                </Suspense>
              }
            />
          </Route>
          <Route path="/403" element={<div>Forbidden Page</div>} />
        </Routes>
      </MemoryRouter>,
    )

    // Guard passes, Suspense renders its fallback while lazy loads
    expect(screen.getByText('Loading chunk...')).toBeInTheDocument()

    // The import factory WAS called — chunk download was triggered
    expect(chunkImportSpy).toHaveBeenCalledTimes(1)

    // Resolve so there are no dangling promises
    resolveModule({ default: function AdminPage() { return <div>Admin Page</div> } })
  })
})
