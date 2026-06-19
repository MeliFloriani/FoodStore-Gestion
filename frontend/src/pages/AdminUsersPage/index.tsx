/**
 * AdminUsersPage — Admin user management panel.
 *
 * Change 21: admin-users-management.
 * Route: /admin/users (protected by RoleGuard ADMIN from parent route)
 *
 * Composes:
 *   - UserSearchBar (debounced search, 400ms, min 3 chars)
 *   - UserFilters (rol + activo selects, immediate)
 *   - UsersTable (paginated, skeleton loader, actions)
 *   - Pagination controls (Previous/Next + page indicator)
 *   - EditUserModal (lazy — data editing)
 *   - EditUserRolesModal (lazy — role replacement)
 *   - DeactivateUserModal (lazy — destructive confirmation)
 *
 * State:
 *   - page, size (default 20), q (raw), rol, activo
 *   - selectedUser: UsuarioAdminRead | null
 *   - openModal: 'edit' | 'roles' | 'deactivate' | null
 *
 * OQ-02 CLOSED: NO "Reactivar" button or action exposed anywhere.
 */

import { lazy, Suspense, useState, useCallback } from 'react'
import { useUsersQuery } from '@/features/admin-users/api/useUsersQuery'
import { useDeactivateUserMutation } from '@/features/admin-users/api/useDeactivateUserMutation'
import { UsersTable } from '@/features/admin-users/ui/UsersTable'
import { UserSearchBar } from '@/features/admin-users/ui/UserSearchBar'
import { UserFilters } from '@/features/admin-users/ui/UserFilters'
import { SkeletonList } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'
import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
import type { UsuarioAdminRead } from '@/features/admin-users/types'

// Lazy imports for modals (code splitting)
const EditUserModal = lazy(() =>
  import('@/features/admin-users/ui/EditUserModal').then((m) => ({ default: m.EditUserModal })),
)
const EditUserRolesModal = lazy(() =>
  import('@/features/admin-users/ui/EditUserRolesModal').then((m) => ({
    default: m.EditUserRolesModal,
  })),
)

type ModalType = 'edit' | 'roles' | null

function ModalSpinner() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

export default function AdminUsersPage() {
  const [page, setPage] = useState(1)
  const size = 20
  const [q, setQ] = useState('')
  const [rol, setRol] = useState<string | undefined>(undefined)
  const [activo, setActivo] = useState<boolean | undefined>(undefined)
  const [selectedUser, setSelectedUser] = useState<UsuarioAdminRead | null>(null)
  const [openModal, setOpenModal] = useState<ModalType>(null)

  const toast = useToast()
  const confirm = useConfirm()
  const deactivateMutation = useDeactivateUserMutation()

  const { data, isLoading } = useUsersQuery({ page, size, q, rol, activo })
  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pages = data?.pages ?? 0

  function openEditModal(user: UsuarioAdminRead) {
    setSelectedUser(user)
    setOpenModal('edit')
  }

  function openRolesModal(user: UsuarioAdminRead) {
    setSelectedUser(user)
    setOpenModal('roles')
  }

  function closeModal() {
    setOpenModal(null)
    setSelectedUser(null)
  }

  const handleSearchChange = useCallback((value: string) => {
    setQ(value)
    setPage(1)
  }, [])

  function handleRolChange(value: string | undefined) {
    setRol(value)
    setPage(1)
  }

  function handleActivoChange(value: boolean | undefined) {
    setActivo(value)
    setPage(1)
  }

  function handleEditSuccess() {
    toast.toast({ variant: 'success', title: 'Usuario actualizado correctamente.' })
    closeModal()
  }

  function handleRolesSuccess() {
    toast.toast({ variant: 'success', title: 'Roles actualizados correctamente.' })
    closeModal()
  }

  async function handleDeactivate(user: UsuarioAdminRead) {
    const ok = await confirm.confirm({
      variant: 'destructive',
      title: '¿Desactivar usuario?',
    })
    if (!ok) return
    deactivateMutation.mutate(
      { id: user.id, data: { activo: false } },
      {
        onSuccess: () => {
          toast.toast({ variant: 'success', title: 'Usuario desactivado correctamente.' })
        },
        onError: () => {
          toast.toast({ variant: 'error', title: 'Error al desactivar usuario.' })
        },
      },
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Gestión de Usuarios</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {total > 0 ? `${total} usuario${total !== 1 ? 's' : ''} en total` : ''}
        </p>
      </div>

      {/* Search + Filters row */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <UserSearchBar onChange={handleSearchChange} disabled={isLoading} />
        <UserFilters
          rol={rol}
          activo={activo}
          onRolChange={handleRolChange}
          onActivoChange={handleActivoChange}
          disabled={isLoading}
        />
      </div>

      {/* Table / Skeleton / Empty state */}
      {isLoading ? (
        <SkeletonList rows={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Sin usuarios"
          description="No hay usuarios registrados."
        />
      ) : (
        <UsersTable
          users={items}
          isLoading={false}
          onEditData={openEditModal}
          onEditRoles={openRolesModal}
          onDeactivate={handleDeactivate}
        />
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Página {page} de {pages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || isLoading}
              aria-label="Página anterior"
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted transition-colors"
            >
              Anterior
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages || isLoading}
              aria-label="Página siguiente"
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted transition-colors"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}

      {/* Modals — lazy loaded, only mounted when open */}
      {openModal === 'edit' && selectedUser && (
        <Suspense fallback={<ModalSpinner />}>
          <EditUserModal
            user={selectedUser}
            onClose={closeModal}
            onSuccess={handleEditSuccess}
          />
        </Suspense>
      )}
      {openModal === 'roles' && selectedUser && (
        <Suspense fallback={<ModalSpinner />}>
          <EditUserRolesModal
            user={selectedUser}
            onClose={closeModal}
            onSuccess={handleRolesSuccess}
          />
        </Suspense>
      )}
      {/* Note: Deactivation uses useConfirm directly — no lazy modal needed */}
    </div>
  )
}
