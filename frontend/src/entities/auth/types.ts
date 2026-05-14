export type User = {
  id: string
  nombre: string
  apellido: string
  email: string
  roles: string[]
}

export type AuthStatus =
  | 'idle'
  | 'authenticating'
  | 'authenticated'
  | 'unauthenticated'
