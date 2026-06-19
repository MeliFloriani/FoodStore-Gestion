/**
 * ProfilePage — profile management page.
 *
 * Change 13: customer-profile-management.
 *
 * Replaces the Change 08 placeholder at /profile.
 * Composes two decoupled forms:
 *   - EditProfileForm: update nombre/apellido
 *   - ChangePasswordForm: change password + logout all sessions
 *
 * Loads user data via TanStack Query (GET /api/v1/auth/me).
 * Shows a loading skeleton while data loads.
 * Route is already protected by RoleGuard (Change 08) — no additional auth check needed.
 */

import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { AUTH_ME } from '@/shared/api/endpoints'
import { queryKeys } from '@/shared/lib/queryKeys'
import { EditProfileForm } from '@/features/profile/EditProfileForm'
import { ChangePasswordForm } from '@/features/profile/ChangePasswordForm'
import { SkeletonRect } from '@/shared/ui/skeleton'
import type { User } from '@/entities/auth/types'

function ProfileSkeleton() {
  return (
    <div role="status" aria-label="Cargando perfil">
      <SkeletonRect height="h-64" />
    </div>
  )
}

export default function ProfilePage() {
  const { data: user, isLoading } = useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: () => http.get<User>(AUTH_ME).then((res) => res.data),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold mb-8">Mi Perfil</h1>

      <section className="mb-12 p-6 bg-white rounded-lg shadow">
        {isLoading || !user ? (
          <ProfileSkeleton />
        ) : (
          <EditProfileForm user={user} />
        )}
      </section>

      <section className="p-6 bg-white rounded-lg shadow">
        <ChangePasswordForm />
      </section>
    </div>
  )
}
