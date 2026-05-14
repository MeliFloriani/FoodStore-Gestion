export type User = {
  id: number
  nombre: string
  email: string
  roles: string[]
}

export type AuthStatus =
  | 'idle'
  | 'authenticating'
  | 'authenticated'
  | 'unauthenticated'
