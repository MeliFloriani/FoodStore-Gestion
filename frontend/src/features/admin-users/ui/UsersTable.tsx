/**
 * UsersTable — admin user management table component.
 *
 * Change 21: admin-users-management.
 *
 * Columns: Nombre + Apellido, Email, Roles (badges), Estado (badge), Fecha registro, Acciones.
 * Actions per row: [Editar datos] [Editar roles] [Desactivar]
 *
 * OQ-02 CLOSED: NO "Reactivar" button exposed in this change.
 * Frontend only shows "Desactivar" action (button hidden/disabled for inactive users).
 */

import { isUserActive } from '../types'
import type { UsuarioAdminRead } from '../types'

interface UsersTableProps {
  users: UsuarioAdminRead[]
  isLoading: boolean
  onEditData: (user: UsuarioAdminRead) => void
  onEditRoles: (user: UsuarioAdminRead) => void
  onDeactivate: (user: UsuarioAdminRead) => void
}

const ROLE_BADGE_COLORS: Record<string, string> = {
  ADMIN: 'bg-purple-100 text-purple-800',
  STOCK: 'bg-blue-100 text-blue-800',
  PEDIDOS: 'bg-orange-100 text-orange-800',
  CLIENT: 'bg-gray-100 text-gray-700',
}

function RoleBadge({ codigo }: { codigo: string }) {
  const colorClass = ROLE_BADGE_COLORS[codigo] ?? 'bg-gray-100 text-gray-700'
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {codigo}
    </span>
  )
}

function SkeletonRow() {
  return (
    <tr className="border-b border-border">
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 animate-pulse rounded bg-muted" />
        </td>
      ))}
    </tr>
  )
}

export function UsersTable({
  users,
  isLoading,
  onEditData,
  onEditRoles,
  onDeactivate,
}: UsersTableProps) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border border-border bg-background">
      <table className="min-w-full text-sm">
        <thead className="bg-muted/40">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Nombre
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Email
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Roles
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Estado
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Registro
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">
              Acciones
            </th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
          ) : users.length === 0 ? (
            <tr>
              <td
                colSpan={6}
                className="px-4 py-8 text-center text-muted-foreground"
              >
                No se encontraron usuarios.
              </td>
            </tr>
          ) : (
            users.map((user) => {
              const active = isUserActive(user)
              const registroDate = new Date(user.created_at).toLocaleDateString(
                'es-AR',
                { day: '2-digit', month: '2-digit', year: 'numeric' },
              )

              return (
                <tr
                  key={user.id}
                  className="border-b border-border transition-colors hover:bg-muted/20"
                >
                  <td className="px-4 py-3 font-medium">
                    {user.nombre} {user.apellido}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {user.email}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {user.roles.length === 0 ? (
                        <span className="text-muted-foreground text-xs">—</span>
                      ) : (
                        user.roles.map((rol) => (
                          <RoleBadge key={rol.id} codigo={rol.codigo} />
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {active ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                        Activo
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
                        Inactivo
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {registroDate}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onEditData(user)}
                        aria-label={`Editar datos de ${user.nombre} ${user.apellido}`}
                        className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
                      >
                        Editar datos
                      </button>
                      <button
                        type="button"
                        onClick={() => onEditRoles(user)}
                        aria-label={`Editar roles de ${user.nombre} ${user.apellido}`}
                        className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
                      >
                        Editar roles
                      </button>
                      {/* OQ-02: Only "Desactivar" is shown (hidden for inactive users) */}
                      {active && (
                        <button
                          type="button"
                          onClick={() => onDeactivate(user)}
                          aria-label={`Desactivar a ${user.nombre} ${user.apellido}`}
                          className="rounded px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          Desactivar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
