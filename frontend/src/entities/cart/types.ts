// Breaking Change from Change 05:
// - producto_id: number  →  string (UUID, aligned with ProductoPublicoRead.id)
// - personalizacion: number[]  →  string[] (UUID array, aligned with ProductoIngredienteRead.ingrediente_id)
export interface CartItem {
  producto_id: string
  nombre: string
  precio: number
  cantidad: number
  imagen_url: string
  personalizacion: string[] // sorted, deduplicated UUIDs of excluded ingredient IDs
}

export type AddItemResult =
  | { ok: true }
  | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }
