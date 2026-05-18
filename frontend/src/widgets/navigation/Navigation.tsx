import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'
import { filterNavItems, NAVIGATION_ITEMS, ANONYMOUS_NAV_ITEMS } from '@/shared/lib/navigation'

type NavigationProps = { isPublic?: boolean }

export function Navigation({ isPublic: _isPublic }: NavigationProps) {
  const status = useAuthStore(s => s.status)
  // Read user directly to avoid creating a new array reference on each render
  // when user is null (which would cause infinite re-renders with `?? []`)
  const user = useAuthStore(s => s.user)
  const roles = user?.roles ?? []

  const items =
    status === 'authenticated'
      ? filterNavItems(NAVIGATION_ITEMS, roles)
      : ANONYMOUS_NAV_ITEMS

  return (
    <nav className="border-b border-border px-4 py-3">
      <div className="container mx-auto flex items-center gap-6">
        <span className="font-semibold text-foreground">Food Store</span>
        <ul className="flex items-center gap-4">
          {items.map(item => (
            <li key={item.key}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `text-sm transition-colors hover:text-primary ${
                    isActive ? 'font-medium text-primary' : 'text-muted-foreground'
                  }`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
