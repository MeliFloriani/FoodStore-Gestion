/**
 * UserFilters — role and status filter selects for user management.
 *
 * Change 21: admin-users-management.
 *
 * - Rol select: "Todos", "ADMIN", "STOCK", "PEDIDOS", "CLIENT"
 * - Estado select: "Todos", "Activos", "Inactivos"
 * - No debounce (selects trigger immediately).
 */

interface UserFiltersProps {
  rol: string | undefined
  activo: boolean | undefined
  onRolChange: (value: string | undefined) => void
  onActivoChange: (value: boolean | undefined) => void
  disabled?: boolean
}

export function UserFilters({
  rol,
  activo,
  onRolChange,
  onActivoChange,
  disabled = false,
}: UserFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Rol filter */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="filter-rol"
          className="text-sm font-medium text-muted-foreground"
        >
          Rol:
        </label>
        <select
          id="filter-rol"
          value={rol ?? ''}
          onChange={(e) => onRolChange(e.target.value || undefined)}
          disabled={disabled}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Todos</option>
          <option value="ADMIN">ADMIN</option>
          <option value="STOCK">STOCK</option>
          <option value="PEDIDOS">PEDIDOS</option>
          <option value="CLIENT">CLIENT</option>
        </select>
      </div>

      {/* Estado filter */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="filter-activo"
          className="text-sm font-medium text-muted-foreground"
        >
          Estado:
        </label>
        <select
          id="filter-activo"
          value={activo === undefined ? '' : activo ? 'true' : 'false'}
          onChange={(e) => {
            const val = e.target.value
            if (val === '') onActivoChange(undefined)
            else onActivoChange(val === 'true')
          }}
          disabled={disabled}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Todos</option>
          <option value="true">Activos</option>
          <option value="false">Inactivos</option>
        </select>
      </div>
    </div>
  )
}
