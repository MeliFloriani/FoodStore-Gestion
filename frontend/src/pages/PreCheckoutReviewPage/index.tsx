/**
 * PreCheckoutReviewPage — Page component for /checkout/review route.
 *
 * Composes the <PreCheckoutReview> feature component.
 * Protected by ProtectedRoute + RoleGuard(['CLIENT']) (pre-Change-24:
 * checkout flow is CLIENT-only; ADMIN is rejected to /403).
 *
 * This page is a thin shell — all logic lives in the feature component.
 */

import { PreCheckoutReview } from '@/features/pre-checkout-validation'

export default function PreCheckoutReviewPage() {
  return <PreCheckoutReview />
}
