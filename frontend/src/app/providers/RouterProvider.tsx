import { RouterProvider as ReactRouterProvider } from 'react-router-dom'
import { router } from '@/app/router/routes'

export function RouterProvider() {
  return <ReactRouterProvider router={router} />
}
