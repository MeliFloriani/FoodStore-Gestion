import { Outlet } from 'react-router-dom'
import { Navigation } from '@/widgets/navigation/Navigation'

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navigation isPublic />
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
