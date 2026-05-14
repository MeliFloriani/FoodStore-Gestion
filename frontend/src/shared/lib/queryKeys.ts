/**
 * Centralized, namespaced query key factory.
 * All namespaces use `as const` tuples for type safety.
 */
export const queryKeys = {
  auth: {
    all: () => ['auth'] as const,
    me: () => ['auth', 'me'] as const,
  },
  catalog: {
    all: () => ['catalog'] as const,
    products: (filters?: Record<string, unknown>) =>
      ['catalog', 'products', filters] as const,
    product: (id: number) => ['catalog', 'product', id] as const,
    categories: () => ['catalog', 'categories'] as const,
  },
  cart: {
    all: () => ['cart'] as const,
  },
  orders: {
    all: () => ['orders'] as const,
    order: (id: number) => ['orders', 'order', id] as const,
    list: (filters?: Record<string, unknown>) =>
      ['orders', 'list', filters] as const,
  },
  payment: {
    all: () => ['payment'] as const,
    preference: (pedidoId: number) =>
      ['payment', 'preference', pedidoId] as const,
  },
} as const
