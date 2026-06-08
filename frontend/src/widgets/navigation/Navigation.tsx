import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'
import { filterNavItems, NAVIGATION_ITEMS, ANONYMOUS_NAV_ITEMS } from '@/shared/lib/navigation'
import { useLogout } from '@/features/auth/hooks/useLogout'

type NavigationProps = { isPublic?: boolean }

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function Navigation({ isPublic: _isPublic }: NavigationProps) {
  const status = useAuthStore(s => s.status)
  // Read user directly to avoid creating a new array reference on each render
  // when user is null (which would cause infinite re-renders with `?? []`)
  const user = useAuthStore(s => s.user)
  const roles = user?.roles ?? []
  const logout = useLogout()
  const isAuthenticated = status === 'authenticated'

  const items = isAuthenticated
    ? filterNavItems(NAVIGATION_ITEMS, roles)
    : ANONYMOUS_NAV_ITEMS

  return (
    <nav className="border-b border-border px-4 py-3">
      <div className="container mx-auto flex flex-wrap items-center gap-4">
        <span className="font-semibold text-foreground">Food Store</span>
        <ul className="flex flex-wrap items-center gap-2">
          {items.map(item => (
            <li key={item.key}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `inline-flex min-h-[44px] items-center px-3 py-2 text-sm transition-colors hover:text-primary ${
                    isActive ? 'font-medium text-primary' : 'text-muted-foreground'
                  }`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        {isAuthenticated && (
          <button
            type="button"
            onClick={() => {
              void logout()
            }}
            aria-label="Cerrar sesión"
            className="ml-auto inline-flex min-h-[44px] items-center px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            Cerrar sesión
          </button>
        )}
      </div>
    </nav>
  )
}
