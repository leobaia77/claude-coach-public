import { createAuthClient } from 'better-auth/react'

// Same-origin: the API and frontend are served by the one Express process.
export const authClient = createAuthClient({ basePath: '/api/auth' })

export const { useSession, signIn, signUp, signOut } = authClient
