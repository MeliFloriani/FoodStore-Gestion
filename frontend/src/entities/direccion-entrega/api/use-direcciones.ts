/**
 * TanStack Query v5 hooks for the DireccionEntrega entity.
 *
 * Change 14: delivery-addresses-management.
 *
 * Hooks:
 *   - useAddresses(): query, enabled only when user is authenticated
 *   - useAddress(id): query for a single address
 *   - useCreateAddress(): mutation — invalidates ['addresses'] on success
 *   - useUpdateAddress(): mutation — invalidates ['addresses'] and ['addresses', id]
 *   - useSetMainAddress(): mutation — invalidates ['addresses'] on success
 *   - useDeleteAddress(): mutation — invalidates ['addresses'] on success
 *
 * All mutations invalidate the addresses cache so the list re-fetches.
 * Server state is managed entirely by TanStack Query — NOT duplicated in Zustand.
 *
 * TanStack Query v5: use `isPending` (not `isLoading`) for mutations.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/entities/auth/model/store'
import type { DireccionEntregaCreateDto, DireccionEntregaUpdateDto } from '../model/types'
import {
  createAddress,
  deleteAddress,
  getAddress,
  getAddresses,
  setMainAddress,
  updateAddress,
} from './direccion-entrega-api'

/** Query key factory for addresses (local to this module). */
const addressKeys = {
  all: ['addresses'] as const,
  detail: (id: string) => ['addresses', id] as const,
}

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

/**
 * useAddresses — fetch all active addresses for the authenticated user.
 *
 * Only active when the user is authenticated (enabled: !!user).
 * Automatically refetches when the cache is invalidated by mutations.
 */
export function useAddresses() {
  const user = useAuthStore((state) => state.user)

  return useQuery({
    queryKey: addressKeys.all,
    queryFn: getAddresses,
    enabled: !!user,
  })
}

/**
 * useAddress — fetch a single address by ID.
 */
export function useAddress(id: string) {
  return useQuery({
    queryKey: addressKeys.detail(id),
    queryFn: () => getAddress(id),
    enabled: !!id,
  })
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * useCreateAddress — mutation to create a new delivery address.
 * Invalidates ['addresses'] on success so the list re-fetches.
 */
export function useCreateAddress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DireccionEntregaCreateDto) => createAddress(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: addressKeys.all })
    },
  })
}

/**
 * useUpdateAddress — mutation to partially update a delivery address.
 * Invalidates both the list and the specific address cache on success.
 */
export function useUpdateAddress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DireccionEntregaUpdateDto }) =>
      updateAddress(id, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: addressKeys.all })
      queryClient.invalidateQueries({ queryKey: addressKeys.detail(variables.id) })
    },
  })
}

/**
 * useSetMainAddress — mutation to mark an address as principal.
 * Invalidates ['addresses'] on success so all addresses refresh.
 */
export function useSetMainAddress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => setMainAddress(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: addressKeys.all })
    },
  })
}

/**
 * useDeleteAddress — mutation to soft-delete a delivery address.
 * Invalidates ['addresses'] on success so the list removes the deleted entry.
 */
export function useDeleteAddress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => deleteAddress(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: addressKeys.all })
    },
  })
}
