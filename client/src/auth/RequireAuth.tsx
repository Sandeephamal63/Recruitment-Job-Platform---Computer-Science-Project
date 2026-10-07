import { Box, CircularProgress } from '@mui/material'
import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { Role } from '@/types/auth'
import { useAuth } from '@/auth/AuthContext'

function RouteLoading() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
      <CircularProgress />
    </Box>
  )
}

/** Single post-auth landing path. Both roles share one registered route, which
 *  dispatches on `user.role` — the old per-role paths (`/employer/dashboard`,
 *  `/candidate/dashboard`) were never registered, so every login landed on 404. */
export const DASHBOARD_PATH = '/dashboard'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <RouteLoading />
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <RouteLoading />
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (user.role !== role) {
    return <Navigate to={DASHBOARD_PATH} replace />
  }
  return <>{children}</>
}

/**
 * Keeps the signed-out pages signed-out. Without it an authenticated user who
 * lands on /login (a stale tab, a bookmark) is shown a working login form whose
 * submit re-authenticates and replaces their session.
 */
export function RequireAnonymous({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <RouteLoading />
  }
  if (user) {
    return <Navigate to={DASHBOARD_PATH} replace />
  }
  return <>{children}</>
}