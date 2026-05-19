/**
 * Profile feature barrel exports.
 *
 * Change 13: customer-profile-management.
 *
 * FSD: features/ layer — exports for pages/ and other consumers above in the hierarchy.
 */

export { EditProfileForm } from './EditProfileForm'
export { ChangePasswordForm } from './ChangePasswordForm'
export { useUpdateProfile } from './hooks/useUpdateProfile'
export { useChangePassword } from './hooks/useChangePassword'
export type { ProfileUpdatePayload } from './hooks/useUpdateProfile'
export type { ChangePasswordPayload } from './hooks/useChangePassword'
