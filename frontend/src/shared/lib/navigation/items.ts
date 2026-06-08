export interface NavigationItem {
  key: string
  label: string
  path: string
  icon?: string
  allowedRoles: string[]
}

export const NAVIGATION_ITEMS: NavigationItem[] = [
  // CLIENT items
  // Pre-Change-24 surgical fix: cart/orders/addresses are CLIENT-only flows.
  // ADMIN must not see "Mi Carrito" / "Mis Pedidos" / "Mis Direcciones" — admin
  // manages orders via /pedidos-panel and /admin/* instead.
  { key: 'catalog', label: 'Catálogo', path: '/catalog', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'cart', label: 'Mi Carrito', path: '/cart', allowedRoles: ['CLIENT'] },
  { key: 'orders', label: 'Mis Pedidos', path: '/orders', allowedRoles: ['CLIENT'] },
  { key: 'profile', label: 'Mi Perfil', path: '/profile', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'addresses', label: 'Mis Direcciones', path: '/addresses', allowedRoles: ['CLIENT'] },
  // STOCK + ADMIN — catálogo / stock administration. /stock/inventory is
  // intentionally NOT advertised: no real implementation exists yet, so
  // exposing the link would re-introduce the placeholder leak that motivated
  // the pre-Change-24 fix.
  { key: 'stock-ingredients', label: 'Ingredientes', path: '/stock/ingredients', allowedRoles: ['STOCK', 'ADMIN'] },
  { key: 'stock-categories', label: 'Categorías', path: '/stock/categories', allowedRoles: ['STOCK', 'ADMIN'] },
  { key: 'stock-products', label: 'Productos', path: '/stock/products', allowedRoles: ['STOCK', 'ADMIN'] },
  // PEDIDOS items
  { key: 'pedidos-panel', label: 'Panel de Pedidos', path: '/pedidos-panel', allowedRoles: ['PEDIDOS', 'ADMIN'] },
  // ADMIN-only items
  { key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] },
  { key: 'admin-metrics', label: 'Métricas', path: '/admin/metricas', allowedRoles: ['ADMIN'] },
]

export const ANONYMOUS_NAV_ITEMS: NavigationItem[] = [
  { key: 'catalog-public', label: 'Catálogo', path: '/catalog', allowedRoles: [] },
  { key: 'login', label: 'Login', path: '/login', allowedRoles: [] },
  { key: 'register', label: 'Registrarse', path: '/register', allowedRoles: [] },
]
