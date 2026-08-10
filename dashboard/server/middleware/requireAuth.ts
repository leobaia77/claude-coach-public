import type { Request, Response, NextFunction } from 'express'
import { fromNodeHeaders } from 'better-auth/node'
import { auth } from '../auth.js'

export interface SessionUser {
  id: string
  email: string
  name: string
  role: string
  onboardingStage: string
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: SessionUser
    }
  }
}

// Session-cookie auth. Loads the better-auth session and attaches req.user.
// EVERY per-user route depends on req.user.id coming from HERE (the session),
// never from a body/query param — isolation enforcement point #2.
export async function requireAuth(req: Request, res: Response, next: NextFunction) {
  try {
    const session = await auth.api.getSession({ headers: fromNodeHeaders(req.headers) })
    if (!session?.user) {
      res.status(401).json({ error: 'unauthorized' })
      return
    }
    const u = session.user as unknown as SessionUser & Record<string, unknown>
    req.user = {
      id: u.id,
      email: u.email,
      name: u.name,
      role: (u.role as string) ?? 'user',
      onboardingStage: (u.onboardingStage as string) ?? 'account',
    }
    next()
  } catch (err) {
    res.status(401).json({ error: 'unauthorized', detail: String(err) })
  }
}

export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  if (req.user?.role !== 'admin') {
    res.status(403).json({ error: 'forbidden' })
    return
  }
  next()
}
