import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

export function RootLayout() {
  const navigate = useNavigate()

  useEffect(() => {
    const handleAuthExpired = () => {
      void navigate('/login')
    }

    window.addEventListener('auth:expired', handleAuthExpired)
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired)
    }
  }, [navigate])

  return <Outlet />
}
