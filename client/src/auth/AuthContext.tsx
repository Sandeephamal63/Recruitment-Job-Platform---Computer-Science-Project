import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import * as authApi from '@/api/auth'
import type { RegisterPayload, User } from '@/types/auth'
import { tokenStore } from '@/auth/tokenStore'

interface AuthContextValue {
  user: User | null
  loading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<User>
  register: (payload: RegisterPayload) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    async function hydrate() {
      const token = tokenStore.getAccess()
      if (!token) {
        if (active) setLoading(false)
        return
      }
      try {
        const current = await authApi.me()
        if (active) setUser(current)
      } catch {
        if (tokenStore.getAccess() === token) {
          tokenStore.clear()
          if (active) setUser(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    hydrate()
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const session = await authApi.login(email, password)
    tokenStore.set(session.accessToken, session.refreshToken)
    setUser(session.user)
    return session.user
  }, [])

  const register = useCallback(async (payload: RegisterPayload) => {
    const session = await authApi.register(payload)
    tokenStore.set(session.accessToken, session.refreshToken)
    setUser(session.user)
    return session.user
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = tokenStore.getRefresh()
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken)
      }
    } catch {}
    tokenStore.clear()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, isAuthenticated: !!user, login, register, logout }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}