import { describe, it, expect, beforeEach } from 'vitest'
import { useUiStore } from '@/shared/store/uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    useUiStore.setState({ theme: 'system', sidebarOpen: false, toasts: [] })
  })

  it('default theme is system', () => {
    expect(useUiStore.getState().theme).toBe('system')
  })

  it('setTheme updates theme', () => {
    useUiStore.getState().setTheme('dark')
    expect(useUiStore.getState().theme).toBe('dark')
  })

  it('toggleTheme switches between dark and light', () => {
    useUiStore.getState().setTheme('dark')
    useUiStore.getState().toggleTheme()
    expect(useUiStore.getState().theme).toBe('light')
    useUiStore.getState().toggleTheme()
    expect(useUiStore.getState().theme).toBe('dark')
  })

  it('partialize persists only theme field', () => {
    useUiStore.getState().setSidebarOpen(true)
    const partial = useUiStore.persist.getOptions().partialize?.(useUiStore.getState())
    expect(partial).toHaveProperty('theme')
    expect(partial).not.toHaveProperty('sidebarOpen')
    expect(partial).not.toHaveProperty('toasts')
  })

  it('sidebarOpen is ephemeral (not in partialize)', () => {
    useUiStore.getState().setSidebarOpen(true)
    const partial = useUiStore.persist.getOptions().partialize?.(useUiStore.getState())
    expect(partial).not.toHaveProperty('sidebarOpen')
  })

  it('toggleSidebar flips sidebarOpen', () => {
    expect(useUiStore.getState().sidebarOpen).toBe(false)
    useUiStore.getState().toggleSidebar()
    expect(useUiStore.getState().sidebarOpen).toBe(true)
  })

  it('addToast adds a toast with unique id', () => {
    useUiStore.getState().addToast({ message: 'Hello', type: 'success' })
    const toasts = useUiStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]?.message).toBe('Hello')
    expect(toasts[0]?.id).toBeTruthy()
  })

  it('removeToast removes toast by id', () => {
    useUiStore.getState().addToast({ message: 'Hello', type: 'info' })
    const id = useUiStore.getState().toasts[0]?.id
    if (!id) throw new Error('No toast id')
    useUiStore.getState().removeToast(id)
    expect(useUiStore.getState().toasts).toHaveLength(0)
  })
})
