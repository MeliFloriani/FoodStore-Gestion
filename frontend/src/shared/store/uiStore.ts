import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark' | 'system'

type Toast = {
  id: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
}

type UiState = {
  theme: Theme
  sidebarOpen: boolean
  toasts: Toast[]
}

type UiActions = {
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

type UiStore = UiState & UiActions

export const useUiStore = create<UiStore>()(
  persist(
    (set, get) => ({
      theme: 'system',
      sidebarOpen: false,
      toasts: [],

      setTheme: (theme) => set({ theme }),

      toggleTheme: () =>
        set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),

      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),

      toggleSidebar: () => set({ sidebarOpen: !get().sidebarOpen }),

      addToast: (toast) =>
        set({
          toasts: [
            ...get().toasts,
            { ...toast, id: Math.random().toString(36).slice(2) },
          ],
        }),

      removeToast: (id) =>
        set({ toasts: get().toasts.filter((t) => t.id !== id) }),
    }),
    {
      name: 'food-store-ui-theme',
      partialize: (state) => ({ theme: state.theme }),
    },
  ),
)
