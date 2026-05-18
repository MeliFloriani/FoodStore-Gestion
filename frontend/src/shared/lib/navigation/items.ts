export interface NavigationItem {
  key: string
  label: string
  path: string
  icon?: string
  allowedRoles: string[]
}

export const NAVIGATION_ITEMS: NavigationItem[] = [
  // CLIENT items
  { key: 'catalog', label: 'Catálogo', path: '/catalog', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'cart', label: 'Mi Carrito', path: '/cart', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'orders', label: 'Mis Pedidos', path: '/orders', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'profile', label: 'Mi Perfil', path: '/profile', allowedRoles: ['CLIENT', 'ADMIN'] },
  { key: 'addresses', label: 'Mis Direcciones', path: '/addresses', allowedRoles: ['CLIENT', 'ADMIN'] },
  // STOCK items
  { key: 'stock-products', label: 'Productos', path: '/stock/products', allowedRoles: ['STOCK', 'ADMIN'] },
  { key: 'stock-categories', label: 'Categorías', path: '/stock/categories', allowedRoles: ['STOCK', 'ADMIN'] },
  { key: 'stock-ingredients', label: 'Ingredientes', path: '/stock/ingredients', allowedRoles: ['STOCK', 'ADMIN'] },
  { key: 'stock-inventory', label: 'Stock', path: '/stock/inventory', allowedRoles: ['STOCK', 'ADMIN'] },
  // PEDIDOS items
  { key: 'pedidos-panel', label: 'Panel de Pedidos', path: '/pedidos-panel', allowedRoles: ['PEDIDOS', 'ADMIN'] },
  // ADMIN-only items
  { key: 'admin-users', label: 'Usuarios', path: '/admin/users', allowedRoles: ['ADMIN'] },
  { key: 'admin-metrics', label: 'Métricas', path: '/admin/metrics', allowedRoles: ['ADMIN'] },
]

export const ANONYMOUS_NAV_ITEMS: NavigationItem[] = [
  { key: 'catalog-public', label: 'Catálogo', path: '/catalog', allowedRoles: [] },
  { key: 'login', label: 'Login', path: '/login', allowedRoles: [] },
  { key: 'register', label: 'Registrarse', path: '/register', allowedRoles: [] },
]
