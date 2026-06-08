import type { NavigationItem } from './items'

export function filterNavItems(items: NavigationItem[], userRoles: string[]): NavigationItem[] {
  const seen = new Set<string>()
  return items.filter(item => {
    if (seen.has(item.path)) return false
    const included =
      item.allowedRoles.length === 0 || item.allowedRoles.some(r => userRoles.includes(r))
    if (included) seen.add(item.path)
    return included
  })
}

export function resolveDefaultRoute(roles: string[]): string {
  if (roles.includes('ADMIN')) return '/admin'
  if (roles.includes('PEDIDOS')) return '/pedidos-panel'
  // STOCK lands on /stock/products — the real CRUD page restored post the
  // pre-Change-24 fix correction. Matches frontend-navigation spec §default-route.
  if (roles.includes('STOCK')) return '/stock/products'
  if (roles.includes('CLIENT')) return '/catalog'
  return '/catalog'
}
